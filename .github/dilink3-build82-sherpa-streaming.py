#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60032"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build82 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Field identity over Build81.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60031", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build81"',
    '            versionNameSuffix = "-dilink3-production-build82"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build81"',
    'android:label="BYDMate DiLink3 Build82"',
    "manifest label",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Truthful runtime name: PIPER is the model family; OfflineTts is sherpa-onnx.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/voice/SherpaTtsEngine.kt")
s = p.read_text()
s = replace_once(
    s,
    '        ttsEngineName = voice.engine.name\n',
    '        ttsEngineName = "SHERPA_ONNX/${voice.engine.name}"\n',
    "diagnostic runtime name",
)

# ---------------------------------------------------------------------------
# 3) Use up to 4 CPU threads instead of a hard-coded 2. Old head units can have many Android
#    framework threads active, so cap at 4 rather than blindly taking every core.
# ---------------------------------------------------------------------------
s = s.replace(
    '                numThreads = 2,\n                // NEVER "nnapi"',
    '                numThreads = sherpaThreadCount(),\n                // NEVER "nnapi"',
)
if s.count('numThreads = sherpaThreadCount()') != 2:
    raise SystemExit("Build82 expected both sherpa TTS model configs to use dynamic thread count")

# Helper placed before createTts(); no JNI involved.
anchor = '''    private fun createTts(): OfflineTts? = runCatching {
'''
helper = '''    private fun sherpaThreadCount(): Int =
        Runtime.getRuntime().availableProcessors().coerceIn(2, 4)

'''
s = replace_once(s, anchor, helper + anchor, "sherpa thread helper")

