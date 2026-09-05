#!/usr/bin/env python3
from pathlib import Path

vc = Path('app/src/main/java/com/bydmate/app/voice/VoiceController.kt')
text = vc.read_text(encoding='utf-8')

# Build62: independent per-session diagnostic state + watchdog.
anchor = 'private var lastSpeakingSeenMs = 0L\n'
insert = '''private var lastSpeakingSeenMs = 0L\n\n    // BUILD62: automatic diagnostic state for one voice session.\n    private data class Build62Diag(\n        val startedAtMs: Long = System.currentTimeMillis(),\n        var heardAtMs: Long? = null,\n        var routeEnterAtMs: Long? = null,\n        var routeReturnAtMs: Long? = null,\n        var resolveStartAtMs: Long? = null,\n        var resolveEndAtMs: Long? = null,\n        var agentStartAtMs: Long? = null,\n        var agentJoinedAtMs: Long? = null,\n        var answerAtMs: Long? = null,\n        var ttsStartAtMs: Long? = null,\n        var ttsEndAtMs: Long? = null,\n        var finalAnswer: String? = null,\n        var terminalReason: String? = null,\n    )\n\n    @Volatile private var build62Diag = Build62Diag()\n    private var build62WatchdogJob: kotlinx.coroutines.Job? = null\n\n    private fun build62Reset(reason: String) {\n        build62WatchdogJob?.cancel()\n        build62Diag = Build62Diag()\n        VoiceDebugLog.append(\"BUILD62_DIAG_RESET | reason=$reason\")\n    }\n\n    private fun build62Mark(name: String, extra: String = \"\") {\n        val suffix = if (extra.isBlank()) \"\" else \" | $extra\"\n        VoiceDebugLog.append(\"BUILD62_$name$suffix\")\n    }\n\n    private fun build62StartWatchdog(transcript: String) {\n        build62WatchdogJob?.cancel()\n        build62WatchdogJob = controllerScope.launch(kotlinx.coroutines.SupervisorJob()) {\n            kotlinx.coroutines.delay(12000)\n            val d = build62Diag\n            if (d.answerAtMs != null || d.terminalReason != null) return@launch\n            val reason = when {\n                d.routeEnterAtMs == null -> \"ROUTE_NOT_ENTERED\"\n                d.resolveStartAtMs != null && d.resolveEndAtMs == null -> \"RESOLVER_STUCK\"\n                d.agentStartAtMs != null && d.agentJoinedAtMs == null -> \"AGENT_REQUEST_HANGING\"\n                d.routeReturnAtMs != null && d.agentStartAtMs == null -> \"ROUTE_RETURNED_WITHOUT_AGENT_OR_FINAL_ANSWER\"\n                d.agentJoinedAtMs != null && d.answerAtMs == null -> \"AGENT_RETURNED_WITHOUT_FINAL_ANSWER\"\n                else -> \"NO_FINAL_ANSWER_EVENT\"\n            }\n            d.terminalReason = reason\n            build62Mark(\"DIAGNOSIS\", \"reason=$reason transcript=$transcript\")\n            build62SetAssistantField(\"[DIAG] $reason\")\n            build60SpeakTrace(\"build62_diagnosis\", when(reason) {\n                \"ROUTE_RETURNED_WITHOUT_AGENT_OR_FINAL_ANSWER\" -> \"Диагностика: маршрут завершился без запуска агента и без ответа\"\n                \"RESOLVER_STUCK\" -> \"Диагностика: обработчик команды завис\"\n                \"AGENT_REQUEST_HANGING\" -> \"Диагностика: запрос к агенту не завершился\"\n                \"AGENT_RETURNED_WITHOUT_FINAL_ANSWER\" -> \"Диагностика: агент завершился без финального ответа\"\n                else -> \"Диагностика: финальный ответ ассистента не получен\"\n            })\n        }\n    }\n'''
if anchor in text:
    text = text.replace(anchor, insert, 1)

# Reset at physical/session start.
text = text.replace(
    'VoiceDebugLog.append("BUILD59_SESSION_START_ENTER',
    'build62Reset("session_start")\n        VoiceDebugLog.append("BUILD59_SESSION_START_ENTER',
    1
)

# Mark accepted utterance and independent watchdog.
text = text.replace(
    'VoiceDebugLog.append("BUILD60_UTTERANCE_ACCEPTED | decodeMs=${ev.decodeMs} text=${ev.text}")',
    'VoiceDebugLog.append("BUILD60_UTTERANCE_ACCEPTED | decodeMs=${ev.decodeMs} text=${ev.text}")\n                        build62Diag.heardAtMs = System.currentTimeMillis()\n                        build62Mark("HEARD", "text=${ev.text}")\n                        build62StartWatchdog(ev.text)',
    1
)

