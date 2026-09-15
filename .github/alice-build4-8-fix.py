#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice4.8 anchor missing: {label}")
    return text.replace(old, new, 1)


# Identity
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64008", "versionCode = 64009", "versionCode")
s = once(
    s,
    'versionName = "3.15.2-alice4.7-build95-recovery"',
    'versionName = "3.15.2-alice4.8-stable-duck"',
    "versionName",
)
p.write_text(s)


# Restore the proven 4.5 external-Alice media duck that 4.6 intentionally disabled.
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
old = '''            Log.i(TAG, "BUILD6_MANUAL_DUCK_DISABLED reason=system_audio_focus")
            logBuild6AudioState("pre_launch")
            aliceHandler.postDelayed({ logBuild6AudioState("post_launch_350") }, 350L)
            aliceHandler.postDelayed({ logBuild6AudioState("post_launch_1500") }, 1_500L)
            aliceHandler.postDelayed({ logBuild6AudioState("post_launch_3500") }, 3_500L)
'''
new = '''            entryPoint().voiceController().beginExternalAliceDuck()
            Log.i(TAG, "BUILD8_MANUAL_DUCK_ENABLED target=4")
            logBuild6AudioState("pre_launch_after_duck")
            aliceHandler.postDelayed({ logBuild6AudioState("post_launch_350") }, 350L)
            aliceHandler.postDelayed({ logBuild6AudioState("post_launch_1500") }, 1_500L)
            aliceHandler.postDelayed({ logBuild6AudioState("post_launch_3500") }, 3_500L)
'''
s = once(s, old, new, "manual duck start")

# Cold description fallback must mark the Alice session as listening too, otherwise
# leaving Yandex cannot restore volume until the safety timeout.
old = '''                if (clickAliceCandidate(node, "alice_description", source, terminal = true)) {
                    Log.i(TAG, "ALICE4_1_LISTENING_CLICK desc=true coldFirst=$aliceColdEntryClicked")
                    return true
                }
'''
new = '''                if (clickAliceCandidate(node, "alice_description", source, terminal = true)) {
                    aliceSessionListening = true
                    logBuild6AudioState("listening_ready_description")
                    Log.i(TAG, "BUILD8_LISTENING_READY desc=true coldFirst=$aliceColdEntryClicked")
                    return true
                }
'''
s = once(s, old, new, "description listening state")

# Restore original media volume when Alice/Yandex loses the foreground.
old = '''                    logBuild6AudioState("left_yandex")
                    Log.i(TAG, "BUILD6_MANUAL_DUCK_RESTORE_SKIPPED reason=not_owned")
'''
new = '''                    entryPoint().voiceController().endExternalAliceDuck("left_yandex:${activePkg ?: eventPkg}")
                    logBuild6AudioState("left_yandex_after_restore")
                    Log.i(TAG, "BUILD8_MANUAL_DUCK_RESTORED reason=left_yandex")
'''
s = once(s, old, new, "left-yandex restore")

s = once(
    s,
    '''        Log.i(TAG, "BUILD6_MANUAL_DUCK_RESTORE_SKIPPED reason=a11y_unbind_not_owned")
''',
    '''        entryPoint().voiceController().endExternalAliceDuck("a11y_unbind")
''',
    "unbind restore",
)
s = once(
    s,
    '''        Log.i(TAG, "BUILD6_MANUAL_DUCK_RESTORE_SKIPPED reason=a11y_destroy_not_owned")
''',
    '''        entryPoint().voiceController().endExternalAliceDuck("a11y_destroy")
''',
    "destroy restore",
)
p.write_text(s)

print("Alice4.8 applied: stable 4.5-style media duck restored + cold description restore path fixed")
