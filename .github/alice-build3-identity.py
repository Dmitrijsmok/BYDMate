#!/usr/bin/env python3
from pathlib import Path


def swap_all(path: str, old: str, new: str) -> None:
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"missing Alice3 identity anchor: {path}: {old!r}")
    p.write_text(s.replace(old, new))


def swap(path: str, old: str, new: str) -> None:
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"missing Alice3 identity anchor: {path}: {old!r}")
    p.write_text(s.replace(old, new, 1))

# Runs after Alice1 side-by-side and Alice2 identity patches.
swap("app/build.gradle.kts", 'applicationId = "com.bydmate.app.alice2"', 'applicationId = "com.bydmate.app.alice3"')
swap("app/build.gradle.kts", "versionCode = 62001", "versionCode = 63001")
swap("app/build.gradle.kts", 'versionName = "3.15.2-alice2-browser"', 'versionName = "3.15.2-alice3-dilink3"')
swap("app/src/main/AndroidManifest.xml", 'android:label="BYDMate Alice 2"', 'android:label="BYDMate Alice 3"')
swap_all("app/src/main/AndroidManifest.xml", "com.bydmate.app.alice2.helper.BINDER", "com.bydmate.app.alice3.helper.BINDER")
swap_all("app/src/main/AndroidManifest.xml", "com.bydmate.app.alice2.action.RECOVER_START", "com.bydmate.app.alice3.action.RECOVER_START")
swap_all("app/src/main/kotlin/com/bydmate/app/service/BootReceiver.kt", "com.bydmate.app.alice2.action.RECOVER_START", "com.bydmate.app.alice3.action.RECOVER_START")

for p in [
    "app/src/main/kotlin/com/bydmate/app/helper/HelperBinderProtocol.kt",
    "app/src/main/kotlin/com/bydmate/app/helper/HelperDaemon.kt",
]:
    swap_all(p, "bydmate_alice2", "bydmate_alice3")
    swap_all(p, "com.bydmate.app.alice2", "com.bydmate.app.alice3")

p = "app/src/main/kotlin/com/bydmate/app/data/autoservice/AdbOnDeviceClient.kt"
swap_all(p, "bydmate_alice2", "bydmate_alice3")
swap_all(p, "com\\.bydmate\\.app\\.alice2", "com\\.bydmate\\.app\\.alice3")

swap_all("app/src/main/kotlin/com/bydmate/app/diagnostics/LogRecorder.kt", "bydmate_alice2:*", "bydmate_alice3:*")
print("Alice Build 3 identity patch applied")
