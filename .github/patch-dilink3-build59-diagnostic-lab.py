from pathlib import Path

# Build59 field diagnostic lab.
# Goals:
# - audible confirmation the physical 304 mic DOWN edge was accepted by BYDMate;
# - high-signal checkpoints through PTT -> session -> PCM -> GigaAM -> utterance;
# - independent in-app tests (beep, TTS, PTT, raw microphone, raw GigaAM, snapshot);
# - expanded DBG panel can always be collapsed again without reinstalling.

# ---------------------------------------------------------------------------
# 1) VoiceEarcon: a short, distinct physical-button acknowledgement.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceEarcon.kt')
s = p.read_text()
anchor = '    fun ok() = beep(ToneGenerator.TONE_PROP_ACK, 150)\n'
if anchor not in s:
    raise SystemExit('Build59 VoiceEarcon ok anchor not found')
if 'fun press()' not in s:
    s = s.replace(
        anchor,
        '    /** Build59: immediate short cue that the physical mic DOWN edge reached BYDMate. */\n'
        '    fun press() = beep(ToneGenerator.TONE_PROP_BEEP, 80)\n' + anchor,
        1,
    )
p.write_text(s)

# ---------------------------------------------------------------------------
# 2) VoiceController: hardware ACK, independent TTS test and pipeline checkpoints.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt')
s = p.read_text()

import_anchor = 'import com.bydmate.app.ui.overlay.ListeningOverlay\n'
if import_anchor not in s:
    raise SystemExit('Build59 VoiceController import anchor not found')
if 'import com.bydmate.app.ui.diagnostics.DiLink3DebugLog\n' not in s:
    s = s.replace(
        import_anchor,
        'import com.bydmate.app.ui.diagnostics.DiLink3DebugLog\n' + import_anchor,
        1,
    )

method_anchor = '    fun sessionActive(): Boolean = listening.value || busy.get()\n'
if method_anchor not in s:
    raise SystemExit('Build59 sessionActive anchor not found')
if 'fun build59HardwareAck(' not in s:
    methods = r'''

    /** Build59 field seam: confirms the physical steering-wheel mic edge before ASR is touched. */
    fun build59HardwareAck(source: String) {
        earcon.press()
        DiLink3DebugLog.log(
            context,
            "BUILD59_PTT_HARDWARE_ACK",
            "source=$source gateEnabled=${gate.isEnabled()} listening=${_listening.value} busy=${busy.get()} asrReady=${continuousAsr.isReady()}"
        )
    }

    /** Independent TTS diagnostic. It deliberately bypasses the voice-command TTS toggle. */
    fun build59TestTts() {
        scope.launch {
            val phrase = "Проверка голоса BYD Mate"
            DiLink3DebugLog.log(context, "BUILD59_TTS_TEST", "phase=start text=$phrase")
            val result = runCatching { ttsEngine.speak(phrase) }
            DiLink3DebugLog.log(
                context,
                "BUILD59_TTS_TEST",
                "phase=end success=${result.getOrDefault(false)} error=${result.exceptionOrNull()?.let { it::class.java.simpleName + ":" + it.message }}"
            )
        }
    }

    /** Compact state snapshot for the diagnostic panel and exported field log. */
    fun build59Snapshot(): String {
        val text = "gateEnabled=${gate.isEnabled()} listening=${_listening.value} busy=${busy.get()} " +
            "asrReady=${continuousAsr.isReady()} uiLang=${currentLang()} recognitionLang=${gigaAmRecognitionLang()} " +
            "ttsEnabled=${gate.ttsEnabled()} sessionJobActive=${sessionJob?.isActive == true} routingJobActive=${routingJob?.isActive == true}"
        DiLink3DebugLog.log(context, "BUILD59_VOICE_SNAPSHOT", text)
        return text
    }
'''
    s = s.replace(method_anchor, method_anchor + methods, 1)

old_ptt_gate = '''    fun onPttPressed() {
        if (!gate.isEnabled()) return
'''
new_ptt_gate = '''    fun onPttPressed() {
        val build59GateEnabled = gate.isEnabled()
        DiLink3DebugLog.log(
            context,
            "BUILD59_PTT_ENTER",
            "gateEnabled=$build59GateEnabled listening=${_listening.value} busy=${busy.get()} asrReady=${continuousAsr.isReady()} uiLang=${currentLang()}"
        )
        if (!build59GateEnabled) {
            DiLink3DebugLog.log(context, "BUILD59_PTT_REJECTED", "reason=voice_gate_disabled")
            return
        }
'''
if old_ptt_gate not in s:
    raise SystemExit('Build59 onPttPressed gate anchor not found')
