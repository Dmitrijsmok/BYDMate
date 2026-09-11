#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60039"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build89 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Monotonic upgrade identity over Build88. Same package/signing chain.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60038", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build88"',
    '            versionNameSuffix = "-dilink3-production-build89"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build88"',
    'android:label="BYDMate DiLink3 Build89"',
    "manifest label",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Assistant Lab: Yandex Browser is the Alice host observed in the field.
#    Standalone com.yandex.aliceapp is not required/supported by this experiment.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text()
s = s.replace("Build88", "Build89")

s = replace_once(
    s,
    "import android.graphics.Color\n",
    "import android.graphics.Color\nimport android.graphics.Rect\n",
    "Rect import",
)
s = replace_once(
    s,
    "import android.view.accessibility.AccessibilityEvent\n",
    "import android.view.accessibility.AccessibilityEvent\nimport android.view.accessibility.AccessibilityNodeInfo\n",
    "AccessibilityNodeInfo import",
)

s = replace_once(
    s,
    '''    ALICE(
        "Alice",
        listOf("com.yandex.aliceapp"),
        listOf("алиса", "alice"),
        "https://www.rustore.ru/catalog/app/com.yandex.aliceapp",
    ),
''',
    '''    ALICE(
        "Yandex Browser / Alice",
        listOf("com.yandex.browser"),
        listOf("yandex", "яндекс", "browser"),
        "https://apkpure.com/search?q=com.yandex.browser",
    ),
''',
    "Yandex Browser Alice target",
)

# Richer clicked-node trace: the manual toolbar Alice click should expose resource-id/content-desc
# on this exact DiLink/Yandex build so future routing can become deterministic.
s = replace_once(
    s,
    '''        add("A11Y type=${event.eventType} pkg=${pkg.ifBlank { "?" }} cls=${cls.ifBlank { "?" }}")
    }
''',
    '''        add("A11Y type=${event.eventType} pkg=${pkg.ifBlank { "?" }} cls=${cls.ifBlank { "?" }}")
        if (pkg == YandexAliceAccessibility.PACKAGE && event.eventType == AccessibilityEvent.TYPE_VIEW_CLICKED) {
            val node = runCatching { event.source }.getOrNull()
            if (node != null) {
                add("A11Y YANDEX CLICK ${YandexAliceAccessibility.describe(node)}")
                @Suppress("DEPRECATION") runCatching { node.recycle() }
            }
        }
    }
''',
    "Yandex clicked node trace",
)

# Include crash buffer and native crash tags; Build88 proved the browser process dies but the
# previous filtered logcat did not retain the actual exception/backtrace.
s = replace_once(
    s,
    '''            val process = ProcessBuilder(
                "logcat", "-v", "threadtime", "-T", "1",
                "ActivityTaskManager:I", "ActivityManager:I", "WindowManager:I",
                "VoiceInteractionManagerService:I", "AndroidRuntime:E", "*:S",
            ).redirectErrorStream(true).start()
''',
    '''            val process = ProcessBuilder(
                "logcat", "-b", "main", "-b", "system", "-b", "crash",
                "-v", "threadtime", "-T", "1",
                "ActivityTaskManager:I", "ActivityManager:I", "WindowManager:I",
                "VoiceInteractionManagerService:I", "AndroidRuntime:E", "libc:F",
                "DEBUG:F", "crash_dump32:F", "crash_dump64:F", "*:S",
            ).redirectErrorStream(true).start()
''',
    "crash buffer logcat",
)

