#!/usr/bin/env python3
from pathlib import Path


def once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"Alice4.6 anchor missing: {label}")
    return text.replace(old, new, 1)

# Identity.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64006", "versionCode = 64007", "versionCode")
s = once(
    s,
    'versionName = "3.15.2-alice4.5-cold-chain"',
    'versionName = "3.15.2-alice4.6-audiofocus-vrblock"',
    "versionName",
)
p.write_text(s)

# The physical test showed that music is already strongly attenuated even when BYDMate's
# pre-duck state is empty. Do not stack our STREAM_MUSIC volume write on top of Android/BYD
# audio-focus ducking. Keep the 4.5 helper methods for rollback/history, but remove every active
# call from the steering service and log AudioManager state around the external Alice handoff.
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()

s = once(
    s,
    '''            entryPoint().voiceController().beginExternalAliceDuck()\n''',
    '''            Log.i(TAG, "BUILD6_MANUAL_DUCK_DISABLED reason=system_audio_focus")
            logBuild6AudioState("pre_launch")
            aliceHandler.postDelayed({ logBuild6AudioState("post_launch_350") }, 350L)
            aliceHandler.postDelayed({ logBuild6AudioState("post_launch_1500") }, 1_500L)
            aliceHandler.postDelayed({ logBuild6AudioState("post_launch_3500") }, 3_500L)
''',
    "manual duck start",
)

# When the cold->warm chain reports its terminal Alice click, snapshot the media state again.
s = once(
    s,
    '''                        aliceSessionListening = true
                        Log.i(TAG, "ALICE4_5_LISTENING_READY cold=$coldChain exactClicks=$aliceExactAfterColdClickCount")
''',
    '''                        aliceSessionListening = true
                        logBuild6AudioState("listening_ready")
                        Log.i(TAG, "ALICE4_5_LISTENING_READY cold=$coldChain exactClicks=$aliceExactAfterColdClickCount")
''',
    "listening audio snapshot",
)

# Build 4.5 restored a manually changed stream volume when leaving Yandex. 4.6 no longer changes
# that stream, so restoring it would be wrong (and could overwrite a real user/system change).
s = once(
    s,
    '''                    entryPoint().voiceController().endExternalAliceDuck("left_yandex:${activePkg ?: eventPkg}")
''',
    '''                    logBuild6AudioState("left_yandex")
                    Log.i(TAG, "BUILD6_MANUAL_DUCK_RESTORE_SKIPPED reason=not_owned")
''',
    "left-yandex manual restore",
)
s = once(
    s,
    '''        entryPoint().voiceController().endExternalAliceDuck("a11y_unbind")
''',
    '''        Log.i(TAG, "BUILD6_MANUAL_DUCK_RESTORE_SKIPPED reason=a11y_unbind_not_owned")
''',
    "unbind manual restore",
)
s = once(
    s,
    '''        entryPoint().voiceController().endExternalAliceDuck("a11y_destroy")
''',
    '''        Log.i(TAG, "BUILD6_MANUAL_DUCK_RESTORE_SKIPPED reason=a11y_destroy_not_owned")
''',
    "destroy manual restore",
)

# No text/page dump: only system audio state, so the field log stays high-signal and private.
anchor = '''    private fun launchYandexAliceOrApkPure() {
'''
method = '''    private fun logBuild6AudioState(phase: String) {
        try {
            val am = getSystemService(Context.AUDIO_SERVICE) as android.media.AudioManager
            val vol = am.getStreamVolume(android.media.AudioManager.STREAM_MUSIC)
            val max = am.getStreamMaxVolume(android.media.AudioManager.STREAM_MUSIC)
            Log.i(
                TAG,
                "BUILD6_AUDIO_FOCUS phase=$phase mode=${am.mode} musicActive=${am.isMusicActive} " +
                    "musicVol=$vol/$max micMute=${am.isMicrophoneMute}"
            )
        } catch (t: Throwable) {
            Log.w(TAG, "BUILD6_AUDIO_FOCUS phase=$phase failed=${t.javaClass.simpleName}:${t.message}")
        }
    }

'''
s = once(s, anchor, method + anchor, "audio diagnostic helper")
p.write_text(s)

# Build 4.5 already added the privileged, reversible package operation for com.byd.vrassistant.
# Keep exactly that behaviour and make the actual shell result visible in field diagnostics.
p = Path("app/src/main/kotlin/com/bydmate/app/helper/HelperDaemon.kt")
s = p.read_text()
s = once(
    s,
    '''                    val ok = if (pkg == "com.byd.vrassistant" && hidden in 0..1) {
                        val cmd = if (hidden == 1) "pm disable-user --user 0" else "pm enable"
                        shExec("$cmd \\\"\\$1\\\"", pkg).code == 0
                    } else if (pkg == "com.byd.autovoice" && hidden in 0..1) {
''',
    '''                    val ok = if (pkg == "com.byd.vrassistant" && hidden in 0..1) {
                        val cmd = if (hidden == 1) "pm disable-user --user 0" else "pm enable"
                        val result = shExec("$cmd \\\"\\$1\\\"", pkg)
                        android.util.Log.i(
                            "bydmate_helper",
                            "BUILD6_VRASSISTANT_STATE hidden=${hidden == 1} code=${result.code} output=${result.stdout.take(240)}"
                        )
                        result.code == 0
                    } else if (pkg == "com.byd.autovoice" && hidden in 0..1) {
''',
    "vrassistant shell result",
)
p.write_text(s)

# Preserve the startup reassert from 4.5, but give this build a unique marker as well.
p = Path("app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt")
s = p.read_text()
s = once(
    s,
    '''                        Log.i(TAG, "ALICE4_5_VRASSISTANT_BLOCK startup=$vrBlocked")
''',
    '''                        Log.i(TAG, "ALICE4_5_VRASSISTANT_BLOCK startup=$vrBlocked")
                        Log.i(TAG, "BUILD6_VRASSISTANT_REASSERT takeover=true success=$vrBlocked")
''',
    "vrassistant startup marker",
)
p.write_text(s)

print("Alice4.6 applied: system audio-focus diagnostics + no manual duck + vrassistant result logging")
