#!/usr/bin/env python3
from pathlib import Path

def once(s, old, new, name):
    if old not in s:
        raise SystemExit(f"Build92 anchor missing: {name}")
    return s.replace(old, new, 1)

p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 60041", "versionCode = 60042", "versionCode")
s = once(s, 'versionNameSuffix = "-dilink3-production-build91"', 'versionNameSuffix = "-dilink3-production-build92"', "versionName")
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = once(s, 'android:label="BYDMate DiLink3 Build91"', 'android:label="BYDMate DiLink3 Build92"', "label")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text().replace('SectionHeader(text = "Assistant Lab · Build91")', 'SectionHeader(text = "Assistant Lab · Build92")', 1)
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text().replace("Build91", "Build92")

s = once(s,
'''object YandexAliceAccessibility {
    const val PACKAGE = "com.yandex.browser"
    private const val MIN_ALICE_SCORE = 150
''',
'''object YandexAliceAccessibility {
    const val PACKAGE = "com.yandex.browser"
    private const val EXACT_ALICE_ID = "com.yandex.browser:id/alice_input_quarknyx"
    private const val EXACT_ALICE_DESC = "голосовой помощник"
    private const val MIN_ALICE_SCORE = 4000
''', "constants")

start = s.index('    private fun score(node: AccessibilityNodeInfo, context: Context): Int {')
end = s.index('\n    }\n}', start) + len('\n    }')
new_score = '''    private fun score(node: AccessibilityNodeInfo, context: Context): Int {
        val id = node.viewIdResourceName.orEmpty().lowercase(Locale.getDefault())
        val desc = node.contentDescription?.toString().orEmpty().lowercase(Locale.getDefault())
        val text = node.text?.toString().orEmpty().lowercase(Locale.getDefault())
        if (id == EXACT_ALICE_ID.lowercase(Locale.getDefault()) && node.isClickable) return 10000
        if (desc.contains(EXACT_ALICE_DESC) && node.isClickable) return 8000
        if (id.contains("allou_dialog_text") || text.contains("а вот и алиса")) return Int.MIN_VALUE
        return Int.MIN_VALUE
    }'''
s = s[:start] + new_score + s[end:]

old_delays = 'listOf(450L, 900L, 1_500L, 2_400L, 3_400L).forEach { delay ->'
s = once(s, old_delays, 'listOf(150L, 350L, 650L, 1_000L, 1_500L, 2_200L, 3_200L, 4_500L, 6_000L, 8_000L).forEach { delay ->', 'delays')
s = s.replace('if (!clicked[0] && AssistantLabTrace.active) {', 'if (!clicked[0]) {')
s = s.replace('}, 4_000L)', '}, 8_300L)', 1)
s = s.replace('YANDEX toolbar Alice not auto-clicked; click purple toolbar Alice manually once so trace captures its node id/description', 'YANDEX exact Alice button not found; expected id=com.yandex.browser:id/alice_input_quarknyx', 1)

warm_anchor = '''        AssistantLabTrace.add("YANDEX route: browser must host Alice; toolbar entry will be clicked via Accessibility")
        val launcher = pm.getLaunchIntentForPackage(app.packageName)?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
'''
warm_new = '''        AssistantLabTrace.add("YANDEX route Build92: exact toolbar id=alice_input_quarknyx")
        if (YandexAliceAccessibility.tryClickToolbarAlice(context)) {
            AssistantLabTrace.add("YANDEX exact Alice clicked on warm path")
            scheduleForegroundChecks(context, AssistantTarget.ALICE)
            return
        }
        val launcher = pm.getLaunchIntentForPackage(app.packageName)?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
'''
s = once(s, warm_anchor, warm_new, 'warm path')

perm_anchor = '''            info.requestedPermissions.orEmpty().take(80).forEach { perm ->
                val granted = pm.checkPermission(perm, pkg) == PackageManager.PERMISSION_GRANTED
                AssistantLabTrace.add("YANDEX-PERM pkg=$pkg granted=$granted perm=$perm")
            }
'''
perm_new = perm_anchor + '''            if (pkg == "com.yandex.aliceapp") {
                val mic = pm.checkPermission(android.Manifest.permission.RECORD_AUDIO, pkg) == PackageManager.PERMISSION_GRANTED
                AssistantLabTrace.add("ALICE-APP MIC=${if (mic) "GRANTED" else "DENIED"}")
            }
'''
s = once(s, perm_anchor, perm_new, 'mic diagnostic')

p.write_text(s)
print("Build92 applied")