# Insert accessibility helper before the launcher. It never clicks blindly by coordinates: it
# requires Alice/voice metadata on an accessible Yandex node. If not found, candidates are traced.
anchor = '''object AssistantLabLauncher {
'''
helper = r'''object YandexAliceAccessibility {
    const val PACKAGE = "com.yandex.browser"
    private const val MIN_ALICE_SCORE = 150

    fun tryClickToolbarAlice(context: Context): Boolean {
        val service = SteeringWheelKeyService.instance
        if (service == null) {
            AssistantLabTrace.add("YANDEX-A11Y unavailable: SteeringWheelKeyService instance=null")
            return false
        }

        val roots = ArrayList<AccessibilityNodeInfo>()
        runCatching { service.rootInActiveWindow }.getOrNull()?.let { roots.add(it) }
        runCatching { service.windows }.getOrNull().orEmpty().forEach { window ->
            runCatching { window.root }.getOrNull()?.let { roots.add(it) }
        }
        if (roots.isEmpty()) {
            AssistantLabTrace.add("YANDEX-A11Y no roots")
            return false
        }

        var best: AccessibilityNodeInfo? = null
        var bestScore = Int.MIN_VALUE
        val topCandidates = ArrayList<String>()
        for (root in roots) {
            val queue = ArrayDeque<AccessibilityNodeInfo>()
            queue.add(AccessibilityNodeInfo.obtain(root))
            while (queue.isNotEmpty()) {
                val node = queue.removeFirst()
                try {
                    val pkg = node.packageName?.toString().orEmpty()
                    if (pkg == PACKAGE) {
                        val score = score(node, context)
                        if (score >= 60 && topCandidates.size < 16) {
                            topCandidates.add("score=$score ${describe(node)}")
                        }
                        if (score > bestScore) {
                            @Suppress("DEPRECATION") runCatching { best?.recycle() }
                            best = AccessibilityNodeInfo.obtain(node)
                            bestScore = score
                        }
                    }
                    for (i in 0 until node.childCount) {
                        runCatching { node.getChild(i) }.getOrNull()?.let { queue.add(it) }
                    }
                } finally {
                    @Suppress("DEPRECATION") runCatching { node.recycle() }
                }
            }
        }
        roots.forEach { @Suppress("DEPRECATION") runCatching { it.recycle() } }

        val candidate = best
        if (candidate == null || bestScore < MIN_ALICE_SCORE) {
            AssistantLabTrace.add("YANDEX-A11Y Alice node not found; bestScore=$bestScore")
            topCandidates.forEach { AssistantLabTrace.add("YANDEX-A11Y candidate $it") }
            @Suppress("DEPRECATION") runCatching { candidate?.recycle() }
            return false
        }

        AssistantLabTrace.add("YANDEX-A11Y selected score=$bestScore ${describe(candidate)}")
        var current: AccessibilityNodeInfo? = candidate
        repeat(4) {
            val n = current ?: return@repeat
            if (n.isClickable) {
                val ok = runCatching { n.performAction(AccessibilityNodeInfo.ACTION_CLICK) }.getOrDefault(false)
                AssistantLabTrace.add("YANDEX-A11Y click clickable=${n.isClickable} ok=$ok ${describe(n)}")
                if (ok) {
                    @Suppress("DEPRECATION") runCatching { n.recycle() }
                    if (n !== candidate) @Suppress("DEPRECATION") runCatching { candidate.recycle() }
                    return true
                }
            }
            val parent = runCatching { n.parent }.getOrNull()
            if (n !== candidate) @Suppress("DEPRECATION") runCatching { n.recycle() }
            current = parent
        }
        @Suppress("DEPRECATION") runCatching { current?.recycle() }
        @Suppress("DEPRECATION") runCatching { candidate.recycle() }
        return false
    }

    fun describe(node: AccessibilityNodeInfo): String {
        val rect = Rect()
        runCatching { node.getBoundsInScreen(rect) }
        return "id=${node.viewIdResourceName ?: "-"} desc=${node.contentDescription ?: "-"} text=${node.text ?: "-"} cls=${node.className ?: "-"} clickable=${node.isClickable} bounds=$rect"
    }

    private fun score(node: AccessibilityNodeInfo, context: Context): Int {
        val id = node.viewIdResourceName.orEmpty().lowercase(Locale.getDefault())
        val desc = node.contentDescription?.toString().orEmpty().lowercase(Locale.getDefault())
        val text = node.text?.toString().orEmpty().lowercase(Locale.getDefault())
        val cls = node.className?.toString().orEmpty().lowercase(Locale.getDefault())
        val hay = "$id $desc $text"
        var score = 0
        if (hay.contains("алис") || hay.contains("alice")) score += 500
        if (hay.contains("assistant") || hay.contains("voice") || hay.contains("speech")) score += 120
        if (node.isClickable) score += 40
        if (cls.contains("imageview") || cls.contains("imagebutton")) score += 20
        val rect = Rect()
        runCatching { node.getBoundsInScreen(rect) }
        val dm = context.resources.displayMetrics
        if (rect.centerX() > dm.widthPixels * 0.55 && rect.centerY() < dm.heightPixels * 0.30) score += 25
        return score
    }
}

'''
s = replace_once(s, anchor, helper + anchor, "Yandex accessibility helper")

