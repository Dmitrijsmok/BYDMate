from pathlib import Path

# Build60 automatic post-ASR voice trace.
# Field finding from Build59: physical 304 -> capture -> GigaAM -> Utterance all work.
# Build60 therefore moves diagnostics strictly AFTER Utterance:
# - automatically speaks back the recognized phrase;
# - traces router / resolver / agent / TTS boundaries;
# - speaks a timeout notice if routing produces no result after 5 seconds;
# - removes Build59's manual duplicate TEST BEEP/TTS/PTT/RAW buttons.

# ---------------------------------------------------------------------------
# 1) VoiceController: automatic audible echo + post-Utterance tracing.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt')
s = p.read_text()

snapshot_anchor = '    fun build59Snapshot(): String {\n'
if snapshot_anchor not in s:
    raise SystemExit('Build60 Build59 snapshot anchor not found')
if 'suspend fun build60SpeakTrace(' not in s:
    helper = r'''    /** Build60: diagnostic speech independent from command-routing announcements. */
    private suspend fun build60SpeakTrace(stage: String, text: String): Boolean {
        if (text.isBlank()) {
            DiLink3DebugLog.log(context, "BUILD60_TTS_TRACE", "stage=$stage phase=skip reason=blank")
            return false
        }
        DiLink3DebugLog.log(context, "BUILD60_TTS_TRACE", "stage=$stage phase=start text=$text")
        val result = runCatching { ttsEngine.speak(text) }
        val ok = result.getOrDefault(false)
        if (ok) {
            echoFilter.noteSpoken(text)
            lastSpeakingSeenMs = System.currentTimeMillis()
        }
        DiLink3DebugLog.log(
            context,
            "BUILD60_TTS_TRACE",
            "stage=$stage phase=end success=$ok error=${result.exceptionOrNull()?.let { it::class.java.simpleName + ":" + it.message }}"
        )
        return ok
    }

'''
    s = s.replace(snapshot_anchor, helper + snapshot_anchor, 1)

# Automatic audible acknowledgement immediately after the recognizer produced final text.
utterance_marker = '''                            DiLink3DebugLog.log(
                                context,
                                "BUILD59_GIGAAM_UTTERANCE",
                                "decodeMs=$decodeMs processingUtterance=$processingUtterance text=${ev.text}"
                            )
'''
if utterance_marker not in s:
    raise SystemExit('Build60 Build59 utterance marker anchor not found')
utterance_new = utterance_marker + '''                            DiLink3DebugLog.log(
                                context,
                                "BUILD60_UTTERANCE_ACCEPTED",
                                "decodeMs=$decodeMs text=${ev.text}"
                            )
                            if (ev.text.isNotBlank()) {
                                build60SpeakTrace("heard_echo", "Я услышал: ${ev.text}")
                            }
'''
s = s.replace(utterance_marker, utterance_new, 1)

# Trace the routing coroutine and add an audible 5-second watchdog.
route_job_old = '''                            processingUtterance = true
                            val job = launch(start = CoroutineStart.LAZY) {
                                runCatching { updateListeningOverlay(context.getString(R.string.voice_thinking)) }
                                try {
                                    routeUtterance(ev.text, decodeMs)
                                } catch (t: Throwable) {
'''
route_job_new = '''                            processingUtterance = true
                            val build60RouteFinished = AtomicBoolean(false)
                            DiLink3DebugLog.log(context, "BUILD60_ROUTE_JOB_CREATED", "text=${ev.text}")
                            val job = launch(start = CoroutineStart.LAZY) {
                                DiLink3DebugLog.log(context, "BUILD60_ROUTE_JOB_START", "text=${ev.text}")
                                runCatching { updateListeningOverlay(context.getString(R.string.voice_thinking)) }
                                val build60Watchdog = launch {
                                    delay(5_000L)
                                    if (!build60RouteFinished.get() && !stopRequested.get()) {
                                        DiLink3DebugLog.log(context, "BUILD60_ROUTE_TIMEOUT", "afterMs=5000 text=${ev.text}")
                                        build60SpeakTrace("route_timeout", "Ответ пока не получен")
                                    }
                                }
                                try {
                                    routeUtterance(ev.text, decodeMs)
                                    DiLink3DebugLog.log(context, "BUILD60_ROUTE_RETURNED", "text=${ev.text}")
                                } catch (t: Throwable) {
                                    DiLink3DebugLog.log(context, "BUILD60_ROUTE_EXCEPTION", "type=${t::class.java.simpleName} message=${t.message}")
'''
if route_job_old not in s:
    raise SystemExit('Build60 routing job anchor not found')
