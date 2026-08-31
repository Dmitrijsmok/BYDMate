from pathlib import Path

# Build 41: two high-value tasks from real DiLink3 vehicle logs.
# 1) Trace the system/vendor assistant routing at the exact moment KEYCODE_AUTO_MEDIA_VOICE (304)
#    is injected. Activity consume is known NOT to suppress the stock assistant, so capture Android's
#    configured assistant / voice interaction / recognizer handlers and resolved intent targets.
# 2) Trace the real offline TTS path below TtsRouter: engine creation, synthesis, first AudioTrack
#    play/write and drain. This replaces the unreliable top-level audible() timeout as our primary
#    latency evidence.

# ---------------------------------------------------------------------------
# MainActivity: capture system assistant routing whenever 304 DOWN arrives.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/MainActivity.kt')
s = p.read_text()

anchor = '''    override fun dispatchKeyEvent(event: KeyEvent): Boolean {'''
helper = r'''    private fun logDiLink3AssistantRouting(reason: String) {
        runCatching {
            val cr = contentResolver
            fun secure(name: String): String = android.provider.Settings.Secure.getString(cr, name) ?: "<null>"
            fun resolve(action: String): String {
                val i = android.content.Intent(action)
                val ri = packageManager.resolveActivity(i, android.content.pm.PackageManager.MATCH_DEFAULT_ONLY)
                val ai = ri?.activityInfo
                return if (ai == null) "<none>" else "${ai.packageName}/${ai.name}"
            }
            val assistant = secure("assistant")
            val vis = secure("voice_interaction_service")
            val recognizer = secure("voice_recognition_service")
            val enabledA11y = secure("enabled_accessibility_services")
            DiLink3DebugLog.log(
                applicationContext,
                "SYSTEM_ASSISTANT_ROUTING",
                "reason=$reason assistant=$assistant voiceInteraction=$vis voiceRecognizer=$recognizer " +
                    "resolveAssist=${resolve(android.content.Intent.ACTION_ASSIST)} " +
                    "resolveVoiceCommand=${resolve(android.content.Intent.ACTION_VOICE_COMMAND)} " +
                    "enabledAccessibility=$enabledA11y"
            )
        }.onFailure {
            DiLink3DebugLog.log(applicationContext, "SYSTEM_ASSISTANT_ROUTING_ERROR", "${it::class.java.simpleName}: ${it.message}")
        }
    }

'''
if helper.strip() not in s:
    if anchor not in s:
        raise SystemExit('MainActivity dispatch anchor not found')
    s = s.replace(anchor, helper + anchor, 1)

needle = '''            DiLink3DebugLog.log(applicationContext, "ACTIVITY_MIC_304_SEEN", "action=${event.action} scanCode=${event.scanCode} deviceId=${event.deviceId} source=${event.source}")
        }'''
replacement = '''            DiLink3DebugLog.log(applicationContext, "ACTIVITY_MIC_304_SEEN", "action=${event.action} scanCode=${event.scanCode} deviceId=${event.deviceId} source=${event.source}")
            if (event.action == KeyEvent.ACTION_DOWN) logDiLink3AssistantRouting("key304_down")
        }'''
if needle not in s:
    raise SystemExit('MainActivity 304 seen anchor not found')
s = s.replace(needle, replacement, 1)
p.write_text(s)
print('Build41: added system assistant routing snapshot on key304 DOWN')

# ---------------------------------------------------------------------------
# SherpaTtsEngine: instrument the actual offline path used by TtsRouter.speakOffline().
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/voice/SherpaTtsEngine.kt')
s = p.read_text()

import_anchor = 'import android.util.Log\n'
import_line = 'import com.bydmate.app.ui.diagnostics.DiLink3DebugLog\n'
if import_line not in s:
    if import_anchor not in s:
        raise SystemExit('Sherpa import anchor not found')
    s = s.replace(import_anchor, import_anchor + import_line, 1)

# This diagnostic logger needs a Context, which SherpaTtsEngine intentionally does not own.
# Therefore expose timing through android.util.Log plus a lightweight in-process static recorder
# consumed by the diagnostic bridge. Add static volatile trace fields and a helper.
companion_anchor = '''    companion object {
        private const val TAG = "SherpaTtsEngine"'''
companion_repl = '''    companion object {
        @Volatile var diagStage: String = "idle"
        @Volatile var diagStageAtMs: Long = 0L
        @Volatile var diagGeneration: Int = -1
        @Volatile var diagDetail: String = ""

        private fun diag(stage: String, generation: Int, detail: String = "") {
            diagStage = stage
            diagStageAtMs = SystemClock.elapsedRealtime()
            diagGeneration = generation
            diagDetail = detail
            Log.i(TAG, "DIAG_TTS stage=$stage gen=$generation $detail")
        }

        private const val TAG = "SherpaTtsEngine"'''
