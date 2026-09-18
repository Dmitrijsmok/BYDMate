#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice4.4 anchor missing: {label}")
    return text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 1) Identity: same package, monotonic versionCode for in-place update.
# ---------------------------------------------------------------------------
p = Path('app/build.gradle.kts')
s = p.read_text()
s = replace_once(s, 'versionCode = 64004', 'versionCode = 64005', 'versionCode')
s = replace_once(
    s,
    'versionName = "3.15.2-alice4.3-stable"',
    'versionName = "3.15.2-alice4.4-silent-recovery"',
    'versionName',
)
p.write_text(s)

# ---------------------------------------------------------------------------
# 2) Boot prewarm: NO Browser Activity, NO Accessibility clicks, NO Alice tone.
#    Only ask Yandex' exported Alice wakeup service to start. If the service-only
#    warmup is not enough on this firmware, first real steering press simply pays
#    the normal cold Browser/Alice path; startup remains invisible.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt')
s = p.read_text()
old = '''        serviceScope.launch {
            val voicePrefs = getSharedPreferences("voice", Context.MODE_PRIVATE)
            if (!voicePrefs.getBoolean("alice_native_takeover", false)) return@launch
            val bootPrefs = getSharedPreferences(BootReceiver.PREFS_NAME, Context.MODE_PRIVATE)
            val action = bootPrefs.getString(BootReceiver.KEY_LAST_BOOT_ACTION, "").orEmpty()
            val bootTs = bootPrefs.getLong(BootReceiver.KEY_LAST_BOOT_TS, 0L)
            val realBoot = action == Intent.ACTION_BOOT_COMPLETED ||
                action == "android.intent.action.QUICKBOOT_POWERON"
            val recent = bootTs > 0L && System.currentTimeMillis() - bootTs in 0L..60_000L
            val marker = voicePrefs.getLong("alice4_2_last_prewarm_boot_ts", 0L)
            if (!realBoot || !recent || marker == bootTs) return@launch
            voicePrefs.edit().putLong("alice4_2_last_prewarm_boot_ts", bootTs).apply()
            delay(5_000L)
            repeat(5) { attempt ->
                if (com.bydmate.app.cluster.SteeringWheelKeyService.requestBootAlicePrewarm()) {
                    Log.i(TAG, "Alice4.2 boot prewarm requested attempt=${attempt + 1}")
                    return@launch
                }
                delay(1_500L)
            }
            Log.w(TAG, "Alice4.2 boot prewarm skipped: accessibility not bound")
        }
'''
new = '''        serviceScope.launch {
            val voicePrefs = getSharedPreferences("voice", Context.MODE_PRIVATE)
            if (!voicePrefs.getBoolean("alice_native_takeover", false)) return@launch
            val bootPrefs = getSharedPreferences(BootReceiver.PREFS_NAME, Context.MODE_PRIVATE)
            val action = bootPrefs.getString(BootReceiver.KEY_LAST_BOOT_ACTION, "").orEmpty()
            val bootTs = bootPrefs.getLong(BootReceiver.KEY_LAST_BOOT_TS, 0L)
            val realBoot = action == Intent.ACTION_BOOT_COMPLETED ||
                action == "android.intent.action.QUICKBOOT_POWERON"
            val recent = bootTs > 0L && System.currentTimeMillis() - bootTs in 0L..60_000L
            val marker = voicePrefs.getLong("alice4_4_last_silent_prewarm_boot_ts", 0L)
            if (!realBoot || !recent || marker == bootTs) return@launch
            voicePrefs.edit().putLong("alice4_4_last_silent_prewarm_boot_ts", bootTs).apply()
            delay(5_000L)
            runCatching {
                val wake = Intent().setComponent(
                    ComponentName(
                        "com.yandex.browser",
                        "com.yandex.browser.speech.alice.wakeup.AliceRealmeWakeupService",
                    )
                )
                startService(wake)
                Log.i(TAG, "ALICE4_4_SILENT_PREWARM requested=true")
            }.onFailure {
                Log.w(TAG, "ALICE4_4_SILENT_PREWARM failed=${it.javaClass.simpleName}:${it.message}")
            }
        }
'''
s = replace_once(s, old, new, 'replace visible boot prewarm with service-only prewarm')

