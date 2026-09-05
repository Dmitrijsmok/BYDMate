#!/usr/bin/env python3
from pathlib import Path

p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt')
s = p.read_text()

# Build62 runs after Build61. It intentionally diagnoses the REAL post-ASR pipeline
# without depending on routeJob lifetime. Results are stored in the same prefs that
# power Build61's separate HEARD / ASSISTANT cards.
helper_anchor = '    /** Build60: diagnostic speech independent from command-routing announcements. */\n'
if helper_anchor not in s:
    raise SystemExit('Build62: Build60 helper anchor not found')

helper = r'''    // BUILD62: independent automatic post-ASR diagnostic state.
    private val build62DiagScope = kotlinx.coroutines.CoroutineScope(
        kotlinx.coroutines.SupervisorJob() + kotlinx.coroutines.Dispatchers.Default
    )
    @Volatile private var build62SessionId: Long = 0L
    @Volatile private var build62RouteEntered = false
    @Volatile private var build62RouteReturned = false
    @Volatile private var build62ResolveStarted = false
    @Volatile private var build62ResolveEnded = false
    @Volatile private var build62AgentRouteEntered = false
    @Volatile private var build62AgentAskStarted = false
    @Volatile private var build62AgentAskJoined = false
    @Volatile private var build62RealAnswerReceived = false

    private fun build62Log(stage: String, details: String = "") {
        DiLink3DebugLog.log(context, "BUILD62_$stage", details)
    }

    private fun build62ResetForUtterance(text: String): Long {
        val id = System.currentTimeMillis()
        build62SessionId = id
        build62RouteEntered = false
        build62RouteReturned = false
        build62ResolveStarted = false
        build62ResolveEnded = false
        build62AgentRouteEntered = false
        build62AgentAskStarted = false
        build62AgentAskJoined = false
        build62RealAnswerReceived = false
        build62Log("SESSION_START", "id=$id text=$text")
        return id
    }

    private fun build62RecordRealAssistant(text: String, source: String) {
        // Build61's own timeout is diagnostic text, not an actual assistant answer.
        if (source == "watchdog" || source == "build62_diagnosis") return
        build62RealAnswerReceived = true
        build62Log("REAL_ANSWER", "source=$source text=$text")
    }

    private fun build62DiagnosisText(reason: String): String = when (reason) {
        "ROUTE_NEVER_ENTERED" -> "Диагностика: распознавание завершилось, но маршрутизатор не запустился"
        "ROUTE_RETURNED_BEFORE_RESOLVER" -> "Диагностика: маршрутизатор завершился до запуска обработчика команды"
        "RESOLVER_STUCK" -> "Диагностика: обработчик команды завис и не вернул результат"
        "RESOLVER_RETURNED_BUT_NO_AGENT_ROUTE" -> "Диагностика: обработчик завершился, но ответ и агент не были запущены"
        "AGENT_ROUTE_WITHOUT_REQUEST" -> "Диагностика: переход к агенту произошёл, но запрос к агенту не запустился"
        "AGENT_REQUEST_HANGING" -> "Диагностика: запрос к агенту запущен, но не завершился"
        "AGENT_JOINED_WITHOUT_FINAL_ANSWER" -> "Диагностика: агент завершил запрос, но финальный ответ не был создан"
        "ROUTE_RETURNED_WITHOUT_FINAL_ANSWER" -> "Диагностика: маршрут завершился без финального ответа ассистента"
        else -> "Диагностика: финальный ответ ассистента не получен"
    }

    private fun build62StartIndependentWatchdog(sessionId: Long, transcript: String) {
        build62DiagScope.launch {
            kotlinx.coroutines.delay(12_000L)
            if (build62SessionId != sessionId || build62RealAnswerReceived) return@launch
            val reason = when {
                !build62RouteEntered -> "ROUTE_NEVER_ENTERED"
                build62RouteReturned && !build62ResolveStarted -> "ROUTE_RETURNED_BEFORE_RESOLVER"
                build62ResolveStarted && !build62ResolveEnded -> "RESOLVER_STUCK"
                build62ResolveEnded && !build62AgentRouteEntered && !build62RealAnswerReceived -> "RESOLVER_RETURNED_BUT_NO_AGENT_ROUTE"
                build62AgentRouteEntered && !build62AgentAskStarted -> "AGENT_ROUTE_WITHOUT_REQUEST"
                build62AgentAskStarted && !build62AgentAskJoined -> "AGENT_REQUEST_HANGING"
                build62AgentAskJoined && !build62RealAnswerReceived -> "AGENT_JOINED_WITHOUT_FINAL_ANSWER"
                build62RouteReturned && !build62RealAnswerReceived -> "ROUTE_RETURNED_WITHOUT_FINAL_ANSWER"
                else -> "NO_FINAL_ANSWER_EVENT"
            }
            val spoken = build62DiagnosisText(reason)
            build62Log(
                "DIAGNOSIS",
                "id=$sessionId reason=$reason routeEntered=$build62RouteEntered routeReturned=$build62RouteReturned " +
                    "resolveStarted=$build62ResolveStarted resolveEnded=$build62ResolveEnded agentRoute=$build62AgentRouteEntered " +
                    "agentAskStarted=$build62AgentAskStarted agentAskJoined=$build62AgentAskJoined transcript=$transcript"
            )
            build61TracePrefs.edit()
                .putString("last_assistant", "[DIAG] $reason")
                .putString("last_assistant_source", "build62_diagnosis")
                .putLong("last_assistant_ms", System.currentTimeMillis())
                .apply()
            build60SpeakTrace("build62_diagnosis", spoken)
        }
    }

'''
if 'private val build62DiagScope' not in s:
    s = s.replace(helper_anchor, helper + helper_anchor, 1)

