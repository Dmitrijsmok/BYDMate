#!/usr/bin/env python3
from pathlib import Path


def once(s, old, new, name):
    if old not in s:
        raise SystemExit(f"Build91 anchor missing: {name}")
    return s.replace(old, new, 1)

p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 60040", "versionCode = 60041", "version")
s = once(s, 'versionNameSuffix = "-dilink3-production-build90"', 'versionNameSuffix = "-dilink3-production-build91"', "suffix")
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = once(s, 'android:label="BYDMate DiLink3 Build90"', 'android:label="BYDMate DiLink3 Build91"', "label")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text().replace("Build90", "Build91")

s = once(s,
'''    @Volatile private var armedTarget: AssistantTarget? = null
    @Volatile private var consume304UntilUp: Boolean = false
''',
'''    @Volatile private var armedTarget: AssistantTarget? = null
    @Volatile private var consume304UntilUp: Boolean = false
    @Volatile var aliceTestMode: Boolean = false
        private set
''', "mode field")

s = once(s,
'''    fun armSteering(context: Context, target: AssistantTarget) {
        if (!active) start(context)
        armedTarget = target
        consume304UntilUp = false
        add("ARM next steering mic 304 -> ${target.title}")
    }
''',
'''    fun armSteering(context: Context, target: AssistantTarget) {
        if (!active) start(context)
        armedTarget = target
        consume304UntilUp = false
        add("ARM next steering mic 304 -> ${target.title}")
    }

    fun toggleAliceTestMode(context: Context): Boolean {
        if (!active) start(context)
        aliceTestMode = !aliceTestMode
        armedTarget = null
        consume304UntilUp = false
        add("ALICE TEST MODE=${if (aliceTestMode) "ON" else "OFF"}")
        return aliceTestMode
    }
''', "toggle")

s = once(s,
'''    fun maybeHandleSteering(context: Context, event: KeyEvent): Boolean {
        if (!active || event.keyCode != MIC_KEYCODE) return false
''',
'''    fun maybeHandleSteering(context: Context, event: KeyEvent): Boolean {
        if (event.keyCode != MIC_KEYCODE) return false
        if (!active && !aliceTestMode) return false
''', "mode independent of trace")

s = once(s,
'''        val target = armedTarget ?: return false
        if (event.action != KeyEvent.ACTION_DOWN || event.repeatCount != 0) return false

        armedTarget = null
        consume304UntilUp = true
        add("KEY 304 armed hit scan=${event.scanCode}; bypass BYDMate once -> ${target.title}")
''',
'''        val oneShot = armedTarget
        val target = oneShot ?: if (aliceTestMode) AssistantTarget.ALICE else return false
        if (event.action != KeyEvent.ACTION_DOWN || event.repeatCount != 0) return false

        if (oneShot != null) armedTarget = null
        consume304UntilUp = true
        add("KEY 304 route=${if (oneShot != null) "one-shot" else "alice-test"} target=${target.title}")
''', "persistent routing")

needle = '''        val alice = actionButton(context, "Alice") { launchOrInstall(context, AssistantTarget.ALICE) }
'''
insert = '''        content.addView(buttonRow(context,
            actionButton(context, "ALICE MODE ON/OFF") {
                val on = AssistantLabTrace.toggleAliceTestMode(context)
                Toast.makeText(context, if (on) "Alice Test Mode ON" else "Alice Test Mode OFF", Toast.LENGTH_LONG).show()
                refresh()
            },
        ))

'''
s = once(s, needle, insert + needle, "mode button")

status_anchor = '            append("\\nYandex/Alice: ")'
s = once(s, status_anchor, '            append("\\nALICE TEST MODE: ").append(if (AssistantLabTrace.aliceTestMode) "ON" else "OFF")\n' + status_anchor, "status")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text().replace('SectionHeader(text = "Assistant Lab · Build90")', 'SectionHeader(text = "Assistant Lab · Build91")', 1)
p.write_text(s)

print("Build91 applied")