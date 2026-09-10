#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60033"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build83 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Monotonic field identity over Build82.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60032", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build82"',
    '            versionNameSuffix = "-dilink3-production-build83"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build82"',
    'android:label="BYDMate DiLink3 Build83"',
    "manifest label",
)

# Android kills/replaces the application process during an APK update. DiLink 3's accessibility
# binding is then gone, while the persisted toggle is still ON. Receive the package-replaced event
# so BYDMate restarts its foreground service and the Build81 A11Y self-heal without requiring the
# user to toggle OFF/ON manually.
s = replace_once(
    s,
    '                <action android:name="android.intent.action.USER_PRESENT" />\n',
    '                <action android:name="android.intent.action.USER_PRESENT" />\n'
    '                <action android:name="android.intent.action.MY_PACKAGE_REPLACED" />\n',
    "MY_PACKAGE_REPLACED manifest action",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Immediate post-update restart of TrackingService.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/service/BootReceiver.kt")
s = p.read_text()
s = replace_once(
    s,
    '''            Intent.ACTION_USER_PRESENT,
            ACTION_RECOVER_START,
''',
    '''            Intent.ACTION_USER_PRESENT,
            Intent.ACTION_MY_PACKAGE_REPLACED,
            ACTION_RECOVER_START,
''',
    "package replaced valid action",
)

# On Android 10 / DiLink3, starting directly from this system broadcast is allowed and avoids
# waiting for WorkManager. We still enqueue WorkManager below as a belt-and-suspenders fallback.
anchor = '''        logBootEvent(context, intent.action ?: "unknown")

        // Use WorkManager — guaranteed execution (like BydConnect)
'''
insert = '''        logBootEvent(context, intent.action ?: "unknown")

        if (intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            try {
                TrackingService.start(context)
                updateBootMethod(context, "DirectAfterPackageReplace")
                ChainLog.append(context, "MY_PACKAGE_REPLACED direct TrackingService start OK")
                Log.i(TAG, "APK updated: TrackingService restarted immediately for A11Y rebind")
            } catch (e: Exception) {
                ChainLog.append(context, "MY_PACKAGE_REPLACED direct start failed: ${e.message}")
                Log.w(TAG, "APK update direct service start failed; WorkManager fallback follows", e)
            }
        }

        // Use WorkManager — guaranteed execution (like BydConnect)
'''
s = replace_once(s, anchor, insert, "post-update direct service start")

# If an old unique boot work happens to be pending, package replacement must not KEEP it and skip
# the new recovery request. REPLACE only for this update event; normal boot/user events retain KEEP.
s = replace_once(
    s,
    '''            WorkManager.getInstance(context).enqueueUniqueWork(
                ServiceStartWorker.WORK_NAME,
                ExistingWorkPolicy.KEEP,
                request
            )
''',
    '''            WorkManager.getInstance(context).enqueueUniqueWork(
                ServiceStartWorker.WORK_NAME,
                if (intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) ExistingWorkPolicy.REPLACE else ExistingWorkPolicy.KEEP,
                request
            )
''',
    "replace WorkManager policy after APK update",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 3) Build82 field data proved the 2.8 s direct-to-AudioTrack prebuffer is unsafe on DiLink3.
#    This head unit is Android 10 (API 29), where createTrack() intentionally uses a small
#    4*minBuffer track because startThresholdInFrames cannot be lowered. Build82 tried to put
#    2.8 seconds into that small track BEFORE play(); the field result was only 7088 samples
#    (=0.32 s) and RTF=20.14x. That is a truncated first callback, not a valid full-utterance RTF.
#
#    Roll ONLY the direct streaming queue back to the proven full-sentence buffer/write ordering.
#    Keep Build82's important CPU change: sherpaThreadCount() up to 4 threads. The next field test
#    will therefore measure the actual benefit of 4-thread sherpa/Piper without audio truncation.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/voice/SherpaTtsEngine.kt")
s = p.read_text()
old = '''                    val synthesisText = textForSynthesis(voice.engine, text, marker::mark)
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
new = '''                    val synthesisText = textForSynthesis(voice.engine, text, marker::mark)
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
                    Log.i(
                        TAG,
                        "Build83 synth done (queued): samples=${samples?.size} threads=${sherpaThreadCount()} " +
                            "generation ok=${generation.get() == myGen}",
                    )
                    if (samples != null && samples.isNotEmpty() && generation.get() == myGen) {
                        if (out.playState != AudioTrack.PLAYSTATE_PLAYING) out.play()
                        VoiceTimingDiagnostics.noteAudioPlay()
                        VoiceTimingDiagnostics.noteWriteStart()
                        val written = writeSentence(
                            samples = samples,
                            write = { out.write(it, 0, it.size, AudioTrack.WRITE_BLOCKING) },
                            publish = {
                                pendingTarget = PendingTarget(myGen, trackFramesWritten + samples.size)
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
s = replace_once(s, old, new, "rollback unsafe direct AudioTrack prebuffer")

# Remove the now-unused Build82 prebuffer helper while keeping the 4-thread helper.
helper = '''        internal const val BUILD82_STREAM_PREBUFFER_MS = 2_800L

        internal fun streamPrebufferFrames(sampleRate: Int): Long =
            sampleRate.coerceAtLeast(1).toLong() * BUILD82_STREAM_PREBUFFER_MS / 1_000L

'''
s = replace_once(s, helper, "", "remove Build82 direct-track prebuffer helper")
p.write_text(s)

print("Build83 applied: package-update A11Y rebind + safe 4-thread sherpa/Piper queue")