# Specialized launch path for the browser-hosted Alice. Bring Yandex Browser foreground, then let
# Accessibility click the working toolbar Alice entry observed by the user.
s = replace_once(
    s,
    '''        AssistantLabTrace.add("LAUNCH target=${target.title} pkg=${app.packageName} label=${app.label} preferVoice=$preferVoice")
        dumpPackage(context, app.packageName)
        val pm = context.packageManager

        val candidates = if (preferVoice) listOf(Intent.ACTION_ASSIST, Intent.ACTION_VOICE_COMMAND) else emptyList()
''',
    '''        AssistantLabTrace.add("LAUNCH target=${target.title} pkg=${app.packageName} label=${app.label} preferVoice=$preferVoice")
        dumpPackage(context, app.packageName)
        val pm = context.packageManager

        if (target == AssistantTarget.ALICE && app.packageName == YandexAliceAccessibility.PACKAGE) {
            launchYandexBrowserAlice(context, pm, app)
            return
        }

        val candidates = if (preferVoice) listOf(Intent.ACTION_ASSIST, Intent.ACTION_VOICE_COMMAND) else emptyList()
''',
    "special Yandex launch routing",
)

open_anchor = '''    fun openOfficialInstall(context: Context, target: AssistantTarget) {
'''
yandex_launch = r'''    private fun launchYandexBrowserAlice(context: Context, pm: PackageManager, app: InstalledAssistant) {
        AssistantLabTrace.add("YANDEX route: browser must host Alice; toolbar entry will be clicked via Accessibility")
        val launcher = pm.getLaunchIntentForPackage(app.packageName)?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (launcher == null || !start(context, launcher, "yandex-browser-main")) {
            AssistantLabTrace.add("YANDEX route failed: no working browser launcher")
            return
        }
        scheduleForegroundChecks(context, AssistantTarget.ALICE)
        val handler = Handler(Looper.getMainLooper())
        val clicked = booleanArrayOf(false)
        listOf(450L, 900L, 1_500L, 2_400L, 3_400L).forEach { delay ->
            handler.postDelayed({
                if (!clicked[0] && AssistantLabTrace.active) {
                    val ok = YandexAliceAccessibility.tryClickToolbarAlice(context)
                    if (ok) {
                        clicked[0] = true
                        AssistantLabTrace.add("YANDEX toolbar Alice clicked at +${delay}ms")
                    }
                }
            }, delay)
        }
        handler.postDelayed({
            if (!clicked[0] && AssistantLabTrace.active) {
                AssistantLabTrace.add("YANDEX toolbar Alice not auto-clicked; click purple toolbar Alice manually once so trace captures its node id/description")
            }
        }, 4_000L)
    }

'''
s = replace_once(s, open_anchor, yandex_launch + open_anchor, "Yandex browser launch helper")

# Replace the Build88 RuStore-only standalone Alice installer with a generic target URL. For Alice
# this is an APKPure package search for com.yandex.browser, matching the user's installation path.
old_install = '''    fun openOfficialInstall(context: Context, target: AssistantTarget) {
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
new_install = '''    fun openOfficialInstall(context: Context, target: AssistantTarget) {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(target.officialInstallUrl)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        AssistantLabTrace.add("INSTALL ${target.title}: ${target.officialInstallUrl}")
        start(context, intent, "install:${target.officialInstallUrl}")
    }
