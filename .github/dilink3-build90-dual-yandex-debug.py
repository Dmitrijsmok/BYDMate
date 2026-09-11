#!/usr/bin/env python3
from pathlib import Path


def once(s, old, new, name):
    if old not in s:
        raise SystemExit(f"Build90 anchor missing: {name}")
    return s.replace(old, new, 1)

# Identity
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 60039", "versionCode = 60040", "version")
s = once(s, 'versionNameSuffix = "-dilink3-production-build89"', 'versionNameSuffix = "-dilink3-production-build90"', "suffix")
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = once(s, 'android:label="BYDMate DiLink3 Build89"', 'android:label="BYDMate DiLink3 Build90"', "label")
provider = '''        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.assistantlab.files"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data android:name="android.support.FILE_PROVIDER_PATHS" android:resource="@xml/assistant_lab_file_paths" />
        </provider>
'''
if "assistantlab.files" not in s:
    s = once(s, "    </application>", provider + "    </application>", "provider")
p.write_text(s)

x = Path("app/src/main/res/xml/assistant_lab_file_paths.xml")
x.parent.mkdir(parents=True, exist_ok=True)
x.write_text('''<?xml version="1.0" encoding="utf-8"?>
<paths xmlns:android="http://schemas.android.com/apk/res/android">
    <cache-path name="assistant_lab_share" path="assistant-lab-share/" />
</paths>
''')

# Assistant Lab
p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text().replace("Build89", "Build90")
s = once(s, "import androidx.core.content.ContextCompat\n", "import androidx.core.content.ContextCompat\nimport androidx.core.content.FileProvider\n", "FileProvider")

s = once(s, '''    CHATGPT(
        "ChatGPT",
        listOf("com.openai.chatgpt"),
        listOf("chatgpt", "openai"),
        "https://chatgpt.com/download",
    ),
''', '''    ALICE_APP(
        "Alice app",
        listOf("com.yandex.aliceapp"),
        listOf("алиса", "alice"),
        "https://apkpure.com/search?q=com.yandex.aliceapp",
    ),
''', "Alice app target")
s = s.replace("AssistantTarget.CHATGPT", "AssistantTarget.ALICE_APP")
s = once(s, "        // Fallback by launcher label:", "        if (target == AssistantTarget.ALICE_APP) return null\n\n        // Fallback by launcher label:", "exact package")

# Rich A11Y trace for either Yandex host.
marker = '        add("A11Y type=${event.eventType} pkg=${pkg.ifBlank { "?" }} cls=${cls.ifBlank { "?" }}")\n'
extra = marker + '''        if (pkg == "com.yandex.browser" || pkg == "com.yandex.aliceapp") {
            val n = runCatching { event.source }.getOrNull()
            if (n != null) {
                add("A11Y-YANDEX pkg=$pkg type=${event.eventType} ${YandexAliceAccessibility.describe(n)}")
                @Suppress("DEPRECATION") runCatching { n.recycle() }
            }
        }
'''
s = once(s, marker, extra, "dual A11Y")

s = once(s, '        logForeground(context, "snapshot")\n', '        AssistantLabLauncher.dumpYandexProfile(context)\n        logForeground(context, "snapshot")\n', "profile snapshot")

# Share a real txt file through Android share sheet.
s = once(s, '    fun snapshot(): String = synchronized(lock) { lines.joinToString("\\n") }\n', '''    fun snapshot(): String = synchronized(lock) { lines.joinToString("\\n") }

    fun share(context: Context) {
        val text = snapshot()
        if (text.isBlank()) { Toast.makeText(context, "Лог пуст", Toast.LENGTH_SHORT).show(); return }
        runCatching {
            val dir = File(context.cacheDir, "assistant-lab-share").apply { mkdirs() }
            val file = File(dir, "BYDMate-AssistantLab-Build90.txt").apply { writeText(text) }
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.assistantlab.files", file)
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_STREAM, uri)
                clipData = ClipData.newRawUri("BYDMate Assistant Lab", uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(Intent.createChooser(send, "Отправить лог").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }.onFailure { Toast.makeText(context, "Share log: ${it.message}", Toast.LENGTH_LONG).show() }
    }
''', "share")
s = once(s, 'actionButton(context, "COPY LOG") { copyLog(context) }', 'actionButton(context, "SHARE LOG") { AssistantLabTrace.share(context) }', "share button")