s = s.replace(route_job_old, route_job_new, 1)

route_finally_old = '''                                } finally {
                                    routingJob = null
                                    processingUtterance = false
'''
route_finally_new = '''                                } finally {
                                    build60RouteFinished.set(true)
                                    build60Watchdog.cancel()
                                    DiLink3DebugLog.log(context, "BUILD60_ROUTE_JOB_END", "text=${ev.text}")
                                    routingJob = null
                                    processingUtterance = false
'''
if route_finally_old not in s:
    raise SystemExit('Build60 routing finally anchor not found')
s = s.replace(route_finally_old, route_finally_new, 1)

# Trace routeUtterance itself and the NLU -> agent split.
route_enter_old = '''    private suspend fun routeUtterance(transcript: String, decodeMs: Long) {
        // Orb dialog: show "Ты: <phrase>" (clearing any prior answer) and cancel a pending clear so a
'''
route_enter_new = '''    private suspend fun routeUtterance(transcript: String, decodeMs: Long) {
        DiLink3DebugLog.log(context, "BUILD60_ROUTE_ENTER", "decodeMs=$decodeMs transcript=$transcript")
        // Orb dialog: show "Ты: <phrase>" (clearing any prior answer) and cancel a pending clear so a
'''
if route_enter_old not in s:
    raise SystemExit('Build60 routeUtterance entry anchor not found')
s = s.replace(route_enter_old, route_enter_new, 1)

resolve_old = '''        val followUp = runCatching { agentOrchestrator.expectsFollowUp() }.getOrDefault(false)
        val res = if (followUp) null else resolve(command, gigaAmRecognitionLang())
        _state.value = VoiceUiState.Thinking
        if (res != null) apply(res, command, decodeMs) else agentFallback(command, decodeMs)
'''
resolve_new = '''        val followUp = runCatching { agentOrchestrator.expectsFollowUp() }.getOrDefault(false)
        DiLink3DebugLog.log(context, "BUILD60_RESOLVE_START", "followUp=$followUp command=$command")
        val res = if (followUp) null else resolve(command, gigaAmRecognitionLang())
        DiLink3DebugLog.log(
            context,
            "BUILD60_RESOLVE_END",
            "followUp=$followUp result=${res?.let { it::class.java.simpleName } ?: "AGENT_FALLBACK"} command=$command"
        )
        _state.value = VoiceUiState.Thinking
        if (res != null) {
            DiLink3DebugLog.log(context, "BUILD60_LOCAL_ROUTE_ENTER", "type=${res::class.java.simpleName} command=$command")
            apply(res, command, decodeMs)
            DiLink3DebugLog.log(context, "BUILD60_LOCAL_ROUTE_END", "command=$command")
        } else {
            DiLink3DebugLog.log(context, "BUILD60_AGENT_ROUTE_ENTER", "command=$command")
            agentFallback(command, decodeMs)
            DiLink3DebugLog.log(context, "BUILD60_AGENT_ROUTE_END", "command=$command")
        }
        DiLink3DebugLog.log(context, "BUILD60_ROUTE_EXIT", "command=$command")
'''
if resolve_old not in s:
    raise SystemExit('Build60 resolver split anchor not found')