s = s.replace(old_ptt_gate, new_ptt_gate, 1)

old_stop = '''        if (_listening.value) {
            stopContinuousSession()
            return
        }
'''
new_stop = '''        if (_listening.value) {
            DiLink3DebugLog.log(context, "BUILD59_PTT_STOP_REQUEST", "reason=already_listening")
            stopContinuousSession()
            return
        }
'''
if old_stop not in s:
    raise SystemExit('Build59 PTT stop anchor not found')
s = s.replace(old_stop, new_stop, 1)

ready_anchor = '''        if (continuousAsr.isReady()) {
            Log.i(TAG, "BUILD58_GIGAAM_FORCED_RU uiLang=${currentLang()} recognitionLang=${gigaAmRecognitionLang()}")
            startContinuousSession()
'''
ready_new = '''        if (continuousAsr.isReady()) {
            Log.i(TAG, "BUILD58_GIGAAM_FORCED_RU uiLang=${currentLang()} recognitionLang=${gigaAmRecognitionLang()}")
            DiLink3DebugLog.log(context, "BUILD59_PTT_START_REQUEST", "asrReady=true recognitionLang=${gigaAmRecognitionLang()}")
            startContinuousSession()
'''
if ready_anchor not in s:
    raise SystemExit('Build59 Build58 ready anchor not found')
s = s.replace(ready_anchor, ready_new, 1)

start_anchor = '''    private fun startContinuousSession() {
        if (!busy.compareAndSet(false, true)) return
'''
start_new = '''    private fun startContinuousSession() {
        DiLink3DebugLog.log(context, "BUILD59_SESSION_START_ENTER", "busyBefore=${busy.get()} listeningBefore=${_listening.value}")
        if (!busy.compareAndSet(false, true)) {
            DiLink3DebugLog.log(context, "BUILD59_SESSION_START_REJECTED", "reason=busy")
            return
        }
'''
if start_anchor not in s:
    raise SystemExit('Build59 session start anchor not found')
s = s.replace(start_anchor, start_new, 1)

listening_anchor = '''        _state.value = VoiceUiState.Listening
        _listening.value = true
        earcon.ok()
'''
listening_new = '''        _state.value = VoiceUiState.Listening
        _listening.value = true
        DiLink3DebugLog.log(context, "BUILD59_SESSION_LISTENING", "state=Listening busy=${busy.get()}")
        earcon.ok()
'''
if listening_anchor not in s:
    raise SystemExit('Build59 listening-state anchor not found')
s = s.replace(listening_anchor, listening_new, 1)

capture_anchor = '''            try {
                val pcm = audioCapture.captureSession(maxMs = Long.MAX_VALUE) // Wave P: no session cap; silence auto-stop below is the only auto-exit
                    .filter {
'''
capture_new = '''            try {
                DiLink3DebugLog.log(context, "BUILD59_CAPTURE_OPEN", "maxMs=Long.MAX_VALUE")
                var build59FirstPcm = true
                val pcm = audioCapture.captureSession(maxMs = Long.MAX_VALUE) // Wave P: no session cap; silence auto-stop below is the only auto-exit
                    .filter {
                        if (build59FirstPcm) {
                            build59FirstPcm = false
                            DiLink3DebugLog.log(context, "BUILD59_PCM_FIRST_FRAME", "samples=${it.size}")
                        }
'''
if capture_anchor not in s:
    raise SystemExit('Build59 capture anchor not found')
s = s.replace(capture_anchor, capture_new, 1)

speech_anchor = '''                        is ContinuousAsrEvent.SpeechStart -> {
                            lastEventMs = System.currentTimeMillis()
'''
speech_new = '''                        is ContinuousAsrEvent.SpeechStart -> {
                            DiLink3DebugLog.log(context, "BUILD59_GIGAAM_SPEECH_START", "processingUtterance=$processingUtterance")
                            lastEventMs = System.currentTimeMillis()
'''
if speech_anchor not in s:
    raise SystemExit('Build59 SpeechStart anchor not found')
s = s.replace(speech_anchor, speech_new, 1)

