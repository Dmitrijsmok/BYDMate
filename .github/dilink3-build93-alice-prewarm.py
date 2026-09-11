#!/usr/bin/env python3
from pathlib import Path
import re


def once(s, old, new, name):
    if old not in s:
        raise SystemExit(f"Build93 anchor missing: {name}")
    return s.replace(old, new, 1)

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 60042", "versionCode = 60043", "versionCode")
s = once(s, 'versionNameSuffix = "-dilink3-production-build92"', 'versionNameSuffix = "-dilink3-production-build93"', "versionName")
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = once(s, 'android:label="BYDMate DiLink3 Build92"', 'android:label="BYDMate DiLink3 Build93"', "label")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text().replace('SectionHeader(text = "Assistant Lab · Build92")', 'SectionHeader(text = "Assistant Lab · Build93")', 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# Assistant Lab / Yandex Alice routing.
# Field log Build92 proved that alice_input_quarknyx exists only AFTER BroAliceActivity is open.
# On a cold browser, the working entry is bro_omnibox_button_microphone_inactive.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text().replace("Build92", "Build93")

s = once(s,
'''    private const val EXACT_ALICE_ID = "com.yandex.browser:id/alice_input_quarknyx"
    private const val EXACT_ALICE_DESC = "голосовой помощник"
    private const val MIN_ALICE_SCORE = 4000
''',
'''    private const val EXACT_ALICE_ID = "com.yandex.browser:id/alice_input_quarknyx"
    private const val EXACT_ALICE_DESC = "голосовой помощник"
    private const val COLD_ALICE_ID = "com.yandex.browser:id/bro_omnibox_button_microphone_inactive"
    private const val COLD_ALICE_DESC = "активировать голосовой поиск"
    private const val MIN_ALICE_SCORE = 4000
''', "Alice node constants")

start = s.index('    private fun score(node: AccessibilityNodeInfo, context: Context): Int {')
end = s.index('\n    }\n}', start) + len('\n    }')
new_score = '''    private fun score(node: AccessibilityNodeInfo, context: Context): Int {
        val id = node.viewIdResourceName.orEmpty().lowercase(Locale.getDefault())
        val desc = node.contentDescription?.toString().orEmpty().lowercase(Locale.getDefault())
        val text = node.text?.toString().orEmpty().lowercase(Locale.getDefault())
        if (id == EXACT_ALICE_ID.lowercase(Locale.getDefault()) && node.isClickable) return 10000
        if (id == COLD_ALICE_ID.lowercase(Locale.getDefault()) && node.isClickable) return 9500
        if (desc.contains(EXACT_ALICE_DESC) && node.isClickable) return 8000
        if (desc.contains(COLD_ALICE_DESC) && node.isClickable) return 7600
        if (id.contains("bro_omnibox_button_microphone") && node.isClickable) return 7200
        if (id.contains("allou_dialog_text") || text.contains("а вот и алиса")) return Int.MIN_VALUE
        return Int.MIN_VALUE
    }'''
s = s[:start] + new_score + s[end:]

# A short-lived stock-assistant guard is active only while an explicit Alice handoff / boot warm
# is in progress. It does not disable or force-stop the BYD package; Accessibility just closes its
# transient window if it steals foreground during the Yandex voice handoff.
s = once(s,
'''    @Volatile var aliceTestMode: Boolean = false
        private set
''',
'''    @Volatile var aliceTestMode: Boolean = false
        private set
    @Volatile private var aliceStockGuardUntilElapsed: Long = 0L
    @Volatile private var lastStockDismissElapsed: Long = 0L
''', "stock guard state")

insert_after = '''    fun toggleAliceTestMode(context: Context): Boolean {
        if (!active) start(context)
        aliceTestMode = !aliceTestMode
        armedTarget = null
        consume304UntilUp = false
        add("ALICE TEST MODE=${if (aliceTestMode) "ON" else "OFF"}")
        return aliceTestMode
    }
'''
guard_methods = insert_after + '''
    fun armAliceStockGuard(durationMs: Long = 15_000L) {
        aliceStockGuardUntilElapsed = android.os.SystemClock.elapsedRealtime() + durationMs
        add("ALICE stock-assistant guard armed ${durationMs}ms")
    }

    fun shouldDismissStockAssistant(event: AccessibilityEvent): Boolean {
        if (event.packageName?.toString() != "com.byd.vrassistant") return false
        val now = android.os.SystemClock.elapsedRealtime()
        if (now >= aliceStockGuardUntilElapsed) return false
        if (now - lastStockDismissElapsed < 650L) return false
        lastStockDismissElapsed = now
        add("ALICE guard: stock BYD assistant window intercepted")
        return true
    }
'''
s = once(s, insert_after, guard_methods, "stock guard methods")

# Generalize the Yandex helper so the normal route and the boot prewarm use the same field-proven
# accessibility click sequence.
s = once(s,
'''    private fun launchYandexBrowserAlice(context: Context, pm: PackageManager, app: InstalledAssistant) {
        AssistantLabTrace.add("YANDEX route Build93: exact toolbar id=alice_input_quarknyx")
''',
'''    private fun launchYandexBrowserAlice(
        context: Context,
        pm: PackageManager,
        app: InstalledAssistant,
        backgroundAfterClick: Boolean = false,
    ) {
        AssistantLabTrace.armAliceStockGuard()
        AssistantLabTrace.add("YANDEX route Build93: warm=id=alice_input_quarknyx cold=id=bro_omnibox_button_microphone_inactive")
''', "Yandex launcher signature")

# The prior Build92 text may still say Build92 if the global replacement above hit a different
# occurrence first; normalize defensively.
s = s.replace('YANDEX route Build92: exact toolbar id=alice_input_quarknyx',
              'YANDEX route Build93: warm=id=alice_input_quarknyx cold=id=bro_omnibox_button_microphone_inactive')

# When warm-path click succeeds, optionally return Yandex to background after Alice has initialized.
s = once(s,
'''        if (YandexAliceAccessibility.tryClickToolbarAlice(context)) {
            AssistantLabTrace.add("YANDEX exact Alice clicked on warm path")
            scheduleForegroundChecks(context, AssistantTarget.ALICE)
            return
        }
''',
'''        if (YandexAliceAccessibility.tryClickToolbarAlice(context)) {
            AssistantLabTrace.add("YANDEX Alice entry clicked on warm path")
            scheduleForegroundChecks(context, AssistantTarget.ALICE)
            if (backgroundAfterClick) scheduleYandexToBackground(context, 1_800L)
            return
        }
''', "warm click background")

# After any delayed click (cold browser mic or already-open Alice button), boot prewarm backgrounds
# Yandex so the driver gets the normal launcher/UI while Alice stays initialized behind it.
s = once(s,
'''                    if (ok) {
                        clicked[0] = true
                        AssistantLabTrace.add("YANDEX toolbar Alice clicked at +${delay}ms")
                    }
''',
'''                    if (ok) {
                        clicked[0] = true
                        AssistantLabTrace.add("YANDEX Alice entry clicked at +${delay}ms")
                        if (backgroundAfterClick) scheduleYandexToBackground(context, 1_800L)
                    }
''', "delayed click background")

# Insert a background-only prewarm entry point and a conservative exported wakeup-service probe.
# The service probe is non-destructive; the browser+Accessibility path remains the reliable fallback.
anchor = '''    fun openOfficialInstall(context: Context, target: AssistantTarget) {
'''
prewarm = '''    private val build93WarmOnce = java.util.concurrent.atomic.AtomicBoolean(false)

    fun warmYandexAliceAfterStartup(context: Context) {
        val app = resolveInstalled(context, AssistantTarget.ALICE) ?: return
        if (app.packageName != YandexAliceAccessibility.PACKAGE) return
        if (!build93WarmOnce.compareAndSet(false, true)) return

        android.util.Log.i("AssistantLab", "Build93 Alice prewarm starting")
        AssistantLabTrace.armAliceStockGuard(20_000L)

        // This exported service exists in the field package dump. Starting it may be enough to keep
        // Yandex' wake-word path resident; failure is harmless and the browser warm fallback follows.
        runCatching {
            val wake = Intent().setComponent(
                android.content.ComponentName(
                    YandexAliceAccessibility.PACKAGE,
                    "com.yandex.browser.speech.alice.wakeup.AliceRealmeWakeupService",
                )
            )
            context.startService(wake)
            android.util.Log.i("AssistantLab", "Build93 AliceRealmeWakeupService start requested")
        }.onFailure {
            android.util.Log.w("AssistantLab", "Build93 wakeup service start failed: ${it.message}")
        }

        Handler(Looper.getMainLooper()).postDelayed({
            launchYandexBrowserAlice(context.applicationContext, context.packageManager, app, backgroundAfterClick = true)
        }, 1_200L)
    }

    private fun scheduleYandexToBackground(context: Context, delayMs: Long) {
        Handler(Looper.getMainLooper()).postDelayed({
            runCatching {
                val home = Intent(Intent.ACTION_MAIN).apply {
                    addCategory(Intent.CATEGORY_HOME)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION)
                }
                context.startActivity(home)
                AssistantLabTrace.add("YANDEX prewarm complete -> HOME; Alice remains background-warm")
                android.util.Log.i("AssistantLab", "Build93 Alice prewarm complete; Yandex moved behind HOME")
            }.onFailure {
                AssistantLabTrace.add("YANDEX prewarm HOME failed ${it.javaClass.simpleName}: ${it.message}")
            }
        }, delayMs)
    }

'''
s = once(s, anchor, prewarm + anchor, "prewarm functions")

# Remove standalone Alice app from the visible right side of the lab. Keep the enum internally so
# older diagnostic code compiles, but do not present or dump it in the normal Build93 workflow.
s = s.replace('AssistantTarget.entries.forEach { target ->',
              'AssistantTarget.entries.filter { it != AssistantTarget.ALICE_APP }.forEach { target ->', 1)
s = s.replace('listOf("com.yandex.browser", "com.yandex.aliceapp").forEach { pkg ->',
              'listOf("com.yandex.browser").forEach { pkg ->', 1)

ui_old = '''        val alice = actionButton(context, "Alice") { launchOrInstall(context, AssistantTarget.ALICE) }
        val gpt = actionButton(context, "Alice app") { launchOrInstall(context, AssistantTarget.ALICE_APP) }
        aliceButton = alice
        gptButton = gpt
        content.addView(buttonRow(context, alice, gpt))
'''
ui_new = '''        val alice = actionButton(context, "Alice / Yandex") { launchOrInstall(context, AssistantTarget.ALICE) }
        aliceButton = alice
        gptButton = null
        content.addView(buttonRow(context, alice))
'''
s = once(s, ui_old, ui_new, "single Alice app row")

pattern = re.compile(
    r'''        content\.addView\(buttonRow\(context,\n            actionButton\(context, "РУЛЬ → ALICE \(1 раз\)"\) \{.*?        \)\)\n\n        val scroll = ScrollView\(context\)''',
    re.S,
)
replacement = '''        content.addView(buttonRow(context,
            actionButton(context, "РУЛЬ → ALICE (1 раз)") {
                if (!AssistantLabLauncher.isInstalled(context, AssistantTarget.ALICE)) {
                    AssistantLabLauncher.openOfficialInstall(context, AssistantTarget.ALICE)
                } else {
                    AssistantLabTrace.armSteering(context, AssistantTarget.ALICE)
                    AssistantLabTrace.armAliceStockGuard()
                    minimize(context)
                    Toast.makeText(context, "Следующее нажатие микрофона → Alice", Toast.LENGTH_SHORT).show()
                }
                refresh()
            },
        ))

        val scroll = ScrollView(context)'''
s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit("Build93 steering-row regex anchor missing")

# Remove the standalone-app status line and button refresh from visible UI.
s = re.sub(r'\n\s*append\("\\nStandalone Alice app: "\).*?\n', '\n', s, count=1)
s = re.sub(r'\n\s*gptButton\?\.text = .*?\n', '\n', s, count=1)

p.write_text(s)

# ---------------------------------------------------------------------------
# Accessibility: while Alice handoff is armed, immediately back out of a stock BYD assistant
# window if it steals the foreground. This is transient; package state is never disabled.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
old = '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event != null) AssistantLabTrace.onAccessibilityEvent(event)
        NavA11yFeed.onEvent(this, event)
    }