s = s.replace(resolve_old, resolve_new, 1)

# Trace announce and its actual TTS call for local command/error outcomes.
announce_enter_old = '''    private suspend fun announce(title: String, overlay: String, spoken: String) {
        // Hard stop gate: never start a new announcement after the orb went off — the callers'
'''
announce_enter_new = '''    private suspend fun announce(title: String, overlay: String, spoken: String) {
        DiLink3DebugLog.log(context, "BUILD60_ANNOUNCE_ENTER", "title=$title spoken=$spoken ttsEnabled=${gate.ttsEnabled()}")
        // Hard stop gate: never start a new announcement after the orb went off — the callers'
'''
if announce_enter_old not in s:
    raise SystemExit('Build60 announce entry anchor not found')
s = s.replace(announce_enter_old, announce_enter_new, 1)

announce_tts_old = '''            val phrase = agentIdentity().persona.spokenPhrase(spoken)
            if (runCatching { ttsEngine.speak(phrase) }.getOrDefault(false)) {
                echoFilter.noteSpoken(phrase)
                lastSpeakingSeenMs = System.currentTimeMillis()
            }
'''
announce_tts_new = '''            val phrase = agentIdentity().persona.spokenPhrase(spoken)
            val build60AnnounceSpoken = build60SpeakTrace("announce", phrase)
            DiLink3DebugLog.log(context, "BUILD60_ANNOUNCE_TTS_RESULT", "success=$build60AnnounceSpoken phrase=$phrase")
'''
if announce_tts_old not in s:
    raise SystemExit('Build60 announce TTS anchor not found')
s = s.replace(announce_tts_old, announce_tts_new, 1)

# Trace the agent call. If a final answer was not streamed to the queue, use the Build60
# direct TTS helper so success/failure is explicit in the exported log.
agent_enter_old = '''    private suspend fun agentFallback(transcript: String, decodeMs: Long? = null) {
        if (transcript.isBlank()) {
'''
agent_enter_new = '''    private suspend fun agentFallback(transcript: String, decodeMs: Long? = null) {
        DiLink3DebugLog.log(context, "BUILD60_AGENT_FALLBACK_ENTER", "transcript=$transcript ttsEnabled=${gate.ttsEnabled()}")
        if (transcript.isBlank()) {
'''
if agent_enter_old not in s:
    raise SystemExit('Build60 agent entry anchor not found')
s = s.replace(agent_enter_old, agent_enter_new, 1)

ask_old = '''            cancellableAskJob = askJob
            askJob.start()
            try {
                askJob.join()
            } finally {
                cancellableAskJob = null
            }
'''
ask_new = '''            cancellableAskJob = askJob
            DiLink3DebugLog.log(context, "BUILD60_AGENT_ASK_START", "transcript=$transcript queueReady=${queue != null}")
            askJob.start()
            try {
                askJob.join()
                DiLink3DebugLog.log(context, "BUILD60_AGENT_ASK_JOINED", "transcript=$transcript resultType=${r?.let { it::class.java.simpleName }} queuedAny=$queuedAny")
            } finally {
                cancellableAskJob = null
            }
'''
if ask_old not in s:
    raise SystemExit('Build60 agent ask anchor not found')
s = s.replace(ask_old, ask_new, 1)

agent_answer_old = '''            is AgentResult.Answer -> {
                // Gated on queuedAny (an actual successful enqueue), not "sentences arrived": the
'''
agent_answer_new = '''            is AgentResult.Answer -> {
                DiLink3DebugLog.log(context, "BUILD60_AGENT_ANSWER", "queuedAny=$queuedAny text=${result.text} tools=${result.tools.size}")
                // Gated on queuedAny (an actual successful enqueue), not "sentences arrived": the
'''
if agent_answer_old not in s:
    raise SystemExit('Build60 agent answer anchor not found')
s = s.replace(agent_answer_old, agent_answer_new, 1)