if companion_anchor not in s:
    raise SystemExit('Sherpa companion anchor not found')
s = s.replace(companion_anchor, companion_repl, 1)

needle = '''        val myGen = generation.incrementAndGet()
        worker.execute {'''
replacement = '''        val myGen = generation.incrementAndGet()
        diag("accepted", myGen, "chars=${text.length} voice=${selectedVoice().id}")
        worker.execute {
            diag("worker_start", myGen, "chars=${text.length}")'''
if needle not in s:
    raise SystemExit('Sherpa speak worker anchor not found')
s = s.replace(needle, replacement, 1)

needle = '''                    val engine = tts ?: createTts()?.also {
                        Log.i(TAG, "engine created: voice=${selectedVoice().id} engineRate=${it.sampleRate()}")
                        tts = it
                    } ?: run {'''
replacement = '''                    val engine = tts ?: run {
                        val engineStart = SystemClock.elapsedRealtime()
                        diag("engine_create_start", myGen, "voice=${selectedVoice().id}")
                        createTts()?.also {
                            diag("engine_create_done", myGen, "dt=${SystemClock.elapsedRealtime() - engineStart}ms rate=${it.sampleRate()}")
                            Log.i(TAG, "engine created: voice=${selectedVoice().id} engineRate=${it.sampleRate()}")
                            tts = it
                        }
                    } ?: run {'''
if needle not in s:
    raise SystemExit('Sherpa engine create anchor not found')
s = s.replace(needle, replacement, 1)

needle = '''                    val samples = cached ?: accumulateSentence(
                        generate = { onChunk ->'''
replacement = '''                    val synthStart = SystemClock.elapsedRealtime()
                    diag("synth_start", myGen, "cached=${cached != null} chars=${text.length}")
                    val samples = cached ?: accumulateSentence(
                        generate = { onChunk ->'''
if needle not in s:
    raise SystemExit('Sherpa synth start anchor not found')
s = s.replace(needle, replacement, 1)

needle = ''').also { Log.i(TAG, "synth done: samples=${it?.size} generation ok=${generation.get() == myGen}") }
                    if (samples != null && samples.isNotEmpty() && generation.get() == myGen) {'''
replacement = ''').also {
                        diag("synth_done", myGen, "dt=${SystemClock.elapsedRealtime() - synthStart}ms samples=${it?.size} current=${generation.get() == myGen}")
                        Log.i(TAG, "synth done: samples=${it?.size} generation ok=${generation.get() == myGen}")
                    }
                    if (cached != null) diag("synth_done", myGen, "dt=${SystemClock.elapsedRealtime() - synthStart}ms samples=${cached.size} cache=true")
                    if (samples != null && samples.isNotEmpty() && generation.get() == myGen) {'''
if needle not in s:
    raise SystemExit('Sherpa synth done anchor not found')
s = s.replace(needle, replacement, 1)

needle = '''                        if (out.playState != AudioTrack.PLAYSTATE_PLAYING) out.play()
                        // Publish target/floor before the write'''
replacement = '''                        diag("audio_play_call", myGen, "playStateBefore=${out.playState} samples=${samples.size} rate=${engine.sampleRate()}")
                        if (out.playState != AudioTrack.PLAYSTATE_PLAYING) out.play()
                        diag("audio_playing", myGen, "playStateAfter=${out.playState}")
                        // Publish target/floor before the write'''
if needle not in s:
    raise SystemExit('Sherpa play anchor not found')
s = s.replace(needle, replacement, 1)

needle = '''                        val written = writeSentence(
                            samples = samples,'''
replacement = '''                        val writeStart = SystemClock.elapsedRealtime()
                        diag("audio_write_start", myGen, "samples=${samples.size}")
                        val written = writeSentence(
                            samples = samples,'''
if needle not in s:
    raise SystemExit('Sherpa write anchor not found')
s = s.replace(needle, replacement, 1)

needle = '''                        if (written > 0) trackFramesWritten += written
                    }
                    // Skip the drain wait'''
replacement = '''                        if (written > 0) trackFramesWritten += written
                        diag("audio_write_done", myGen, "dt=${SystemClock.elapsedRealtime() - writeStart}ms written=$written totalFrames=$trackFramesWritten")
                    }
                    // Skip the drain wait'''
if needle not in s:
    raise SystemExit('Sherpa write done anchor not found')
s = s.replace(needle, replacement, 1)

