#!/usr/bin/env python3
from pathlib import Path


def swap_all(path: str, old: str, new: str) -> None:
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"missing Alice4 identity anchor: {path}: {old!r}")
    p.write_text(s.replace(old, new))


def swap(path: str, old: str, new: str) -> None:
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"missing Alice4 identity anchor: {path}: {old!r}")
    p.write_text(s.replace(old, new, 1))

# Runs after Alice3 identity.
swap("app/build.gradle.kts", 'applicationId = "com.bydmate.app.alice3"', 'applicationId = "com.bydmate.app.alice4"')
swap("app/build.gradle.kts", "versionCode = 63001", "versionCode = 64001")
swap("app/build.gradle.kts", 'versionName = "3.15.2-alice3-dilink3"', 'versionName = "3.15.2-alice4-unified"')
swap("app/src/main/AndroidManifest.xml", 'android:label="BYDMate Alice 3"', 'android:label="BYDMate Alice 4"')
swap_all("app/src/main/AndroidManifest.xml", "com.bydmate.app.alice3.helper.BINDER", "com.bydmate.app.alice4.helper.BINDER")
swap_all("app/src/main/AndroidManifest.xml", "com.bydmate.app.alice3.action.RECOVER_START", "com.bydmate.app.alice4.action.RECOVER_START")
swap_all("app/src/main/kotlin/com/bydmate/app/service/BootReceiver.kt", "com.bydmate.app.alice3.action.RECOVER_START", "com.bydmate.app.alice4.action.RECOVER_START")

for p in [
    "app/src/main/kotlin/com/bydmate/app/helper/HelperBinderProtocol.kt",
    "app/src/main/kotlin/com/bydmate/app/helper/HelperDaemon.kt",
]:
    swap_all(p, "bydmate_alice3", "bydmate_alice4")
    swap_all(p, "com.bydmate.app.alice3", "com.bydmate.app.alice4")

p = "app/src/main/kotlin/com/bydmate/app/data/autoservice/AdbOnDeviceClient.kt"
swap_all(p, "bydmate_alice3", "bydmate_alice4")
swap_all(p, "com\\.bydmate\\.app\\.alice3", "com\\.bydmate\\.app\\.alice4")

swap_all("app/src/main/kotlin/com/bydmate/app/diagnostics/LogRecorder.kt", "bydmate_alice3:*", "bydmate_alice4:*")
print("Alice Build 4 identity patch applied")
