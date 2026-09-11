#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60038"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build88 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Monotonic upgrade identity over Build87. Same package/signing chain.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60037", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build87"',
    '            versionNameSuffix = "-dilink3-production-build88"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build87"',
    'android:label="BYDMate DiLink3 Build88"',
    "manifest label",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Fix Assistant Lab overlay touch handling on DiLink Android 10.
#    Build86/87 used FLAG_NOT_FOCUSABLE. On this BYD image the overlay was drawn correctly but
#    taps could fall through to the app below. Make the overlay focusable/clickable while keeping
#    it non-modal so taps OUTSIDE its bounds still go to Alice/ChatGPT.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text()
s = s.replace("Build87", "Build88")

s = replace_once(
    s,
    '''            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
''',
    '''            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
''',
    "overlay focus/touch flags",
)

s = replace_once(
    s,
    '''        val outer = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
''',
    '''        val outer = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            isClickable = true
            isFocusable = true
            isFocusableInTouchMode = true
''',
    "clickable overlay root",
)

# Only the title is a drag handle. The old whole-header drag listener could compete with
# minimize/close buttons on vendor View dispatch implementations.
s = replace_once(
    s,
    '''        outer.addView(header)
        installDrag(header)
''',
    '''        outer.addView(header)
        installDrag(title)
''',
    "drag title only",
)

s = replace_once(
    s,
    '''        val min = smallButton(context, "СВЕРНУТЬ") { toggleSize(context) }.apply {
''',
    '''        val min = smallButton(context, "СВЕРНУТЬ") {
            AssistantLabTrace.add("UI minimize/expand clicked")
            toggleSize(context)
        }.apply {
''',
    "trace minimize click",
)

s = replace_once(
    s,
    '''        val close = smallButton(context, "×") { hide() }
''',
    '''        val close = smallButton(context, "×") {
            AssistantLabTrace.add("UI close clicked")
            hide()
        }
''',
    "trace close click",
)

# Make every button an explicit touch target; this is redundant on AOSP but useful on the
# customized DiLink framework where the previous overlay behaved visually but was touch-through.
s = replace_once(
    s,
    '''    private fun actionButton(context: Context, label: String, action: () -> Unit): Button =
        Button(context).apply {
            text = label
            textSize = 11f
            isAllCaps = false
            setOnClickListener { action() }
        }
''',
    '''    private fun actionButton(context: Context, label: String, action: () -> Unit): Button =
        Button(context).apply {
            text = label
            textSize = 11f
            isAllCaps = false
            isClickable = true
            isFocusable = true
            setOnClickListener { action() }
        }
''',
    "action button touch target",
)

s = replace_once(
    s,
    '''    private fun smallButton(context: Context, label: String, action: () -> Unit): Button =
        Button(context).apply {
            text = label
            textSize = 18f
            minWidth = 0
            minimumWidth = 0
            setPadding(0, 0, 0, 0)
            setOnClickListener { action() }
            layoutParams = LinearLayout.LayoutParams(dp(context, 60), dp(context, 44))
        }
''',
    '''    private fun smallButton(context: Context, label: String, action: () -> Unit): Button =
        Button(context).apply {
            text = label
            textSize = 18f
            minWidth = 0
            minimumWidth = 0
            setPadding(0, 0, 0, 0)
            isClickable = true
            isFocusable = true
            setOnClickListener { action() }
            layoutParams = LinearLayout.LayoutParams(dp(context, 60), dp(context, 44))
        }
''',
    "small button touch target",
)

# ---------------------------------------------------------------------------
# 3) Alice installation: don't send a missing Alice target to the generic alice.yandex.ru page,
#    which looks like Alice but is only the browser/web app. Open the official RuStore app card
#    directly. If RuStore is installed its deep link is preferred; otherwise the official web card
#    is opened. Package detection remains com.yandex.aliceapp.
# ---------------------------------------------------------------------------
s = replace_once(
    s,
    '        "https://alice.yandex.ru/",\n',
    '        "https://www.rustore.ru/catalog/app/com.yandex.aliceapp",\n',
    "Alice official install URL",
)

old_open = '''    fun openOfficialInstall(context: Context, target: AssistantTarget) {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(target.officialInstallUrl)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        start(context, intent, "official-install:${target.officialInstallUrl}")
    }
'''
new_open = '''    fun openOfficialInstall(context: Context, target: AssistantTarget) {
        if (target == AssistantTarget.ALICE) {
            val rustore = Intent(
                Intent.ACTION_VIEW,
                Uri.parse("rustore://apps.rustore.ru/app/com.yandex.aliceapp"),
            ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            val canOpenRuStore = runCatching { context.packageManager.resolveActivity(rustore, 0) != null }.getOrDefault(false)
            AssistantLabTrace.add("INSTALL Alice: RuStore handler=$canOpenRuStore")
            if (canOpenRuStore && start(context, rustore, "official-install:rustore-alice")) return
        }
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(target.officialInstallUrl)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        start(context, intent, "official-install:${target.officialInstallUrl}")
    }
'''
s = replace_once(s, old_open, new_open, "official install launcher")

# Clarify status so the browser web chat is never mistaken for an installed Android assistant.
s = replace_once(
    s,
    '''            append("\\nAlice: ").append(alice?.let { "${it.label} · ${it.packageName} · ${it.versionName}" } ?: "НЕ УСТАНОВЛЕНА")
''',
    '''            append("\\nAlice: ").append(alice?.let { "${it.label} · ${it.packageName} · ${it.versionName}" } ?: "НЕ УСТАНОВЛЕНА (web-страница в браузере не считается приложением)")
''',
    "Alice installed status clarification",
)

p.write_text(s)


# ---------------------------------------------------------------------------
# 4) Settings copy.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
s = s.replace('SectionHeader(text = "Assistant Lab · Build87")', 'SectionHeader(text = "Assistant Lab · Build88")', 1)
s = s.replace(
    "Плавающее окно остаётся поверх внешнего приложения. Кнопка СВЕРНУТЬ делает его компактным; trace продолжает писаться.",
    "Плавающее окно остаётся поверх внешнего приложения. В Build88 исправлен touch-through: кнопки окна должны нажиматься, а касания вне окна проходят в Alice/ChatGPT. Кнопка СВЕРНУТЬ делает окно компактным; trace продолжает писаться.",
    1,
)
p.write_text(s)

print("Build88 applied: Build85 baseline + native assistant handoff + DiLink overlay touch fix + RuStore Alice install")
