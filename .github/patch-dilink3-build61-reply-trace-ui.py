from pathlib import Path

# Build61: fix the remaining post-ASR gap discovered by Build60.
# - watchdog waits for an ACTUAL assistant reply, not route() return;
# - persist/display separate "heard" and "assistant said" fields;
# - trace BYD Voice stream volume and raise it to a safe minimum if extremely low;
# - keep Build59 manual duplicate test buttons removed.

p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt')
s = p.read_text()

if 'import android.media.AudioManager\n' not in s:
    s = s.replace('import android.content.Context\n', 'import android.content.Context\nimport android.media.AudioManager\n', 1)

helper_anchor = '    /** Build60: diagnostic speech independent from command-routing announcements. */\n'
if helper_anchor not in s:
    raise SystemExit('Build61 Build60 helper anchor not found')
if 'private fun build61StoreHeard(' not in s:
    helper = r'''    private val build61TracePrefs by lazy {
        context.getSharedPreferences("build61_voice_trace", Context.MODE_PRIVATE)
    }
    @Volatile private var build61LastAssistantReplyMs: Long = 0L

    private fun build61StoreHeard(text: String) {
        build61TracePrefs.edit()
            .putString("last_heard", text)
            .putLong("last_heard_ms", System.currentTimeMillis())
            .apply()
        DiLink3DebugLog.log(context, "BUILD61_HEARD_FIELD", "text=$text")
    }

    private fun build61StoreAssistant(text: String, source: String) {
        if (text.isBlank()) return
        build61LastAssistantReplyMs = System.currentTimeMillis()
        build61TracePrefs.edit()
            .putString("last_assistant", text)
            .putString("last_assistant_source", source)
            .putLong("last_assistant_ms", build61LastAssistantReplyMs)
            .apply()
        DiLink3DebugLog.log(context, "BUILD61_ASSISTANT_FIELD", "source=$source text=$text")
    }

    private fun build61EnsureVoiceVolume(stage: String) {
        runCatching {
            val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val stream = 17 // BYD STREAM_BTTS, used by SherpaTtsEngine on DiLink.
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
        }.onFailure {
            DiLink3DebugLog.log(context, "BUILD61_AUDIO_VOLUME", "stage=$stage error=${it::class.java.simpleName}:${it.message}")
        }
    }

'''
    s = s.replace(helper_anchor, helper + helper_anchor, 1)

# Always inspect/repair the BYD Voice stream right before diagnostic/direct TTS.
tts_start = '        DiLink3DebugLog.log(context, "BUILD60_TTS_TRACE", "stage=$stage phase=start text=$text")\n'
if tts_start not in s:
    raise SystemExit('Build61 TTS trace start anchor not found')
s = s.replace(tts_start, '        build61EnsureVoiceVolume(stage)\n' + tts_start, 1)

# Persist recognized text and start a watchdog tied to real assistant-output timestamps.
accepted = '''                            DiLink3DebugLog.log(
                                context,
                                "BUILD60_UTTERANCE_ACCEPTED",
                                "decodeMs=$decodeMs text=${ev.text}"
                            )
'''
if accepted not in s:
    raise SystemExit('Build61 utterance accepted anchor not found')
accepted_new = accepted + '''                            val build61AcceptedAt = System.currentTimeMillis()
                            build61StoreHeard(ev.text)
                            build61TracePrefs.edit()
                                .putString("last_assistant", "Ожидание ответа…")
                                .putString("last_assistant_source", "pending")
                                .apply()
                            scope.launch {
                                delay(10_000L)
                                if (build61LastAssistantReplyMs < build61AcceptedAt && !stopRequested.get()) {
                                    DiLink3DebugLog.log(context, "BUILD61_REPLY_TIMEOUT", "afterMs=10000 text=${ev.text}")
                                    val timeoutText = "Ответ не получен"
                                    build61StoreAssistant(timeoutText, "watchdog")
                                    build60SpeakTrace("reply_timeout", timeoutText)
                                }
                            }
'''
s = s.replace(accepted, accepted_new, 1)

# A local command/error announce is a real assistant response.
announce = '        DiLink3DebugLog.log(context, "BUILD60_ANNOUNCE_ENTER", "title=$title spoken=$spoken ttsEnabled=${gate.ttsEnabled()}")\n'
if announce not in s:
    raise SystemExit('Build61 announce anchor not found')
s = s.replace(announce, announce + '        build61StoreAssistant(spoken, "announce")\n', 1)

# AgentResult.Answer is the canonical real assistant answer even when speech is streamed via queue.
agent_answer = '                DiLink3DebugLog.log(context, "BUILD60_AGENT_ANSWER", "queuedAny=$queuedAny text=${result.text} tools=${result.tools.size}")\n'
if agent_answer not in s:
    raise SystemExit('Build61 agent answer anchor not found')
s = s.replace(agent_answer, agent_answer + '                build61StoreAssistant(result.text, "agent_answer")\n', 1)

p.write_text(s)

# Build61 UI: two continuously refreshed, separate fields.
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
s = s.replace('Text("DiLink3 Build60 AUTO VOICE TRACE", style = MaterialTheme.typography.titleLarge)',
              'Text("DiLink3 Build61 REPLY TRACE", style = MaterialTheme.typography.titleLarge)', 1)
s = s.replace('"BUILD60_DEBUG_PANEL", "action=collapse"', '"BUILD61_DEBUG_PANEL", "action=collapse"', 1)
s = s.replace('"BUILD60_DEBUG_PANEL", "action=expand"', '"BUILD61_DEBUG_PANEL", "action=expand"', 1)

ui_anchor = '''            Text(
                "Старые TEST BEEP / TEST TTS / PTT / RAW MIC / RAW GigaAM кнопки удалены. Теперь после распознанной фразы приложение само говорит «Я услышал: ...», затем трассирует router -> NLU/agent -> TTS. Если за 5 секунд роутер не вернул результат, вслух прозвучит «Ответ пока не получен». После одной обычной попытки достаточно Share log.",
                style = MaterialTheme.typography.bodySmall,
            )

'''
if ui_anchor not in s:
    raise SystemExit('Build61 Build60 UI description anchor not found')
ui_new = '''            Text(
                "Build61 ждёт именно реальный ответ ассистента, а не возврат route(). Через 10 секунд без реального ответа будет записано и озвучено «Ответ не получен». Ниже отдельно сохраняются распознанная речь и фактический ответ ассистента. Также проверяется громкость BYD Voice stream.",
                style = MaterialTheme.typography.bodySmall,
            )

            val build61TracePrefs = remember { context.getSharedPreferences("build61_voice_trace", Context.MODE_PRIVATE) }
            val build61Heard = build61TracePrefs.getString("last_heard", "—") ?: "—"
            val build61Assistant = build61TracePrefs.getString("last_assistant", "—") ?: "—"
            val build61AssistantSource = build61TracePrefs.getString("last_assistant_source", "") ?: ""

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text("ЧТО УСЛЫШАЛ", style = MaterialTheme.typography.titleMedium)
                    Text(build61Heard, style = MaterialTheme.typography.bodyLarge)
                }
            }

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text("ЧТО СКАЗАЛ АССИСТЕНТ", style = MaterialTheme.typography.titleMedium)
                    Text(build61Assistant, style = MaterialTheme.typography.bodyLarge)
                    if (build61AssistantSource.isNotBlank()) {
                        Text("source: $build61AssistantSource", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }

'''
s = s.replace(ui_anchor, ui_new, 1)
p.write_text(s)

print('Build61 installed: actual-reply watchdog + heard/assistant UI + BYD voice-volume guard')