utterance_anchor = '''                        is ContinuousAsrEvent.Utterance -> {
                            val decodeMs = System.currentTimeMillis() - lastEventMs
'''
utterance_new = '''                        is ContinuousAsrEvent.Utterance -> {
                            val decodeMs = System.currentTimeMillis() - lastEventMs
                            DiLink3DebugLog.log(
                                context,
                                "BUILD59_GIGAAM_UTTERANCE",
                                "decodeMs=$decodeMs processingUtterance=$processingUtterance text=${ev.text}"
                            )
'''
if utterance_anchor not in s:
    raise SystemExit('Build59 Utterance anchor not found')
s = s.replace(utterance_anchor, utterance_new, 1)

failure_anchor = '                Log.w(TAG, "Continuous session failed: ${t.message}")\n'
if failure_anchor not in s:
    raise SystemExit('Build59 session failure anchor not found')
s = s.replace(
    failure_anchor,
    failure_anchor + '                DiLink3DebugLog.log(context, "BUILD59_SESSION_FAILURE", "error=${t::class.java.simpleName}:${t.message}")\n',
    1,
)

finally_anchor = '''                sessionJob = null
                busy.set(false)
'''
finally_new = '''                sessionJob = null
                busy.set(false)
                DiLink3DebugLog.log(context, "BUILD59_SESSION_END", "listening=${_listening.value} busy=${busy.get()} stopRequested=${stopRequested.get()}")
'''
if finally_anchor not in s:
    raise SystemExit('Build59 session-finally anchor not found')
s = s.replace(finally_anchor, finally_new, 1)

p.write_text(s)

# ---------------------------------------------------------------------------
# 3) SteeringWheelKeyService: play ACK on the actual physical 304 DOWN edge.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()
physical_anchor = '''        if (build56PhysicalMic304) {
            DiLink3DebugLog.log(
'''
physical_new = '''        if (build56PhysicalMic304) {
            if (isDown && voiceEnabled) {
                entryPoint().voiceController().build59HardwareAck(
                    "physical304 scanCode=${event.scanCode} deviceId=${event.deviceId} source=${event.source}"
                )
            }
            DiLink3DebugLog.log(
'''
if physical_anchor not in s:
    raise SystemExit('Build59 physical 304 anchor not found')
