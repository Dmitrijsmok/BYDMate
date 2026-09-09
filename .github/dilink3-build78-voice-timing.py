#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60028"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build78 anchor missing: {label}")
    return text.replace(old, new, 1)


# 1) Field identity: monotonic update over Build77.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60027", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build77"',
    '            versionNameSuffix = "-dilink3-production-build78"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build77"',
    'android:label="BYDMate DiLink3 Build78"',
    "manifest label",
)
p.write_text(s)


# 2) One in-process diagnostic snapshot for the last voice turn.
#    No logcat is required: Settings polls these fields and shows human-readable timings.
p = Path("app/src/main/kotlin/com/bydmate/app/voice/SherpaTtsEngine.kt")
s = p.read_text()
anchor = '''class SherpaTtsEngine(
'''
diag = r'''/** Build78 field diagnostics for latency and silent-TTS diagnosis.
 *  Values are intentionally process-local and volatile: this is a field-test panel, not telemetry.
 *  We preserve the FIRST streamed sentence/TTS sentence because that determines perceived latency. */
object VoiceTimingDiagnostics {
    @Volatile var pttAtMs: Long = 0L
    @Volatile var asrAtMs: Long = 0L
    @Volatile var agentStartAtMs: Long = 0L
    @Volatile var agentHttpStartAtMs: Long = 0L
    @Volatile var agentFirstDeltaAtMs: Long = 0L
    @Volatile var agentFirstSentenceAtMs: Long = 0L
    @Volatile var agentFinishedAtMs: Long = 0L

    @Volatile var ttsRequestAtMs: Long = 0L
    @Volatile var ttsWorkerAtMs: Long = 0L
    @Volatile var ttsInitStartAtMs: Long = 0L
    @Volatile var ttsInitEndAtMs: Long = 0L
    @Volatile var ttsSynthStartAtMs: Long = 0L
    @Volatile var ttsSynthEndAtMs: Long = 0L
    @Volatile var audioPlayAtMs: Long = 0L
    @Volatile var audioWriteStartAtMs: Long = 0L
    @Volatile var audioWriteEndAtMs: Long = 0L

    @Volatile var ttsMode: String = ""
    @Volatile var ttsVoiceId: String = ""
    @Volatile var ttsEngineName: String = ""
    @Volatile var ttsSpeakerId: Int = -1
    @Volatile var ttsTextLength: Int = 0
    @Volatile var ttsSamples: Int = -1
    @Volatile var ttsSampleRate: Int = 0
    @Volatile var ttsError: String = ""

    @Synchronized
    fun startTurn(now: Long = System.currentTimeMillis()) {
        pttAtMs = now
        asrAtMs = 0L
        agentStartAtMs = 0L
        agentHttpStartAtMs = 0L
        agentFirstDeltaAtMs = 0L
        agentFirstSentenceAtMs = 0L
        agentFinishedAtMs = 0L
        clearTts()
    }

    @Synchronized
    fun beginTts(mode: String, voice: TtsVoice, textLength: Int, force: Boolean) {
        if (!force && ttsRequestAtMs != 0L) return
        clearTts()
        ttsRequestAtMs = System.currentTimeMillis()
        ttsMode = mode
        ttsVoiceId = voice.id
        ttsEngineName = voice.engine.name
        ttsSpeakerId = voice.speakerId
        ttsTextLength = textLength
    }

    @Synchronized
    private fun clearTts() {
        ttsRequestAtMs = 0L
        ttsWorkerAtMs = 0L
        ttsInitStartAtMs = 0L
        ttsInitEndAtMs = 0L
        ttsSynthStartAtMs = 0L
        ttsSynthEndAtMs = 0L
        audioPlayAtMs = 0L
        audioWriteStartAtMs = 0L
        audioWriteEndAtMs = 0L
        ttsMode = ""
        ttsVoiceId = ""
        ttsEngineName = ""
        ttsSpeakerId = -1
        ttsTextLength = 0
        ttsSamples = -1
        ttsSampleRate = 0
        ttsError = ""
    }

    fun noteWorkerStart() {
        if (ttsWorkerAtMs == 0L) ttsWorkerAtMs = System.currentTimeMillis()
    }

    fun noteInitStart() {
        if (ttsInitStartAtMs == 0L) ttsInitStartAtMs = System.currentTimeMillis()
    }

    fun noteInitEnd() {
        if (ttsInitEndAtMs == 0L) ttsInitEndAtMs = System.currentTimeMillis()
    }

    fun noteSynthStart(sampleRate: Int) {
        if (ttsSynthStartAtMs == 0L) ttsSynthStartAtMs = System.currentTimeMillis()
        if (ttsSampleRate == 0) ttsSampleRate = sampleRate
    }

    fun noteSynthEnd(samples: Int) {
        if (ttsSynthEndAtMs == 0L) ttsSynthEndAtMs = System.currentTimeMillis()
        if (ttsSamples < 0) ttsSamples = samples
    }

    fun noteAudioPlay() {
        if (audioPlayAtMs == 0L) audioPlayAtMs = System.currentTimeMillis()
    }

    fun noteWriteStart() {
        if (audioWriteStartAtMs == 0L) audioWriteStartAtMs = System.currentTimeMillis()
    }

    fun noteWriteEnd() {
        if (audioWriteEndAtMs == 0L) audioWriteEndAtMs = System.currentTimeMillis()
    }

    fun noteError(t: Throwable?) {
        val name = t?.javaClass?.simpleName.orEmpty()
        val msg = t?.message.orEmpty()
        ttsError = listOf(name, msg).filter { it.isNotBlank() }.joinToString(": ").ifBlank { "unknown TTS error" }
    }
}

'''
s = replace_once(s, anchor, diag + anchor, "VoiceTimingDiagnostics object")