# Use safe standard Android stream diagnostics. BYD private stream type 17 throws on this unit.
old_volume = r'''            val stream = 17 // BYD STREAM_BTTS, used by SherpaTtsEngine on DiLink.
            val before = am.getStreamVolume(stream)
            val max = am.getStreamMaxVolume(stream).coerceAtLeast(1)
            val minTarget = (max * 0.60f).toInt().coerceAtLeast(1)
            var after = before
            var adjusted = false
            if (before < minTarget) {
                runCatching { am.setStreamVolume(stream, minTarget, 0) }
                after = runCatching { am.getStreamVolume(stream) }.getOrDefault(before)
                adjusted = after != before
            }
            val music = runCatching { am.getStreamVolume(AudioManager.STREAM_MUSIC) }.getOrDefault(-1)
            val musicMax = runCatching { am.getStreamMaxVolume(AudioManager.STREAM_MUSIC) }.getOrDefault(-1)
            DiLink3DebugLog.log(
                context,
                "BUILD61_AUDIO_VOLUME",
                "stage=$stage bydStream17Before=$before bydStream17After=$after bydStream17Max=$max adjusted=$adjusted music=$music/$musicMax mode=${am.mode}"
            )
'''
new_volume = r'''            val music = runCatching { am.getStreamVolume(AudioManager.STREAM_MUSIC) }.getOrDefault(-1)
            val musicMax = runCatching { am.getStreamMaxVolume(AudioManager.STREAM_MUSIC) }.getOrDefault(-1)
            val voiceCall = runCatching { am.getStreamVolume(AudioManager.STREAM_VOICE_CALL) }.getOrDefault(-1)
            val voiceCallMax = runCatching { am.getStreamMaxVolume(AudioManager.STREAM_VOICE_CALL) }.getOrDefault(-1)
            DiLink3DebugLog.log(
                context,
                "BUILD62_AUDIO_STATE",
                "stage=$stage music=$music/$musicMax voiceCall=$voiceCall/$voiceCallMax mode=${am.mode}"
            )
'''
if old_volume not in s:
    raise SystemExit('Build62: Build61 stream17 block not found')
s = s.replace(old_volume, new_volume, 1)

# Any actual announce/agent answer stored by Build61 is also the terminal event for Build62.
store_anchor = '        DiLink3DebugLog.log(context, "BUILD61_ASSISTANT_FIELD", "source=$source text=$text")\n'
if store_anchor not in s:
    raise SystemExit('Build62: Build61 assistant-store anchor not found')
s = s.replace(store_anchor, store_anchor + '        build62RecordRealAssistant(text, source)\n', 1)

# Start a fresh diagnosis after ASR acceptance. This scope is independent from routeJob/session capture.
heard_anchor = '                            build61StoreHeard(ev.text)\n'
if heard_anchor not in s:
    raise SystemExit('Build62: Build61 heard anchor not found')
s = s.replace(
    heard_anchor,
    heard_anchor + '''                            val build62Id = build62ResetForUtterance(ev.text)
                            build62StartIndependentWatchdog(build62Id, ev.text)
''',
    1,
)