s = s.replace(physical_anchor, physical_new, 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# 4) Diagnostic panel: re-collapse control + independent field-test modules.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

launch_import = 'import kotlinx.coroutines.launch\n'
if launch_import not in s:
    raise SystemExit('Build59 panel launch import anchor not found')
if 'import kotlinx.coroutines.Job\n' not in s:
    s = s.replace(launch_import, 'import kotlinx.coroutines.Job\n' + launch_import, 1)
asr_import = 'import com.bydmate.app.voice.ContinuousAsr\n'
if asr_import not in s:
    raise SystemExit('Build59 panel ContinuousAsr import anchor not found')
if 'import com.bydmate.app.voice.ContinuousAsrEvent\n' not in s:
    s = s.replace(asr_import, asr_import + 'import com.bydmate.app.voice.ContinuousAsrEvent\n', 1)

collapse_anchor = '    if (!build58PanelExpanded) {\n'
if collapse_anchor not in s:
    raise SystemExit('Build59 Build58 collapse anchor not found')
if 'fun build59RunMicProbe()' not in s:
    lab_state = r'''    var build59MicProbeJob by remember { mutableStateOf<Job?>(null) }
    var build59AsrProbeJob by remember { mutableStateOf<Job?>(null) }

    fun build59RunMicProbe() {
        if (build59MicProbeJob?.isActive == true) {
            build59MicProbeJob?.cancel()
            DiLink3DebugLog.log(context, "BUILD59_RAW_MIC_TEST", "phase=cancel_requested")
            return
        }
        build59MicProbeJob = scope.launch {
            var frames = 0L
            var samples = 0L
            DiLink3DebugLog.log(context, "BUILD59_RAW_MIC_TEST", "phase=start durationMs=3000")
            val result = runCatching {
                audioCapture.captureSession(maxMs = 3_000).collect { frame ->
                    frames++
                    samples += frame.size
                }
            }
            DiLink3DebugLog.log(
                context,
                "BUILD59_RAW_MIC_TEST",
                "phase=end success=${result.isSuccess} frames=$frames samples=$samples error=${result.exceptionOrNull()?.let { it::class.java.simpleName + ":" + it.message }}"
            )
        }
    }

    fun build59RunRawGigaAm() {
        if (build59AsrProbeJob?.isActive == true) {
            build59AsrProbeJob?.cancel()
            DiLink3DebugLog.log(context, "BUILD59_RAW_GIGAAM_TEST", "phase=cancel_requested")
            return
        }
        if (!continuousAsr.isReady()) {
            DiLink3DebugLog.log(context, "BUILD59_RAW_GIGAAM_TEST", "phase=reject reason=model_not_ready")
            return
        }
        build59AsrProbeJob = scope.launch {
            DiLink3DebugLog.log(context, "BUILD59_RAW_GIGAAM_TEST", "phase=start durationMs=10000")
            var speechStarts = 0
            var utterances = 0
            var lastText = ""
            val result = runCatching {
                val pcm = audioCapture.captureSession(maxMs = 10_000)
                continuousAsr.transcribe(pcm).collect { ev ->
                    when (ev) {
                        is ContinuousAsrEvent.SpeechStart -> {
                            speechStarts++
                            DiLink3DebugLog.log(context, "BUILD59_RAW_GIGAAM_EVENT", "type=SpeechStart count=$speechStarts")
                        }
                        is ContinuousAsrEvent.SilenceTick -> Unit
                        is ContinuousAsrEvent.Utterance -> {
                            utterances++
                            lastText = ev.text
                            DiLink3DebugLog.log(context, "BUILD59_RAW_GIGAAM_EVENT", "type=Utterance count=$utterances text=${ev.text}")
                        }
                    }
                }
            }
            DiLink3DebugLog.log(
                context,
                "BUILD59_RAW_GIGAAM_TEST",
                "phase=end success=${result.isSuccess} speechStarts=$speechStarts utterances=$utterances lastText=$lastText error=${result.exceptionOrNull()?.let { it::class.java.simpleName + ":" + it.message }}"
            )
        }
    }

'''
    s = s.replace(collapse_anchor, lab_state + collapse_anchor, 1)

title_anchor = '            Text("DiLink3 Build58", style = MaterialTheme.typography.titleLarge)\n'
if title_anchor not in s:
    raise SystemExit('Build59 Build58 title anchor not found')
controls = r'''            Text("DiLink3 Build59 DIAGNOSTIC LAB", style = MaterialTheme.typography.titleLarge)

            Button(
                onClick = {
                    build58PanelExpanded = false
                    DiLink3DebugLog.log(context, "BUILD59_DEBUG_PANEL", "action=collapse")
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("MINIMIZE DBG") }

            Text("НЕЗАВИСИМЫЕ ТЕСТЫ ГОЛОСА", style = MaterialTheme.typography.titleMedium)
            Text("Каждый тест проверяет отдельный участок цепочки. Для следующей диагностики достаточно отправить лог — переустановка ради одного теста не нужна.", style = MaterialTheme.typography.bodySmall)

            Button(
                onClick = {
                    voiceController.build59HardwareAck("debug_panel")
                    status = "BEEP: команда отправлена"
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("1. TEST BEEP / ПРОВЕРИТЬ СИГНАЛ") }

            Button(
                onClick = {
                    voiceController.build59TestTts()
                    status = "TTS: тестовая фраза отправлена"
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("2. TEST TTS / ПРОВЕРИТЬ ГОЛОС") }

            Button(
                onClick = {
                    voiceController.onPttPressed()
                    status = "PTT toggle: ${voiceController.build59Snapshot()}"
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("3. PTT START / STOP") }

            Button(
                onClick = {
                    val snapshot = voiceController.build59Snapshot()
                    status = "SNAPSHOT: $snapshot"
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("4. VOICE PIPELINE SNAPSHOT") }

            Button(
                onClick = {
                    build59RunMicProbe()
                    status = if (build59MicProbeJob?.isActive == true) "RAW MIC: stop requested" else "RAW MIC: test started; result goes to log"
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (build59MicProbeJob?.isActive == true) "STOP RAW MIC" else "5. RAW MIC TEST - 3 SEC")
            }

            Button(
                onClick = {
                    build59RunRawGigaAm()
                    status = if (continuousAsr.isReady()) "RAW GigaAM: test toggled; result goes to log" else "RAW GigaAM: model NOT READY"
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (build59AsrProbeJob?.isActive == true) "STOP RAW GIGAAM" else "6. RAW GIGAAM TEST - 10 SEC")
            }

'''
s = s.replace(title_anchor, controls, 1)

s = s.replace(
    'DiLink3DebugLog.log(context, "BUILD58_DEBUG_PANEL", "action=expand")',
    'DiLink3DebugLog.log(context, "BUILD59_DEBUG_PANEL", "action=expand")',
    1,
)

p.write_text(s)
print('Build59 installed: hardware ACK + modular voice diagnostics + re-collapsible DBG panel')