# Direct speak() covers preview/fallback speech. Force=true resets only TTS fields while
# preserving the current PTT/ASR/API timings when this speak belongs to a live turn.
old = '''        val myGen = generation.incrementAndGet()
        worker.execute {
            if (generation.get() != myGen) return@execute
            _speaking.value = true
'''
new = '''        val myGen = generation.incrementAndGet()
        VoiceTimingDiagnostics.beginTts("direct", selectedVoice(), text.length, force = true)
        worker.execute {
            if (generation.get() != myGen) return@execute
            VoiceTimingDiagnostics.noteWorkerStart()
            _speaking.value = true
'''
s = replace_once(s, old, new, "direct TTS request/worker timing")

old = '''                    val samples = cached ?: accumulateSentence(
                        generate = { onChunk ->
'''
new = '''                    if (cached == null) VoiceTimingDiagnostics.noteSynthStart(engine.sampleRate())
                    val samples = cached ?: accumulateSentence(
                        generate = { onChunk ->
'''
s = replace_once(s, old, new, "direct synth start")

old = '''                    ).also { Log.i(TAG, "synth done: samples=${it?.size} generation ok=${generation.get() == myGen}") }
                    if (samples != null && samples.isNotEmpty() && generation.get() == myGen) {
'''
new = '''                    ).also {
                        if (cached == null) VoiceTimingDiagnostics.noteSynthEnd(it?.size ?: 0)
                        else {
                            VoiceTimingDiagnostics.noteSynthStart(engine.sampleRate())
                            VoiceTimingDiagnostics.noteSynthEnd(it.size)
                        }
                        Log.i(TAG, "synth done: samples=${it?.size} generation ok=${generation.get() == myGen}")
                    }
                    if (samples != null && samples.isNotEmpty() && generation.get() == myGen) {
'''
s = replace_once(s, old, new, "direct synth end")

old = '''                        if (out.playState != AudioTrack.PLAYSTATE_PLAYING) out.play()
                        // Publish target/floor before the write, not after -- see writeSentence's
'''
new = '''                        if (out.playState != AudioTrack.PLAYSTATE_PLAYING) out.play()
                        VoiceTimingDiagnostics.noteAudioPlay()
                        VoiceTimingDiagnostics.noteWriteStart()
                        // Publish target/floor before the write, not after -- see writeSentence's
'''
s = replace_once(s, old, new, "direct audio start")