# Trace the exact boundaries that distinguish the failure classes.
route_enter = '        DiLink3DebugLog.log(context, "BUILD60_ROUTE_ENTER", "decodeMs=$decodeMs transcript=$transcript")\n'
if route_enter not in s: raise SystemExit('Build62: route enter anchor not found')
s = s.replace(route_enter, route_enter + '        build62RouteEntered = true\n        build62Log("ROUTE_ENTER", "transcript=$transcript")\n', 1)

route_return = '                                    DiLink3DebugLog.log(context, "BUILD60_ROUTE_RETURNED", "text=${ev.text}")\n'
if route_return not in s: raise SystemExit('Build62: route return anchor not found')
s = s.replace(route_return, route_return + '                                    build62RouteReturned = true\n                                    build62Log("ROUTE_RETURN", "text=${ev.text}")\n', 1)

resolve_start = '        DiLink3DebugLog.log(context, "BUILD60_RESOLVE_START", "followUp=$followUp command=$command")\n'
if resolve_start not in s: raise SystemExit('Build62: resolver start anchor not found')
s = s.replace(resolve_start, resolve_start + '        build62ResolveStarted = true\n        build62Log("RESOLVE_START", "followUp=$followUp command=$command")\n', 1)

resolve_end_marker = '''        DiLink3DebugLog.log(
            context,
            "BUILD60_RESOLVE_END",
            "followUp=$followUp result=${res?.let { it::class.java.simpleName } ?: "AGENT_FALLBACK"} command=$command"
        )
'''
if resolve_end_marker not in s: raise SystemExit('Build62: resolver end anchor not found')
s = s.replace(resolve_end_marker, resolve_end_marker + '        build62ResolveEnded = true\n        build62Log("RESOLVE_END", "result=${res?.let { it::class.java.simpleName } ?: "AGENT_FALLBACK"}")\n', 1)

agent_route = '            DiLink3DebugLog.log(context, "BUILD60_AGENT_ROUTE_ENTER", "command=$command")\n'
if agent_route not in s: raise SystemExit('Build62: agent route anchor not found')
s = s.replace(agent_route, agent_route + '            build62AgentRouteEntered = true\n            build62Log("AGENT_ROUTE_ENTER", "command=$command")\n', 1)

agent_ask = '            DiLink3DebugLog.log(context, "BUILD60_AGENT_ASK_START", "transcript=$transcript queueReady=${queue != null}")\n'
if agent_ask not in s: raise SystemExit('Build62: agent ask start anchor not found')
s = s.replace(agent_ask, agent_ask + '            build62AgentAskStarted = true\n            build62Log("AGENT_ASK_START", "transcript=$transcript")\n', 1)

agent_join = '                DiLink3DebugLog.log(context, "BUILD60_AGENT_ASK_JOINED", "transcript=$transcript resultType=${r?.let { it::class.java.simpleName }} queuedAny=$queuedAny")\n'
if agent_join not in s: raise SystemExit('Build62: agent ask joined anchor not found')
s = s.replace(agent_join, agent_join + '                build62AgentAskJoined = true\n                build62Log("AGENT_ASK_JOINED", "resultType=${r?.let { it::class.java.simpleName }} queuedAny=$queuedAny")\n', 1)

p.write_text(s)

# Keep Build61's two separate fields, relabel the panel for Build62.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
if 'DiLink3 Build61 REPLY TRACE' not in s:
    raise SystemExit('Build62: Build61 panel title not found')
s = s.replace('DiLink3 Build61 REPLY TRACE', 'DiLink3 Build62 AUTO DIAG', 1)
s = s.replace(
    'Build61 ждёт именно реальный ответ ассистента, а не возврат route(). Через 10 секунд без реального ответа будет записано и озвучено «Ответ не получен». Ниже отдельно сохраняются распознанная речь и фактический ответ ассистента. Также проверяется громкость BYD Voice stream.',
    'Build62 автоматически трассирует каждый этап после распознавания и через 12 секунд без реального ответа сам определяет класс сбоя. Причина записывается в поле ответа как [DIAG] и в лог BUILD62_DIAGNOSIS, а также произносится вслух. Поля «Что услышал» и «Что сказал ассистент» сохранены.',
    1,
)
p.write_text(s)

print('Build62 installed: independent stage-by-stage diagnosis + spoken reason + safe audio-state trace')