# Repurpose all visible GPT controls as the exact standalone Alice package probe.
s = s.replace('val gpt = actionButton(context, "ChatGPT")', 'val gpt = actionButton(context, "Alice app")')
s = s.replace('"РУЛЬ → GPT (1 раз)"', '"РУЛЬ → ALICE APP (1 раз)"')
s = s.replace('пойдёт в ChatGPT', 'пойдёт в Alice app')
s = s.replace('нативный ChatGPT', 'нативная Alice app')
s = s.replace('ChatGPT: ', 'Standalone Alice app: ')
s = s.replace('"УСТАНОВИТЬ CHATGPT" else "ТЕСТ CHATGPT"', '"ПРОВЕРИТЬ ALICE APP" else "ТЕСТ ALICE APP"')

# Missing standalone app is a diagnostic result, not an installer redirect.
s = once(s, '''    private fun launchOrInstall(context: Context, target: AssistantTarget) {
        if (!AssistantLabTrace.active) AssistantLabTrace.start(context)
''', '''    private fun launchOrInstall(context: Context, target: AssistantTarget) {
        if (!AssistantLabTrace.active) AssistantLabTrace.start(context)
        if (target == AssistantTarget.ALICE_APP && !AssistantLabLauncher.isInstalled(context, target)) {
            AssistantLabTrace.add("ALICE-APP com.yandex.aliceapp present=false")
            AssistantLabLauncher.dumpYandexProfile(context)
            Toast.makeText(context, "com.yandex.aliceapp не установлен", Toast.LENGTH_SHORT).show()
            refresh(); return
        }
''', "missing app UI")

s = once(s, '''    fun openOfficialInstall(context: Context, target: AssistantTarget) {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(target.officialInstallUrl)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
''', '''    fun openOfficialInstall(context: Context, target: AssistantTarget) {
        if (target == AssistantTarget.ALICE_APP) {
            AssistantLabTrace.add("ALICE-APP installer skipped; package absent")
            dumpYandexProfile(context)
            Toast.makeText(context, "Alice app отдельно не найдена", Toast.LENGTH_SHORT).show()
            return
        }
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(target.officialInstallUrl)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
''', "no standalone installer")

# Focused package/component diagnostics.
anchor = '    fun dumpPackage(context: Context, pkg: String) {\n'
helper = '''    fun dumpYandexProfile(context: Context) {
        val pm = context.packageManager
        listOf("com.yandex.browser", "com.yandex.aliceapp").forEach { pkg ->
            val info = runCatching { @Suppress("DEPRECATION") pm.getPackageInfo(pkg, PackageManager.GET_ACTIVITIES or PackageManager.GET_SERVICES) }.getOrNull()
            if (info == null) { AssistantLabTrace.add("YANDEX-PROFILE pkg=$pkg present=false"); return@forEach }
            AssistantLabTrace.add("YANDEX-PROFILE pkg=$pkg present=true version=${info.versionName} launcher=${pm.getLaunchIntentForPackage(pkg)?.component ?: "null"}")
            val needles = listOf("alice", "speech", "voice", "assist", "broalice")
            info.activities.orEmpty().filter { a -> needles.any { a.name.contains(it, true) } }.take(40).forEach { a ->
                AssistantLabTrace.add("YANDEX-ACT pkg=$pkg exported=${a.exported} enabled=${a.enabled} name=${a.name}")
            }
            info.services.orEmpty().filter { a -> needles.any { a.name.contains(it, true) } }.take(40).forEach { a ->
                AssistantLabTrace.add("YANDEX-SVC pkg=$pkg exported=${a.exported} enabled=${a.enabled} name=${a.name}")
            }
        }
    }

'''
s = once(s, anchor, helper + anchor, "profile helper")
p.write_text(s)

# Settings label only.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text().replace('SectionHeader(text = "Assistant Lab · Build89")', 'SectionHeader(text = "Assistant Lab · Build90")', 1)
s = s.replace("Alice / ChatGPT", "Yandex Browser / standalone Alice app").replace("Alice/ChatGPT", "Yandex Browser / standalone Alice app")
p.write_text(s)

print("Build90 applied")