old = '''                        if (written > 0) trackFramesWritten += written
                    }
                    // Skip the drain wait if a newer speak()/stop() has already superseded us --
'''
new = '''                        VoiceTimingDiagnostics.noteWriteEnd()
                        if (written > 0) trackFramesWritten += written
                    }
                    // Skip the drain wait if a newer speak()/stop() has already superseded us --
'''
s = replace_once(s, old, new, "direct write end")

# Queued speech is the real agent path. Keep the first sentence timings even if later sentences arrive.
old = '''        override fun enqueue(text: String): Boolean {
            if (text.isBlank() || generation.get() != myGen) return false
            worker.execute {
                if (generation.get() != myGen) return@execute
                runCatching {
'''
new = '''        override fun enqueue(text: String): Boolean {
            if (text.isBlank() || generation.get() != myGen) return false
            VoiceTimingDiagnostics.beginTts("queue", selectedVoice(), text.length, force = false)
            worker.execute {
                if (generation.get() != myGen) return@execute
                VoiceTimingDiagnostics.noteWorkerStart()
                runCatching {
'''
s = replace_once(s, old, new, "queue request/worker timing")

old = '''                    val synthesisText = textForSynthesis(voice.engine, text, marker::mark)
                    val samples = accumulateSentence(
'''
new = '''                    val synthesisText = textForSynthesis(voice.engine, text, marker::mark)
                    VoiceTimingDiagnostics.noteSynthStart(engine.sampleRate())
                    val samples = accumulateSentence(
'''
s = replace_once(s, old, new, "queue synth start")

old = '''                    Log.i(TAG, "synth done (queued): samples=${samples?.size} generation ok=${generation.get() == myGen}")
                    if (samples != null && samples.isNotEmpty() && generation.get() == myGen) {
'''
new = '''                    VoiceTimingDiagnostics.noteSynthEnd(samples?.size ?: 0)
                    Log.i(TAG, "synth done (queued): samples=${samples?.size} generation ok=${generation.get() == myGen}")
                    if (samples != null && samples.isNotEmpty() && generation.get() == myGen) {
'''
s = replace_once(s, old, new, "queue synth end")

# The same play()/write sequence appears a second time in QueuedSpeech after the direct path.
old = '''                        if (out.playState != AudioTrack.PLAYSTATE_PLAYING) out.play()
                        // See the speak() comment: publish before the blocking write, same
'''
new = '''                        if (out.playState != AudioTrack.PLAYSTATE_PLAYING) out.play()
                        VoiceTimingDiagnostics.noteAudioPlay()
                        VoiceTimingDiagnostics.noteWriteStart()
                        // See the speak() comment: publish before the blocking write, same
'''
s = replace_once(s, old, new, "queue audio start")

old = '''                        if (written > 0) {
                            totalFramesWritten += written
                            trackFramesWritten += written
                        }
'''
new = '''                        VoiceTimingDiagnostics.noteWriteEnd()
                        if (written > 0) {
                            totalFramesWritten += written
                            trackFramesWritten += written
                        }
'''
s = replace_once(s, old, new, "queue write end")

# Capture JNI/model initialization time and actual exceptions. The object records only the first
# init in a diagnostic sample; a warmed engine therefore correctly shows init as "—".
old = '''    private fun createTts(): OfflineTts? = runCatching {
        val voice = selectedVoice()
'''
new = '''    private fun createTts(): OfflineTts? = runCatching {
        VoiceTimingDiagnostics.noteInitStart()
        val voice = selectedVoice()
'''
s = replace_once(s, old, new, "TTS init start")

old = '''        loadGuard?.noteLoadSuccess(AsrLoadGuard.ARTIFACT_TTS)
        ttsInstance
    }.onFailure { Log.w(TAG, "tts init failed", it) }.getOrNull()
'''
new = '''        loadGuard?.noteLoadSuccess(AsrLoadGuard.ARTIFACT_TTS)
        VoiceTimingDiagnostics.noteInitEnd()
        ttsInstance
    }.onFailure {
        VoiceTimingDiagnostics.noteInitEnd()
        VoiceTimingDiagnostics.noteError(it)
        Log.w(TAG, "tts init failed", it)
    }.getOrNull()
'''
s = replace_once(s, old, new, "TTS init end/error")

