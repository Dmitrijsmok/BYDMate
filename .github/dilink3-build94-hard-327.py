#!/usr/bin/env python3
from pathlib import Path


def once(s, old, new, name):
    if old not in s:
        raise SystemExit(f"Build94 anchor missing: {name}")
    return s.replace(old, new, 1)

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 60043", "versionCode = 60044", "versionCode")
s = once(s, 'versionNameSuffix = "-dilink3-production-build93"', 'versionNameSuffix = "-dilink3-production-build94"', "versionName")
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = once(s, 'android:label="BYDMate DiLink3 Build93"', 'android:label="BYDMate DiLink3 Build94"', "label")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text().replace('SectionHeader(text = "Assistant Lab · Build93")', 'SectionHeader(text = "Assistant Lab · Build94")', 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# Alice hard companion-key blocker.
# Field Build93 log proved the race precisely:
#   304 consumed by BYDMate -> Yandex launch -> 327 down/up -> BYD voice.request.start.
# The old Build70 gate depends on voiceEnabled. Alice routing must not depend on that stale/mutated
# setting, so when Alice owns 304 we arm an independent short-lived 327 gate. Persistent Alice test
# mode also consumes 327 unconditionally. This executes synchronously in A11Y key filtering before
# the key can reach com.byd.vrassistant.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text().replace("Build93", "Build94")

s = once(
    s,
    '''    @Volatile private var aliceStockGuardUntilElapsed: Long = 0L
    @Volatile private var lastStockDismissElapsed: Long = 0L
''',
    '''    @Volatile private var aliceStockGuardUntilElapsed: Long = 0L
    @Volatile private var lastStockDismissElapsed: Long = 0L
    @Volatile private var aliceHard327UntilElapsed: Long = 0L
''',
    "hard 327 state",
)

anchor = '''    fun armAliceStockGuard(durationMs: Long = 15_000L) {
        aliceStockGuardUntilElapsed = android.os.SystemClock.elapsedRealtime() + durationMs
        add("ALICE stock-assistant guard armed ${durationMs}ms")
    }

'''
insert = anchor + '''    fun armAliceHard327Block(durationMs: Long = 4_000L) {
        val until = android.os.SystemClock.elapsedRealtime() + durationMs
        if (until > aliceHard327UntilElapsed) aliceHard327UntilElapsed = until
        add("ALICE HARD 327 gate armed ${durationMs}ms")
    }

    fun shouldHardBlockStock327(event: KeyEvent): Boolean {
        if (event.keyCode != 327) return false
        val now = android.os.SystemClock.elapsedRealtime()
        val block = aliceTestMode || now < aliceHard327UntilElapsed
        if (!block) return false
        add("ALICE HARD 327 BLOCK action=${event.action} scan=${event.scanCode}; stopped before BYD dispatch")
        return true
    }

'''
s = once(s, anchor, insert, "hard 327 methods")

s = once(
    s,
    '''        if (oneShot != null) armedTarget = null
        consume304UntilUp = true
        add("KEY 304 route=${if (oneShot != null) "one-shot" else "alice-test"} target=${target.title}")
''',
    '''        if (oneShot != null) armedTarget = null
        consume304UntilUp = true
        if (target == AssistantTarget.ALICE) {
            // The same physical steering press emits the companion 327 after 304 UP. Arm before
            // posting the Yandex launch so BYD never gets a chance to start its native assistant.
            armAliceHard327Block()
            armAliceStockGuard()
        }
        add("KEY 304 route=${if (oneShot != null) "one-shot" else "alice-test"} target=${target.title}")
''',
    "arm hard block on Alice 304",
)

p.write_text(s)

# Synchronous blocker must run before both Assistant Lab launch routing and the historical Build70
# voiceEnabled-dependent gate.
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
s = once(
    s,
    '''        AssistantLabTrace.onKeyEvent(event)
        if (AssistantLabTrace.maybeHandleSteering(applicationContext, event)) {
''',
    '''        AssistantLabTrace.onKeyEvent(event)
        if (AssistantLabTrace.shouldHardBlockStock327(event)) {
            AssistantLabTrace.add("STEERING hard-consumed 327 before stock assistant dispatch")
            return true
        }
        if (AssistantLabTrace.maybeHandleSteering(applicationContext, event)) {
''',
    "synchronous hard 327 gate",
)
p.write_text(s)

# ---------------------------------------------------------------------------
# Prewarm only on actual tablet/head-unit boot, not every TrackingService process start.
# Build93 caused Yandex Browser to pop up whenever BYDMate itself was opened. Remove that behavior.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt")
s = p.read_text()
s = once(
    s,
    '''        serviceScope.launch {
            ensureStarServiceRunning("startup")
            if (voiceGate.isEnabled()) {
                // Give Android 10 a short moment to finish binding SteeringWheelKeyService. The
                // Yandex click helper itself keeps retrying, so this is only startup smoothing.
                kotlinx.coroutines.delay(1_500L)
                com.bydmate.app.assistantlab.AssistantLabLauncher.warmYandexAliceAfterStartup(applicationContext)
            }
        }
''',
    '''        serviceScope.launch { ensureStarServiceRunning("startup") }
''',
    "remove app-open prewarm",
)
p.write_text(s)

# BootReceiver already starts TrackingService immediately for the 327 blocker. On a genuine boot,
# schedule Alice prewarm after A11Y had time to bind. Do not do this on ACTION_USER_PRESENT, package
# replacement, or ordinary app starts.
p = Path("app/src/main/kotlin/com/bydmate/app/service/BootReceiver.kt")
s = p.read_text()
needle = '''                Log.i(TAG, "Build92 boot guard: TrackingService started immediately for 327 blocker")
'''
replacement = needle + '''                if (
                    intent.action == Intent.ACTION_BOOT_COMPLETED ||
                    intent.action == "android.intent.action.QUICKBOOT_POWERON"
                ) {
                    android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                        runCatching {
                            com.bydmate.app.assistantlab.AssistantLabLauncher
                                .warmYandexAliceAfterStartup(context.applicationContext)
                            Log.i(TAG, "Build94 boot-only Alice prewarm requested")
                        }.onFailure {
                            Log.w(TAG, "Build94 boot-only Alice prewarm failed: ${it.message}", it)
                        }
                    }, 3_000L)
                }
'''
s = once(s, needle, replacement, "boot-only prewarm")
p.write_text(s)

print("Build94 applied: synchronous Alice 327 blocker + boot-only Yandex prewarm")