# Instrument existing Build60 markers by piggybacking on exact log lines.
repls = {
    'VoiceDebugLog.append("BUILD60_ROUTE_ENTER | decodeMs=$decodeMs transcript=$transcript")':
        'VoiceDebugLog.append("BUILD60_ROUTE_ENTER | decodeMs=$decodeMs transcript=$transcript")\n        build62Diag.routeEnterAtMs = System.currentTimeMillis()\n        build62Mark("ROUTE_ENTER", "transcript=$transcript")',
    'VoiceDebugLog.append("BUILD60_ROUTE_RETURNED | text=$text")':
        'VoiceDebugLog.append("BUILD60_ROUTE_RETURNED | text=$text")\n                        build62Diag.routeReturnAtMs = System.currentTimeMillis()\n                        build62Mark("ROUTE_RETURN", "text=$text")',
    'VoiceDebugLog.append("BUILD60_RESOLVE_START | transcript=$transcript")':
        'VoiceDebugLog.append("BUILD60_RESOLVE_START | transcript=$transcript")\n        build62Diag.resolveStartAtMs = System.currentTimeMillis()\n        build62Mark("RESOLVE_START", "transcript=$transcript")',
    'VoiceDebugLog.append("BUILD60_RESOLVE_END':
        'build62Diag.resolveEndAtMs = System.currentTimeMillis()\n        build62Mark("RESOLVE_END")\n        VoiceDebugLog.append("BUILD60_RESOLVE_END',
    'VoiceDebugLog.append("BUILD60_AGENT_ASK_START':
        'build62Diag.agentStartAtMs = System.currentTimeMillis()\n        build62Mark("AGENT_ASK_START")\n        VoiceDebugLog.append("BUILD60_AGENT_ASK_START',
    'VoiceDebugLog.append("BUILD60_AGENT_ASK_JOINED':
        'build62Diag.agentJoinedAtMs = System.currentTimeMillis()\n        build62Mark("AGENT_ASK_JOINED")\n        VoiceDebugLog.append("BUILD60_AGENT_ASK_JOINED',
    'VoiceDebugLog.append("BUILD60_AGENT_ANSWER | text=${result.text}")':
        'VoiceDebugLog.append("BUILD60_AGENT_ANSWER | text=${result.text}")\n        build62Diag.answerAtMs = System.currentTimeMillis()\n        build62Diag.finalAnswer = result.text\n        build62Diag.terminalReason = "ANSWER_RECEIVED"\n        build62WatchdogJob?.cancel()\n        build62Mark("FINAL_ANSWER", "text=${result.text}")',
}
for a,b in repls.items():
    if a in text:
        text = text.replace(a,b,1)

# Replace invalid stream-17 diagnostics with safe standard streams logging.
old = 'audioManager.getStreamVolume(17)'
if old in text:
    text = text.replace(old, 'audioManager.getStreamVolume(android.media.AudioManager.STREAM_MUSIC)')
text = text.replace('stream=17', 'stream=MUSIC')

vc.write_text(text, encoding='utf-8')

# Build61 panel patch already provides helper for assistant field in most chains.
# If the helper name differs, add a minimal no-op logging fallback by textual adaptation.
if 'build62SetAssistantField(' in text and 'private fun build62SetAssistantField' not in text:
    vc2 = vc.read_text(encoding='utf-8')
    fallback_anchor = 'private fun build62Mark(name: String, extra: String = "") {'
    helper = '''private fun build62SetAssistantField(value: String) {\n        VoiceDebugLog.append(\"BUILD62_ASSISTANT_FIELD | text=$value\")\n        try {\n            build61AssistantText.value = value\n        } catch (_: Throwable) {\n            // UI state name may differ; log remains authoritative.\n        }\n    }\n\n    '''
    if fallback_anchor in vc2:
        vc2 = vc2.replace(fallback_anchor, helper + fallback_anchor, 1)
        vc.write_text(vc2, encoding='utf-8')

# Panel title: clearly identify Build62 while preserving Build61 heard/assistant fields.
panel = Path('app/src/main/java/com/bydmate/app/ui/screens/settings/DiLink3VoiceDebugPanel.kt')
if panel.exists():
    p = panel.read_text(encoding='utf-8')
    p = p.replace('DiLink3 Build61 Reply Trace', 'DiLink3 Build62 AUTO DIAG')
    p = p.replace('DiLink3 Build61', 'DiLink3 Build62')
    panel.write_text(p, encoding='utf-8')

print('Build62 automatic diagnostic patch applied')