# Capture exceptions from both direct speak and queued speech paths on the diagnostic panel.
s = replace_once(
    s,
    '''                }.onFailure { Log.w(TAG, "tts speak failed", it) }
''',
    '''                }.onFailure {
                    VoiceTimingDiagnostics.noteError(it)
                    Log.w(TAG, "tts speak failed", it)
                }
''',
    "direct TTS error",
)
s = replace_once(
    s,
    '''                }.onFailure { Log.w(TAG, "tts enqueue failed", it) }
''',
    '''                }.onFailure {
                    VoiceTimingDiagnostics.noteError(it)
                    Log.w(TAG, "tts enqueue failed", it)
                }
''',
    "queue TTS error",
)
p.write_text(s)


# 3) Turn/API milestones in the existing controller/backend path.
p = Path("app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt")
s = p.read_text()
old = '''        context.getSharedPreferences("build73_voice_runtime", Context.MODE_PRIVATE).edit()
            .putLong("ptt_at", System.currentTimeMillis())
'''
new = '''        VoiceTimingDiagnostics.startTurn()
        context.getSharedPreferences("build73_voice_runtime", Context.MODE_PRIVATE).edit()
            .putLong("ptt_at", System.currentTimeMillis())
'''
s = replace_once(s, old, new, "PTT timing")

old = '''                            context.getSharedPreferences("build73_voice_runtime", Context.MODE_PRIVATE).edit()
                                .putString("stage", "ASR_OK")
'''
new = '''                            VoiceTimingDiagnostics.asrAtMs = System.currentTimeMillis()
                            context.getSharedPreferences("build73_voice_runtime", Context.MODE_PRIVATE).edit()
                                .putString("stage", "ASR_OK")
'''
s = replace_once(s, old, new, "ASR timing")

old = '''        val queue = if (gate.ttsEnabled()) runCatching { ttsEngine.startQueue() }.getOrNull() else null
'''
new = '''        VoiceTimingDiagnostics.agentStartAtMs = System.currentTimeMillis()
        val queue = if (gate.ttsEnabled()) runCatching { ttsEngine.startQueue() }.getOrNull() else null
'''
s = replace_once(s, old, new, "agent start timing")

old = '''                r = agentOrchestrator.ask(transcript) { sentence ->
                    // Hard stop gate: the SSE loop can emit one more sentence between the ask
'''
new = '''                r = agentOrchestrator.ask(transcript) { sentence ->
                    if (VoiceTimingDiagnostics.agentFirstSentenceAtMs == 0L) {
                        VoiceTimingDiagnostics.agentFirstSentenceAtMs = System.currentTimeMillis()
                    }
                    // Hard stop gate: the SSE loop can emit one more sentence between the ask
'''
s = replace_once(s, old, new, "first streamed sentence timing")

old = '''        runCatching { queue?.finish() }
        val result = r ?: run {
'''
new = '''        runCatching { queue?.finish() }
        VoiceTimingDiagnostics.agentFinishedAtMs = System.currentTimeMillis()
        val result = r ?: run {
'''
s = replace_once(s, old, new, "agent finish timing")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/agent/LlmAgentBackend.kt")
s = p.read_text()
s = replace_once(
    s,
    '''import com.bydmate.app.data.remote.OpenRouterClient
''',
    '''import com.bydmate.app.data.remote.OpenRouterClient
import com.bydmate.app.voice.VoiceTimingDiagnostics
''',
    "diagnostic import",
)
old = '''        var forwarded = false
        val guarded: ((String) -> Unit)? = onDelta?.let { cb -> { d -> forwarded = true; cb(d) } }

        val startedAt = nowMs()
'''
new = '''        var forwarded = false
        var firstDeltaSeen = false
        val guarded: ((String) -> Unit)? = onDelta?.let { cb ->
            { d ->
                if (!firstDeltaSeen) {
                    firstDeltaSeen = true
                    VoiceTimingDiagnostics.agentFirstDeltaAtMs = nowMs()
                }
                forwarded = true
                cb(d)
            }
        }

        val startedAt = nowMs()
        VoiceTimingDiagnostics.agentHttpStartAtMs = startedAt
'''
s = replace_once(s, old, new, "first LLM delta timing")
p.write_text(s)


