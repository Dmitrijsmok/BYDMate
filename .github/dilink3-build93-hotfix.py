#!/usr/bin/env python3
from pathlib import Path


def once(s, old, new, name):
    if old not in s:
        raise SystemExit(f"Build93 hotfix anchor missing: {name}")
    return s.replace(old, new, 1)

p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text()

# Build93 is an Alice-first field build: after APK replacement / reboot the very first 304 must
# route to Yandex Alice without the user reopening Assistant Lab or toggling a test switch.
s = once(
    s,
    '''    @Volatile var aliceTestMode: Boolean = false
        private set
''',
    '''    @Volatile var aliceTestMode: Boolean = true
        private set
''',
    "Alice steering default ON",
)

# TXT/ZIP export proved unnecessary on this head unit. Keep SHARE TEXT (the reliable path) and
# trace persistence, but remove the two visible file-export buttons from the compact lab.
s = once(
    s,
    '''        content.addView(buttonRow(context,
            actionButton(context, "SAVE TXT") { AssistantLabTrace.saveTxt(context) },
            actionButton(context, "SAVE ZIP") { AssistantLabTrace.saveZip(context) },
        ))

''',
    '',
    "remove TXT/ZIP buttons",
)

# Field log captured the actual Yandex internal action that opens BroAliceActivity. Probe that
# action first. BroAliceActivity itself is non-exported, so this is deliberately best-effort:
# start() catches SecurityException/ActivityNotFound and the existing service+browser+A11Y fallback
# remains intact.
anchor = '''    private val build93WarmOnce = java.util.concurrent.atomic.AtomicBoolean(false)

    fun warmYandexAliceAfterStartup(context: Context) {
'''
helper = '''    private fun tryOpenAliceAction(context: Context): Boolean {
        val intent = Intent("com.yandex.alicenger.Alice.OPEN").apply {
            setPackage(YandexAliceAccessibility.PACKAGE)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION)
        }
        val matches = runCatching {
            context.packageManager.queryIntentActivities(intent, 0)
        }.getOrDefault(emptyList())
        val summary = matches.take(8).joinToString { "${it.activityInfo.name}:exported=${it.activityInfo.exported}" }
        AssistantLabTrace.add("YANDEX Alice.OPEN probe matches=${matches.size} $summary")
        android.util.Log.i("AssistantLab", "Build93 Alice.OPEN probe matches=${matches.size} $summary")
        val ok = start(context, intent, "yandex-alice-open-action")
        android.util.Log.i("AssistantLab", "Build93 Alice.OPEN start=$ok")
        return ok
    }

    private val build93WarmOnce = java.util.concurrent.atomic.AtomicBoolean(false)

    fun warmYandexAliceAfterStartup(context: Context) {
'''
s = once(s, anchor, helper, "Alice.OPEN probe helper")

# Normal steering route: if Alice is already warm, Accessibility wins immediately. Otherwise try
# the exact field-observed Alice.OPEN action before falling back to opening Browser main.
old = '''        if (YandexAliceAccessibility.tryClickToolbarAlice(context)) {
            AssistantLabTrace.add("YANDEX Alice entry clicked on warm path")
            scheduleForegroundChecks(context, AssistantTarget.ALICE)
            if (backgroundAfterClick) scheduleYandexToBackground(context, 1_800L)
            return
        }
        val launcher = pm.getLaunchIntentForPackage(app.packageName)?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
'''
new = '''        if (YandexAliceAccessibility.tryClickToolbarAlice(context)) {
            AssistantLabTrace.add("YANDEX Alice entry clicked on warm path")
            scheduleForegroundChecks(context, AssistantTarget.ALICE)
            if (backgroundAfterClick) scheduleYandexToBackground(context, 1_800L)
            return
        }
        if (tryOpenAliceAction(context)) {
            AssistantLabTrace.add("YANDEX Alice.OPEN accepted before Browser fallback")
            scheduleForegroundChecks(context, AssistantTarget.ALICE)
            if (backgroundAfterClick) scheduleYandexToBackground(context, 2_500L)
            return
        }
        val launcher = pm.getLaunchIntentForPackage(app.packageName)?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
'''
s = once(s, old, new, "Alice.OPEN normal route")

# Startup/update warm-up: try the exact Alice action first. If firmware refuses an external launch
# because BroAliceActivity is non-exported, continue with the already-proven exported wakeup service
# and cold Browser microphone route. The result is automatic; no Assistant Lab preparation needed.
old = '''        android.util.Log.i("AssistantLab", "Build93 Alice prewarm starting")
        AssistantLabTrace.armAliceStockGuard(20_000L)

        // This exported service exists in the field package dump. Starting it may be enough to keep
'''
new = '''        android.util.Log.i("AssistantLab", "Build93 Alice prewarm starting")
        AssistantLabTrace.armAliceStockGuard(20_000L)

        if (tryOpenAliceAction(context.applicationContext)) {
            android.util.Log.i("AssistantLab", "Build93 Alice prewarm: Alice.OPEN accepted")
            scheduleYandexToBackground(context.applicationContext, 2_500L)
            return
        }

        // This exported service exists in the field package dump. Starting it may be enough to keep
'''
s = once(s, old, new, "Alice.OPEN startup prewarm")

p.write_text(s)
print("Build93 hotfix applied: Alice steering default ON + Alice.OPEN probe + TXT/ZIP buttons removed")