# ---------------------------------------------------------------------------
# 4) Real buffered streaming for the AGENT QUEUE path.
#
# The old code called generateWithCallback() but accumulated ALL callback chunks before play().
# On the measured Build81 turn that meant ~11.2 s synthesis before the first sample was audible.
#
# Build82 writes callback PCM directly into the existing MODE_STREAM AudioTrack. On DiLink 3 we
# must not start the track empty: AudioFlinger underrun-disables a starving track and the HAL does
# not recover it. Therefore we pre-buffer ~2.8 s of PCM before play(), then continue synthesis into
# the playing track. 2.8 s is intentionally conservative for the measured ~2.24x RTF; if 4 CPU
# threads improve RTF, playback starts even earlier in wall time while retaining underrun margin.
# ---------------------------------------------------------------------------
old = '''                    val synthesisText = textForSynthesis(voice.engine, text, marker::mark)
                    VoiceTimingDiagnostics.noteSynthStart(engine.sampleRate())
                    val samples = accumulateSentence(
                        generate = { onChunk ->
                            engine.generateWithCallback(
                                synthesisText, sid = voice.speakerId, speed = TtsTuning.speed(rate()), TtsSamplesCallback(onChunk),
                            )
                        },
                        stillCurrent = { generation.get() == myGen },
                    )
                    VoiceTimingDiagnostics.noteSynthEnd(samples?.size ?: 0)
                    Log.i(TAG, "synth done (queued): samples=${samples?.size} generation ok=${generation.get() == myGen}")
                    if (samples != null && samples.isNotEmpty() && generation.get() == myGen) {
                        // Same underrun-disable guard as speak(): start the track only with the
                        // sentence in hand. The first sentence of a queue synthesizes for seconds
                        // while an already-started track would starve ACTIVE and get disabled;
                        // for later sentences the track is still playing and play() is skipped.
                        if (out.playState != AudioTrack.PLAYSTATE_PLAYING) out.play()
                        VoiceTimingDiagnostics.noteAudioPlay()
                        VoiceTimingDiagnostics.noteWriteStart()
                        // See the speak() comment: publish before the blocking write, same
                        // ordering fix for queued sentences.
                        val written = writeSentence(
                            samples = samples,
                            write = { out.write(it, 0, it.size, AudioTrack.WRITE_BLOCKING) },
                            publish = {
                                pendingTarget =
                                    PendingTarget(myGen, trackFramesWritten + samples.size)
                                stampAudibleClock(samples.size, engine.sampleRate())
                            },
                            stillCurrent = { generation.get() == myGen },
                            retract = { pendingTarget = null; audibleUntilMs = 0L },
                        )
                        VoiceTimingDiagnostics.noteWriteEnd()
                        if (written > 0) {
                            totalFramesWritten += written
                            trackFramesWritten += written
                        }
                    }
'''
new = '''                    val synthesisText = textForSynthesis(voice.engine, text, marker::mark)
                    val sampleRate = engine.sampleRate()
                    val prebufferFrames = streamPrebufferFrames(sampleRate)
                    var sentenceFrames = 0L
                    var prePlayFrames = 0L
                    var playbackStarted = out.playState == AudioTrack.PLAYSTATE_PLAYING
                    var writeStarted = false
                    VoiceTimingDiagnostics.noteSynthStart(sampleRate)
                    engine.generateWithCallback(
                        synthesisText,
                        sid = voice.speakerId,
                        speed = TtsTuning.speed(rate()),
                        TtsSamplesCallback { chunk ->
                            if (generation.get() != myGen) return@TtsSamplesCallback 0
                            if (chunk.isEmpty()) return@TtsSamplesCallback 1
                            if (!writeStarted) {
                                writeStarted = true
                                VoiceTimingDiagnostics.noteWriteStart()
                            }
                            val written = out.write(chunk, 0, chunk.size, AudioTrack.WRITE_BLOCKING)
                            if (written <= 0) {
                                Log.w(TAG, "Build82 stream write failed: written=$written chunk=${chunk.size}")
                                return@TtsSamplesCallback 0
                            }
                            sentenceFrames += written
                            totalFramesWritten += written
                            trackFramesWritten += written

                            if (!playbackStarted) {
                                prePlayFrames += written
                                if (prePlayFrames >= prebufferFrames) {
                                    out.play()
                                    playbackStarted = true
                                    pendingTarget = PendingTarget(myGen, trackFramesWritten)
                                    stampAudibleClock(prePlayFrames.toInt(), sampleRate)
                                    VoiceTimingDiagnostics.noteAudioPlay()
                                    Log.i(TAG, "Build82 stream play: prebuffer=$prePlayFrames rate=$sampleRate threads=${sherpaThreadCount()}")
                                }
                            } else {
                                pendingTarget = PendingTarget(myGen, trackFramesWritten)
                                stampAudibleClock(written, sampleRate)
                            }
                            1
                        },
                    )
                    // A very short sentence may finish before reaching the conservative prebuffer.
                    // Start it now; this degenerates safely to the old full-sentence behavior.
                    if (generation.get() == myGen && sentenceFrames > 0L && !playbackStarted) {
                        out.play()
                        playbackStarted = true
                        pendingTarget = PendingTarget(myGen, trackFramesWritten)
                        stampAudibleClock(prePlayFrames.toInt(), sampleRate)
                        VoiceTimingDiagnostics.noteAudioPlay()
                        Log.i(TAG, "Build82 short stream play: buffered=$prePlayFrames rate=$sampleRate")
                    }
                    VoiceTimingDiagnostics.noteSynthEnd(sentenceFrames.toInt())
                    if (writeStarted) VoiceTimingDiagnostics.noteWriteEnd()
                    Log.i(
                        TAG,
                        "Build82 synth done (queued): frames=$sentenceFrames prebuffer=$prebufferFrames " +
                            "threads=${sherpaThreadCount()} generation ok=${generation.get() == myGen}",
                    )
'''
s = replace_once(s, old, new, "queued buffered streaming path")

# Pure helper for deterministic test/invariant. 2.8 seconds of source PCM.
companion_anchor = '''        /** PIPER archives need espeak-ng-data/ for phonemization; the VITS_MULTI archive ships
'''
companion_helper = '''        internal const val BUILD82_STREAM_PREBUFFER_MS = 2_800L

        internal fun streamPrebufferFrames(sampleRate: Int): Long =
            sampleRate.coerceAtLeast(1).toLong() * BUILD82_STREAM_PREBUFFER_MS / 1_000L

'''
s = replace_once(s, companion_anchor, companion_helper + companion_anchor, "stream prebuffer helper")
p.write_text(s)

print("Build82 applied: sherpa-onnx buffered streaming queue + dynamic CPU threads")
