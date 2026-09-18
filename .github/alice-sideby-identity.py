#!/usr/bin/env python3
from pathlib import Path


def swap(path, old, new):
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"missing anchor: {path}: {old}")
    p.write_text(s.replace(old, new, 1))

swap("app/build.gradle.kts", 'applicationId = "com.bydmate.app"', 'applicationId = "com.bydmate.app.alice1"')
swap("app/build.gradle.kts", "versionCode = 61001", "versionCode = 61002")
swap("app/build.gradle.kts", 'versionName = "3.15.2-alice1"', 'versionName = "3.15.2-alice1-sbs"')
swap("app/src/main/AndroidManifest.xml", 'android:name="com.bydmate.app.helper.BINDER"', 'android:name="com.bydmate.app.alice1.helper.BINDER"')
swap("app/src/main/AndroidManifest.xml", 'android:name="com.bydmate.app.action.RECOVER_START"', 'android:name="com.bydmate.app.alice1.action.RECOVER_START"')
swap("app/src/main/kotlin/com/bydmate/app/service/BootReceiver.kt", 'const val ACTION_RECOVER_START = "com.bydmate.app.action.RECOVER_START"', 'const val ACTION_RECOVER_START = "com.bydmate.app.alice1.action.RECOVER_START"')
swap("app/src/main/kotlin/com/bydmate/app/ui/welcome/WelcomeScreen.kt", 'val dilinkCommand = "打开应用com.bydmate.app"', 'val dilinkCommand = "打开应用${context.packageName}"')
swap("app/src/main/kotlin/com/bydmate/app/service/UpdateChecker.kt", '.getBoolean(KEY_AUTO_CHECK, true)', '.getBoolean(KEY_AUTO_CHECK, false)')
print("Alice side-by-side identity patch applied")
