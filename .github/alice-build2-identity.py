#!/usr/bin/env python3
from pathlib import Path


def swap(path: str, old: str, new: str, count: int = 1) -> None:
    p = Path(path)
    s = p.read_text()
    actual = s.count(old)
    if actual < count:
        raise SystemExit(f"missing Alice2 identity anchor: {path}: {old!r} (found {actual}, need {count})")
    p.write_text(s.replace(old, new, count))


def swap_all(path: str, old: str, new: str) -> None:
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"missing Alice2 identity anchor: {path}: {old!r}")
    p.write_text(s.replace(old, new))


# This patch runs AFTER alice-build1-patch.py + the Alice1 side-by-side patches.
# Give Build 2 its own Android identity because GitHub debug signing is not stable
# enough to rely on updating the previously downloaded Alice1 APK.
swap("app/build.gradle.kts", 'applicationId = "com.bydmate.app.alice1"', 'applicationId = "com.bydmate.app.alice2"')
swap("app/build.gradle.kts", "versionCode = 61002", "versionCode = 62001")
swap("app/build.gradle.kts", 'versionName = "3.15.2-alice1-sbs"', 'versionName = "3.15.2-alice2-browser"')
swap("app/src/main/AndroidManifest.xml", 'android:label="BYDMate Alice 1"', 'android:label="BYDMate Alice 2"')
swap_all("app/src/main/AndroidManifest.xml", "com.bydmate.app.alice1.helper.BINDER", "com.bydmate.app.alice2.helper.BINDER")
swap_all("app/src/main/AndroidManifest.xml", "com.bydmate.app.alice1.action.RECOVER_START", "com.bydmate.app.alice2.action.RECOVER_START")

swap_all(
    "app/src/main/kotlin/com/bydmate/app/service/BootReceiver.kt",
    "com.bydmate.app.alice1.action.RECOVER_START",
    "com.bydmate.app.alice2.action.RECOVER_START",
)

p = "app/src/main/kotlin/com/bydmate/app/helper/HelperBinderProtocol.kt"
swap_all(p, "bydmate_alice1", "bydmate_alice2")
swap_all(p, "com.bydmate.app.alice1", "com.bydmate.app.alice2")

p = "app/src/main/kotlin/com/bydmate/app/helper/HelperDaemon.kt"
swap_all(p, "bydmate_alice1", "bydmate_alice2")
swap_all(p, "com.bydmate.app.alice1", "com.bydmate.app.alice2")

p = "app/src/main/kotlin/com/bydmate/app/data/autoservice/AdbOnDeviceClient.kt"
swap_all(p, "bydmate_alice1", "bydmate_alice2")
swap_all(p, "com\\.bydmate\\.app\\.alice1", "com\\.bydmate\\.app\\.alice2")

swap_all(
    "app/src/main/kotlin/com/bydmate/app/diagnostics/LogRecorder.kt",
    "bydmate_alice1:*",
    "bydmate_alice2:*",
)

print("Alice Build 2 identity patch applied")