needle = '''                        awaitPlaybackDrain(out, trackFramesWritten, myGen, timeout)
                        // Park the drained track'''
replacement = '''                        val drainStart = SystemClock.elapsedRealtime()
                        diag("drain_start", myGen, "timeout=${timeout}ms target=$trackFramesWritten")
                        awaitPlaybackDrain(out, trackFramesWritten, myGen, timeout)
                        diag("drain_done", myGen, "dt=${SystemClock.elapsedRealtime() - drainStart}ms")
                        // Park the drained track'''
if needle not in s:
    raise SystemExit('Sherpa drain anchor not found')
s = s.replace(needle, replacement, 1)

p.write_text(s)
print('Build41: added deep offline TTS stage recorder')

# ---------------------------------------------------------------------------
# DiLink3E2EBridge: expose Sherpa stage recorder to the normal diagnostic log.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3E2EBridge.kt')
s = p.read_text()

import_anchor = 'import com.bydmate.app.voice.TtsEngine\n'
import_line = 'import com.bydmate.app.voice.SherpaTtsEngine\n'
if import_line not in s:
    if import_anchor not in s:
        raise SystemExit('E2E bridge import anchor not found')
    s = s.replace(import_anchor, import_anchor + import_line, 1)

needle = '''    fun ttsSpeaking(): Boolean = runCatching { deps.ttsEngine().speaking.value }.getOrDefault(false)
'''
replacement = '''    fun ttsSpeaking(): Boolean = runCatching { deps.ttsEngine().speaking.value }.getOrDefault(false)

    fun ttsDeepTrace(): String = "stage=${SherpaTtsEngine.diagStage} at=${SherpaTtsEngine.diagStageAtMs} gen=${SherpaTtsEngine.diagGeneration} detail=${SherpaTtsEngine.diagDetail}"
'''
if needle not in s:
    raise SystemExit('E2E deep trace function anchor not found')
s = s.replace(needle, replacement, 1)
p.write_text(s)
print('Build41: exposed Sherpa stage trace through E2E bridge')

# ---------------------------------------------------------------------------
# Wizard polling: log transitions of the deep TTS stage while waiting for audio.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()
needle = '''                            var firstAudioLogged = false
                            val timeoutAt = pollStarted + 15_000L
                            while (SystemClock.elapsedRealtime() < timeoutAt) {
                                if (e2eBridge.ttsAudible()) {'''
replacement = '''                            var firstAudioLogged = false
                            var lastDeepTrace = ""
                            val timeoutAt = pollStarted + 30_000L
                            while (SystemClock.elapsedRealtime() < timeoutAt) {
                                val deepTrace = e2eBridge.ttsDeepTrace()
                                if (deepTrace != lastDeepTrace) {
                                    lastDeepTrace = deepTrace
                                    DiLink3DebugLog.log(context, "E2E_TTS_DEEP_STAGE", deepTrace)
                                }
                                if (deepTrace.contains("stage=audio_write_start") || deepTrace.contains("stage=audio_playing")) {
                                    val now = SystemClock.elapsedRealtime()
                                    if (!firstAudioLogged) {
                                        ttsFirstAudioMs = now
                                        DiLink3DebugLog.log(context, "E2E_TTS_OUTPUT_START", "fromResult=${now - resultAt}ms fromAsrFinal=${if (e2eAsrFinalMs > 0) now - e2eAsrFinalMs else -1}ms trace=$deepTrace")
                                        firstAudioLogged = true
                                    }
                                }
                                if (e2eBridge.ttsAudible()) {'''
if needle not in s:
    raise SystemExit('Wizard TTS poll anchor not found')
s = s.replace(needle, replacement, 1)

needle = '''                            if (!firstAudioLogged) {
                                DiLink3DebugLog.log(context, "E2E_TTS_FIRST_AUDIO_TIMEOUT", "waited=${SystemClock.elapsedRealtime() - pollStarted}ms speaking=${e2eBridge.ttsSpeaking()} audible=${e2eBridge.ttsAudible()}")'''
replacement = '''                            if (!firstAudioLogged) {
                                DiLink3DebugLog.log(context, "E2E_TTS_FIRST_AUDIO_TIMEOUT", "waited=${SystemClock.elapsedRealtime() - pollStarted}ms speaking=${e2eBridge.ttsSpeaking()} audible=${e2eBridge.ttsAudible()} deep=${e2eBridge.ttsDeepTrace()}")'''
if needle not in s:
    raise SystemExit('Wizard timeout anchor not found')
s = s.replace(needle, replacement, 1)
p.write_text(s)
print('Build41: wizard now traces deep TTS stages for up to 30 s')