'''
new = '''    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event != null) {
            AssistantLabTrace.onAccessibilityEvent(event)
            if (AssistantLabTrace.shouldDismissStockAssistant(event)) {
                val closed = performGlobalAction(GLOBAL_ACTION_BACK)
                AssistantLabTrace.add("ALICE guard BACK stock assistant result=$closed")
            }
        }
        NavA11yFeed.onEvent(this, event)
    }
'''
s = once(s, old, new, "stock assistant transient close")
p.write_text(s)

# ---------------------------------------------------------------------------
# Process startup: after the existing A11Y self-heal, prewarm Yandex/Alice once per BYDMate process.
# Gated by the existing voice master switch so users who turned voice ownership OFF keep stock BYD.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt")
s = p.read_text()
old = '''        serviceScope.launch { ensureStarServiceRunning("startup") }
        serviceScope.launch {
            while (true) {
'''
new = '''        serviceScope.launch {
            ensureStarServiceRunning("startup")
            if (voiceGate.isEnabled()) {
                // Give Android 10 a short moment to finish binding SteeringWheelKeyService. The
                // Yandex click helper itself keeps retrying, so this is only startup smoothing.
                kotlinx.coroutines.delay(1_500L)
                com.bydmate.app.assistantlab.AssistantLabLauncher.warmYandexAliceAfterStartup(applicationContext)
            }
        }
        serviceScope.launch {
            while (true) {
'''
s = once(s, old, new, "startup Alice prewarm")
p.write_text(s)

print("Build93 applied: cold Yandex mic route + background Alice prewarm + transient stock guard + simplified lab")
