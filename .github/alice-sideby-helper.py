#!/usr/bin/env python3
from pathlib import Path


def swap(path, old, new):
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"missing anchor: {path}: {old}")
    p.write_text(s.replace(old, new, 1))

p = "app/src/main/kotlin/com/bydmate/app/helper/HelperBinderProtocol.kt"
swap(p, 'const val SERVICE_NAME = "bydmate_helper"', 'const val SERVICE_NAME = "bydmate_alice1"')
swap(p, 'const val PROCESS_NAME = "bydmate_helper"', 'const val PROCESS_NAME = "bydmate_alice1"')
swap(p, 'const val DESCRIPTOR = "com.bydmate.app.helper.IHelper"', 'const val DESCRIPTOR = "com.bydmate.app.alice1.helper.IHelper"')
swap(p, 'const val ACTION_BINDER = "com.bydmate.app.helper.BINDER"', 'const val ACTION_BINDER = "com.bydmate.app.alice1.helper.BINDER"')
swap(p, 'const val APP_PACKAGE = "com.bydmate.app"', 'const val APP_PACKAGE = "com.bydmate.app.alice1"')
swap(p, '"com.bydmate.app/com.bydmate.app.cluster.SteeringWheelKeyService"', '"com.bydmate.app.alice1/com.bydmate.app.cluster.SteeringWheelKeyService"')
swap(p, '"com.bydmate.app/com.bydmate.app.media.MediaSessionListenerService"', '"com.bydmate.app.alice1/com.bydmate.app.media.MediaSessionListenerService"')

p = "app/src/main/kotlin/com/bydmate/app/helper/HelperDaemon.kt"
swap(p, 'private const val LOCK_PATH = "/data/local/tmp/bydmate_helper.lock"', 'private const val LOCK_PATH = "/data/local/tmp/bydmate_alice1.lock"')
q = Path(p)
s = q.read_text().replace('"bydmate_helper"', '"bydmate_alice1"')
s = s.replace('com.bydmate.app.action.RECOVER_START', 'com.bydmate.app.alice1.action.RECOVER_START')
s = s.replace('pidof com.bydmate.app', 'pidof com.bydmate.app.alice1')
s = s.replace('dumpsys package com.bydmate.app', 'dumpsys package com.bydmate.app.alice1')
q.write_text(s)

p = "app/src/main/kotlin/com/bydmate/app/data/autoservice/AdbOnDeviceClient.kt"
swap(p, 'private val PACKAGE_NAME_REGEX = Regex("""^com\\.bydmate\\.app$""")', 'private val PACKAGE_NAME_REGEX = Regex("""^com\\.bydmate\\.app\\.alice1$""")')
swap(p, 'private const val HELPER_PROCESS_NAME = "bydmate_helper"', 'private const val HELPER_PROCESS_NAME = "bydmate_alice1"')
swap(p, 'private const val HELPER_LOG_PATH = "/data/local/tmp/bydmate_helper.log"', 'private const val HELPER_LOG_PATH = "/data/local/tmp/bydmate_alice1.log"')

p = "app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt"
swap(p, 'adbOnDeviceClient.grantUsageStatsAppop("com.bydmate.app")', 'adbOnDeviceClient.grantUsageStatsAppop(packageName)')
swap(p, 'adbOnDeviceClient.grantWriteSecureSettings("com.bydmate.app")', 'adbOnDeviceClient.grantWriteSecureSettings(packageName)')

p = "app/src/main/kotlin/com/bydmate/app/diagnostics/LogRecorder.kt"
swap(p, '"bydmate_helper:*"', '"bydmate_alice1:*"')
print("Alice helper isolation patch applied")