agent_tts_old = '''                if (!queuedAny && gate.ttsEnabled()) {
                    // See announce() for why this is stamped at call time, not only per-frame,
                    // and only when speak() actually enqueued playback.
                    if (runCatching { ttsEngine.speak(result.text) }.getOrDefault(false)) {
                        echoFilter.noteSpoken(result.text)
                        lastSpeakingSeenMs = System.currentTimeMillis()
                    }
                }
'''
agent_tts_new = '''                if (!queuedAny && gate.ttsEnabled()) {
                    val build60AgentSpoken = build60SpeakTrace("agent_answer", result.text)
                    DiLink3DebugLog.log(context, "BUILD60_AGENT_TTS_RESULT", "success=$build60AgentSpoken")
                } else {
                    DiLink3DebugLog.log(context, "BUILD60_AGENT_TTS_STREAM", "queuedAny=$queuedAny ttsEnabled=${gate.ttsEnabled()}")
                }
'''
if agent_tts_old not in s:
    raise SystemExit('Build60 agent TTS anchor not found')
s = s.replace(agent_tts_old, agent_tts_new, 1)

p.write_text(s)

# ---------------------------------------------------------------------------
# 2) Diagnostic panel: Build60 has NEW automatic logic, not Build59's test buttons.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

# Remove hidden Build59 probe state/functions as well as their visible controls.
probe_start = s.find('    var build59MicProbeJob by remember { mutableStateOf<Job?>(null) }')
collapse_anchor = '    if (!build58PanelExpanded) {\n'
if probe_start >= 0:
    collapse_pos = s.find(collapse_anchor, probe_start)
    if collapse_pos < 0:
        raise SystemExit('Build60 collapse anchor after Build59 probes not found')
    s = s[:probe_start] + s[collapse_pos:]

# Derive the exact Build59 injected controls from the Build59 patch file, then replace them.
p59 = Path('.github/patch-dilink3-build59-diagnostic-lab.py').read_text()
controls_token = "controls = r'''"
controls_start = p59.find(controls_token)
controls_end_token = "\n'''\ns = s.replace(title_anchor, controls, 1)"
controls_end = p59.find(controls_end_token, controls_start)
if controls_start < 0 or controls_end < 0:
    raise SystemExit('Build60 could not derive Build59 controls')
old_controls = p59[controls_start + len(controls_token):controls_end]
if old_controls not in s:
    raise SystemExit('Build60 exact Build59 control block not found in patched panel')
new_controls = '''            Text("DiLink3 Build60 AUTO VOICE TRACE", style = MaterialTheme.typography.titleLarge)

            Button(
                onClick = {
                    build58PanelExpanded = false
                    DiLink3DebugLog.log(context, "BUILD60_DEBUG_PANEL", "action=collapse")
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("MINIMIZE DBG") }

            Text("BUILD60: АВТОМАТИЧЕСКАЯ ДИАГНОСТИКА ПОСЛЕ РАСПОЗНАВАНИЯ", style = MaterialTheme.typography.titleMedium)
            Text(
                "Старые TEST BEEP / TEST TTS / PTT / RAW MIC / RAW GigaAM кнопки удалены. Теперь после распознанной фразы приложение само говорит «Я услышал: ...», затем трассирует router -> NLU/agent -> TTS. Если за 5 секунд роутер не вернул результат, вслух прозвучит «Ответ пока не получен». После одной обычной попытки достаточно Share log.",
                style = MaterialTheme.typography.bodySmall,
            )

'''
s = s.replace(old_controls, new_controls, 1)
s = s.replace(
    'DiLink3DebugLog.log(context, "BUILD59_DEBUG_PANEL", "action=expand")',
    'DiLink3DebugLog.log(context, "BUILD60_DEBUG_PANEL", "action=expand")',
    1,
)

p.write_text(s)
print('Build60 installed: automatic heard-echo + post-Utterance router/agent/TTS trace; Build59 manual test buttons removed')
