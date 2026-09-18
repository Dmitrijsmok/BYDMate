#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice4.7 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Identity: 4.7 is the monotonic successor of the real 4.6 chain.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64007", "versionCode = 64008", "versionCode")
s = once(
    s,
    'versionName = "3.15.2-alice4.6-audiofocus-vrblock"',
    'versionName = "3.15.2-alice4.7-build95-recovery"',
    "versionName",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Build95 recovery rule: absolutely no Yandex/Alice boot prewarm.
#    Keep the silent Accessibility/helper recovery from 4.4/4.5/4.6, but do not
#    start AliceRealmeWakeupService at boot. Physical testing showed that this
#    supposedly silent wake can become visible/audible on the target head unit.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt")
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
new = '''        // Alice4.7 / Build95 recovery: never touch Yandex at boot.
        // Accessibility/helper recovery remains active and silent.
        Log.i(TAG, "BUILD7_BOOT_PREWARM_DISABLED source=build95_recovery")
'''
s = once(s, old, new, "disable Yandex boot prewarm")
p.write_text(s)


# ---------------------------------------------------------------------------
# 3) Preserve every vrassistant blocking layer already present in 4.6 and make
#    the last-resort Accessibility guard as aggressive as Build95.
#
#    Layers inherited from 4.6 and intentionally left intact:
#      A. Settings/startup sync calls setAppHidden(com.byd.vrassistant, ...).
#      B. HelperDaemon executes reversible pm disable-user / pm enable.
#      C. 4.5 helper-ready recovery reasserts the hidden state after update/boot.
#      D. 4.6 logs the real shell result (BUILD6_VRASSISTANT_STATE/REASSERT).
#      E. 304/327 interception prevents normal firmware routing to stock voice.
#
#    Build95 adds the final belt-and-suspenders layer: if vrassistant emits ANY
#    Accessibility event while takeover is enabled, immediately BACK out. Do not
#    restrict this to TYPE_WINDOW_STATE_CHANGED; debounce repeated events at 700ms.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
s = once(
    s,
    "    private var aliceSessionListening = false\n",
    "    private var aliceSessionListening = false\n"
    "    private var lastStockAssistantBackElapsed = 0L\n",
    "Build95 stock assistant guard state",
)
old = '''        if (nativeTakeover && eventPkg == "com.byd.vrassistant" &&
            event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            val closed = performGlobalAction(GLOBAL_ACTION_BACK)
            Log.w(TAG, "ALICE4_5_VRASSISTANT_WINDOW_BLOCKED back=$closed")
        }
'''
new = '''        if (nativeTakeover && eventPkg == "com.byd.vrassistant") {
            val now = android.os.SystemClock.elapsedRealtime()
            if (now - lastStockAssistantBackElapsed >= 700L) {
                lastStockAssistantBackElapsed = now
                val closed = performGlobalAction(GLOBAL_ACTION_BACK)
                Log.w(
                    TAG,
                    "BUILD7_STOCK_ASSISTANT_BACK eventType=${event.eventType} result=$closed"
                )
            }
            return
        }
'''
s = once(s, old, new, "Build95 any-event vrassistant BACK guard")
p.write_text(s)


print("Alice4.7 applied: 4.6 preserved + no boot prewarm + Build95 any-event stock-assistant guard")