# ---------------------------------------------------------------------------
# 3) Startup recovery: after an APK install/update Android 10 can leave our A11Y
#    component enabled in Settings but not actually bound. Retry helper bootstrap
#    while ADB is warming up, re-assert Accessibility as soon as the daemon exists,
#    then hand a genuine Q mBindingServices stall to the existing force-stop/rebind
#    recovery. No head-unit reboot required.
# ---------------------------------------------------------------------------
anchor = '        serviceScope.launch { ensureStarServiceRunning("startup") }\n'
extra = anchor + '''        serviceScope.launch {
            val voicePrefs = getSharedPreferences("voice", Context.MODE_PRIVATE)
            val recoveryNeeded = voicePrefs.getBoolean("alice_native_takeover", false) ||
                voicePrefs.getBoolean(SettingsRepository.KEY_VOICE_ENABLED, false)
            if (!recoveryNeeded) return@launch

            repeat(10) { attempt ->
                if (com.bydmate.app.cluster.SteeringWheelKeyService.isConnected) {
                    Log.i(TAG, "ALICE4_4_A11Y_RECOVERY ready attempt=${attempt + 1}")
                    return@launch
                }

                val helperReady = runCatching { helperBootstrap.ensureRunning() }.getOrDefault(false)
                Log.i(TAG, "ALICE4_4_A11Y_RECOVERY helperReady=$helperReady attempt=${attempt + 1}")
                if (helperReady) {
                    val reasserted = runCatching { helperClient.enableAccessibilityService() }.getOrDefault(false)
                    Log.i(TAG, "ALICE4_4_A11Y_RECOVERY reasserted=$reasserted attempt=${attempt + 1}")
                    delay(1_500L)
                    if (com.bydmate.app.cluster.SteeringWheelKeyService.isConnected) {
                        Log.i(TAG, "ALICE4_4_A11Y_RECOVERY connected attempt=${attempt + 1}")
                        return@launch
                    }
                    // Reuse the existing Android-10 stuck-binding detector/recovery.
                    ensureStarServiceRunning("alice4.4-install-recovery:${attempt + 1}")
                    if (com.bydmate.app.cluster.SteeringWheelKeyService.isConnected) return@launch
                }
                delay(3_000L)
            }
            Log.w(TAG, "ALICE4_4_A11Y_RECOVERY exhausted without connection")
        }
'''
s = replace_once(s, anchor, extra, 'startup Accessibility recovery loop')
p.write_text(s)

# ---------------------------------------------------------------------------
# 4) Toggle-time recovery: when takeover is enabled in Settings, don't wait for
#    a reboot or for a later service restart. Retry the helper in-place; on Q, if
#    the component is listed but still unbound, invoke the existing daemon recovery.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt')
s = p.read_text()
old = '''            helperClient.setAppHidden("com.byd.autovoice", disabled)
            helperClient.setAppHidden("com.byd.vrassistant", disabled)
'''
new = old + '''            if (disabled) {
                runCatching { TrackingService.start(appContext) }
                repeat(8) { attempt ->
                    if (com.bydmate.app.cluster.SteeringWheelKeyService.isConnected) {
                        Log.i(TAG, "Alice4.4 toggle A11Y already connected attempt=${attempt + 1}")
                        return@launch
                    }
                    val helperReady = runCatching { helperBootstrap.ensureRunning() }.getOrDefault(false)
                    Log.i(TAG, "Alice4.4 toggle A11Y helperReady=$helperReady attempt=${attempt + 1}")
                    if (helperReady) {
                        val reasserted = runCatching { helperClient.enableAccessibilityService() }.getOrDefault(false)
                        Log.i(TAG, "Alice4.4 toggle A11Y reasserted=$reasserted attempt=${attempt + 1}")
                        delay(1_500L)
                        if (com.bydmate.app.cluster.SteeringWheelKeyService.isConnected) return@launch

                        if (android.os.Build.VERSION.SDK_INT <= 29) {
                            val listed = runCatching {
                                android.provider.Settings.Secure.getString(
                                    appContext.contentResolver,
                                    "enabled_accessibility_services",
                                ).orEmpty().contains(appContext.packageName)
                            }.getOrDefault(false)
                            if (listed) {
                                Log.w(TAG, "Alice4.4 toggle A11Y listed-but-unbound; requesting recovery")
                                runCatching { helperClient.recoverAccessibilityService() }
                                return@launch
                            }
                        }
                    }
                    delay(2_500L)
                }
                Log.w(TAG, "Alice4.4 toggle A11Y recovery exhausted")
            }
'''
s = replace_once(s, old, new, 'toggle-time Accessibility recovery')
p.write_text(s)

print('Alice4.4 applied: invisible Yandex service-only prewarm + install/update A11Y recovery')