# 4) Human-readable panel directly below the existing Voice Agent runtime block.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
anchor = '''            Text("TTS source: ${state.ttsSource} · voice: ${state.ttsVoice}", color = TextMuted, fontSize = 10.sp, modifier = Modifier.padding(bottom = 8.dp))
'''
panel = anchor + r'''            // Build78: field timing panel. runtimeRefresh is the existing 750 ms ticker,
            // so volatile diagnostics become visible without logcat or a manual refresh button.
            val diagRefresh = runtimeRefresh
            val diag = com.bydmate.app.voice.VoiceTimingDiagnostics
            fun msBetween(a: Long, b: Long): Long? = if (a > 0L && b >= a) b - a else null
            fun sec(ms: Long?): String = if (ms == null) "—" else
                java.lang.String.format(java.util.Locale.US, "%.2f с", ms / 1000.0)
            fun fromPtt(at: Long): String = sec(msBetween(diag.pttAtMs, at))
            val _diagTick = diagRefresh // explicit read keeps the polling recomposition dependency

            HorizontalDivider(color = Border, modifier = Modifier.padding(vertical = 6.dp))
            Text("Диагностика задержки", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            Text(
                "PTT → ASR текст: ${sec(msBetween(diag.pttAtMs, diag.asrAtMs))}",
                color = TextMuted, fontSize = 10.sp,
            )
            Text(
                "API: до 1-го токена ${sec(msBetween(diag.agentHttpStartAtMs, diag.agentFirstDeltaAtMs))} · " +
                    "до 1-й фразы ${sec(msBetween(diag.agentStartAtMs, diag.agentFirstSentenceAtMs))} · " +
                    "весь ответ ${sec(msBetween(diag.agentStartAtMs, diag.agentFinishedAtMs))}",
                color = TextMuted, fontSize = 10.sp,
            )
            Text(
                "TTS: ожидание worker ${sec(msBetween(diag.ttsRequestAtMs, diag.ttsWorkerAtMs))} · " +
                    "инициализация ${sec(msBetween(diag.ttsInitStartAtMs, diag.ttsInitEndAtMs))} · " +
                    "синтез ${sec(msBetween(diag.ttsSynthStartAtMs, diag.ttsSynthEndAtMs))}",
                color = TextMuted, fontSize = 10.sp,
            )
            Text(
                "Звук: PTT → play ${fromPtt(diag.audioPlayAtMs)} · " +
                    "TTS request → play ${sec(msBetween(diag.ttsRequestAtMs, diag.audioPlayAtMs))} · " +
                    "write ${sec(msBetween(diag.audioWriteStartAtMs, diag.audioWriteEndAtMs))}",
                color = TextMuted, fontSize = 10.sp,
            )
            Text(
                "Голос: ${diag.ttsVoiceId.ifBlank { "—" }} · ${diag.ttsEngineName.ifBlank { "—" }} · " +
                    "sid=${if (diag.ttsSpeakerId >= 0) diag.ttsSpeakerId else "—"} · mode=${diag.ttsMode.ifBlank { "—" }}",
                color = TextMuted, fontSize = 10.sp,
            )
            Text(
                "TTS data: text=${diag.ttsTextLength} chars · samples=${if (diag.ttsSamples >= 0) diag.ttsSamples else "—"} · " +
                    "rate=${if (diag.ttsSampleRate > 0) diag.ttsSampleRate else "—"}",
                color = TextMuted, fontSize = 10.sp,
            )
            if (diag.ttsError.isNotBlank()) {
                Text("Ошибка TTS: ${diag.ttsError}", color = SocRed, fontSize = 10.sp, fontWeight = FontWeight.SemiBold)
            }
'''
s = replace_once(s, anchor, panel, "visible timing panel")
p.write_text(s)

print("Build78 applied: human-readable ASR/API/TTS/audio latency diagnostics")