'''
s = replace_once(s, old_install, new_install, "Yandex Browser install route")

# Status/button wording now reflects the actual dependency discovered in the field.
s = replace_once(
    s,
    '''            append("\\nAlice: ").append(alice?.let { "${it.label} · ${it.packageName} · ${it.versionName}" } ?: "НЕ УСТАНОВЛЕНА (web-страница в браузере не считается приложением)")
''',
    '''            append("\\nYandex/Alice: ").append(alice?.let { "${it.label} · ${it.packageName} · ${it.versionName}" } ?: "YANDEX BROWSER НЕ УСТАНОВЛЕН")
''',
    "Yandex status wording",
)
s = replace_once(
    s,
    '''        aliceButton?.text = if (alice == null) "УСТАНОВИТЬ ALICE" else "ТЕСТ ALICE"
''',
    '''        aliceButton?.text = if (alice == null) "УСТАНОВИТЬ YANDEX" else "ТЕСТ ALICE"
''',
    "Yandex install button wording",
)

# ---------------------------------------------------------------------------
# 3) Make Assistant Lab substantially shorter for the 1920x1080 DiLink landscape screen.
#    The log remains scrollable; controls stay above it and are not hidden behind top/bottom bars.
# ---------------------------------------------------------------------------
s = replace_once(s, "            dp(context, 900),\n            dp(context, 690),\n", "            dp(context, 820),\n            dp(context, 500),\n", "compact window size")
s = replace_once(s, "            x = dp(context, 40)\n            y = dp(context, 70)\n", "            x = dp(context, 28)\n            y = dp(context, 72)\n", "safe top offset")
s = replace_once(s, "            textSize = 13f\n", "            textSize = 11.5f\n", "status text size")
s = replace_once(s, "            textSize = 11f\n            typeface = Typeface.MONOSPACE\n", "            textSize = 9.5f\n            typeface = Typeface.MONOSPACE\n", "log text size")
s = replace_once(s, "        p.width = dp(context, if (minimized) 520 else 900)\n        p.height = if (minimized) WindowManager.LayoutParams.WRAP_CONTENT else dp(context, 690)\n", "        p.width = dp(context, if (minimized) 430 else 820)\n        p.height = if (minimized) WindowManager.LayoutParams.WRAP_CONTENT else dp(context, 500)\n", "compact minimize/expand dimensions")
s = replace_once(s, "buttons.forEach { b -> addView(b, LinearLayout.LayoutParams(0, dp(context, 52), 1f).apply { setMargins(dp(context, 3), dp(context, 4), dp(context, 3), dp(context, 4)) }) }", "buttons.forEach { b -> addView(b, LinearLayout.LayoutParams(0, dp(context, 44), 1f).apply { setMargins(dp(context, 3), dp(context, 2), dp(context, 3), dp(context, 2)) }) }", "compact button rows")
s = replace_once(s, "            textSize = 11f\n            isAllCaps = false\n", "            textSize = 10f\n            isAllCaps = false\n", "compact action button text")

p.write_text(s)


# ---------------------------------------------------------------------------
# 4) Settings copy: make the dependency explicit.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
s = s.replace('SectionHeader(text = "Assistant Lab · Build88")', 'SectionHeader(text = "Assistant Lab · Build89")', 1)
s = s.replace(
    "Build88 исправлен touch-through: кнопки окна должны нажиматься, а касания вне окна проходят в Alice/ChatGPT.",
    "Build89 использует Yandex Browser (com.yandex.browser) как хост Alice. Кнопка руля в тестовом режиме открывает браузер и пытается нажать рабочую фиолетовую Alice в toolbar через Accessibility. Debug-окно стало ниже и компактнее.",
    1,
)
p.write_text(s)

print("Build89 applied: Yandex Browser Alice host + accessibility toolbar click + compact lab + crash trace")
