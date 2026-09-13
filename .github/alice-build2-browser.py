#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, name: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice Build 2 anchor missing: {name}")
    return text.replace(old, new, 1)


p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()

# Browser/Alice launcher + accessibility tree helpers.
s = once(
    s,
    "import android.content.SharedPreferences\nimport android.util.Log\n",
    "import android.content.SharedPreferences\nimport android.net.Uri\nimport android.os.Handler\nimport android.os.Looper\nimport android.util.Log\n",
    "Android launcher imports",
)
s = once(
    s,
    "import android.view.accessibility.AccessibilityEvent\n",
    "import android.view.accessibility.AccessibilityEvent\nimport android.view.accessibility.AccessibilityNodeInfo\n",
    "AccessibilityNodeInfo import",
)
s = once(
    s,
    "import kotlinx.coroutines.flow.MutableStateFlow\n",
    "import kotlinx.coroutines.flow.MutableStateFlow\nimport java.util.ArrayDeque\nimport java.util.Locale\n",
    "collection imports",
)

s = once(
    s,
    '''    private val prefs: SharedPreferences by lazy {\n        applicationContext.getSharedPreferences(ClusterProjectionManager.PREFS_NAME, Context.MODE_PRIVATE)\n    }\n''',
    '''    private val prefs: SharedPreferences by lazy {\n        applicationContext.getSharedPreferences(ClusterProjectionManager.PREFS_NAME, Context.MODE_PRIVATE)\n    }\n\n    // Alice Build 2: steering voice key launches the real Alice entry point in Yandex Browser.\n    // The old VoiceController/OpenRouter/GigaAM/TTS code stays in the APK, but this key path\n    // deliberately bypasses it so the integration can be tested independently.\n    private val aliceHandler = Handler(Looper.getMainLooper())\n    private var aliceClickPending = false\n    private var aliceClickAttempt = 0\n    private var aliceClickGeneration = 0\n    private var yandexWindowLogged = false\n''',
    "Alice launcher fields",
)

# Runtime proof that the accessibility service actually has the flags we depend on.
s = once(
    s,
    '''        serviceInfo = info\n        instance = this\n        isConnected = true\n        Log.d(TAG, "connected; filtering steering-wheel keys")\n''',
    '''        serviceInfo = info\n        instance = this\n        isConnected = true\n        Log.i(TAG, "A11Y_SERVICE_CONNECTED package=$packageName")\n        Log.i(\n            TAG,\n            "A11Y_RUNTIME_FLAGS " +\n                "filterKeys=${(info.flags and AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS) != 0} " +\n                "reportViewIds=${(info.flags and AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS) != 0} " +\n                "includeNotImportant=${(info.flags and AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS) != 0} " +\n                "retrieveWindows=${(info.flags and AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS) != 0} " +\n                "eventTypes=${info.eventTypes}"\n        )\n''',
    "runtime accessibility diagnostics",
)

# Replace only the configured voice-key action. Learn mode, star projection, knob and user
# automation key routing stay byte-for-byte on the existing path.
s = once(
    s,
    '''        when (voiceDecision(event.keyCode, isDown, voiceEnabled, voiceKey)) {\n            VoiceKeyDecision.TRIGGER -> {\n                entryPoint().voiceController().onPttPressed()\n                return true\n            }\n            // Swallow the matching key's UP edge too — otherwise it falls through to the\n            // native BYD assistant, which owns the same hardware keycode (Finding 2).\n            VoiceKeyDecision.CONSUME -> return true\n            VoiceKeyDecision.IGNORE -> {}\n        }\n''',
    '''        when (voiceDecision(event.keyCode, isDown, voiceEnabled, voiceKey)) {\n            VoiceKeyDecision.TRIGGER -> {\n                Log.i(TAG, "STEERING_KEY DOWN keyCode=${event.keyCode} repeat=${event.repeatCount}")\n                Log.i(TAG, "NATIVE_ASSISTANT_KEY_BLOCKED keyCode=${event.keyCode}")\n                Log.i(TAG, "STEERING_KEY CONSUMED action=DOWN keyCode=${event.keyCode}")\n                // A held steering key may repeat ACTION_DOWN. Launch Alice only once per press,\n                // while still consuming every repeat so the BYD assistant never receives it.\n                if (event.repeatCount == 0) launchYandexAliceOrApkPure()\n                return true\n            }\n            // Swallow the matching key's UP edge too — otherwise it falls through to the\n            // native BYD assistant, which owns the same hardware keycode (Finding 2).\n            VoiceKeyDecision.CONSUME -> {\n                Log.i(\n                    TAG,\n                    "STEERING_KEY CONSUMED action=${if (isDown) "DOWN" else "UP"} keyCode=${event.keyCode}"\n                )\n                return true\n            }\n            VoiceKeyDecision.IGNORE -> {}\n        }\n''',
    "steering voice route",
)

# Keep Navigator parsing intact, but also react immediately when the Browser window appears.
s = once(
    s,
    '''    // Single volatile read when the HUD feature is off - see NavA11yFeed.enabled.\n    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n        NavA11yFeed.onEvent(this, event)\n    }\n''',
    '''    // Single volatile read when the HUD feature is off - see NavA11yFeed.enabled.\n    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n        NavA11yFeed.onEvent(this, event)\n\n        if (aliceClickPending && event?.packageName?.toString() == YANDEX_BROWSER_PACKAGE) {\n            if (!yandexWindowLogged) {\n                yandexWindowLogged = true\n                Log.i(TAG, "YANDEX_WINDOW_DETECTED eventType=${event.eventType}")\n            }\n            tryClickAliceNode("event:${event.eventType}")\n        }\n    }\n''',
    "Yandex accessibility event hook",
)

# Invalidate pending retries when the service goes away.
s = once(
    s,
    '''    override fun onUnbind(intent: Intent?): Boolean {\n        instance = null\n        isConnected = false\n        Log.d(TAG, "unbound; star key filter inactive")\n        return super.onUnbind(intent)\n    }\n\n    override fun onDestroy() {\n        instance = null\n        isConnected = false\n        super.onDestroy()\n    }\n''',
    '''    override fun onUnbind(intent: Intent?): Boolean {\n        cancelAliceClick("a11y_unbind")\n        instance = null\n        isConnected = false\n        Log.d(TAG, "unbound; star key filter inactive")\n        return super.onUnbind(intent)\n    }\n\n    override fun onDestroy() {\n        cancelAliceClick("a11y_destroy")\n        instance = null\n        isConnected = false\n        super.onDestroy()\n    }\n''',
    "pending click cleanup",
)

# Add the Browser launcher and exact historical Alice-node matcher before entryPoint().
anchor = '''    private fun entryPoint(): ClusterEntryPoint =\n'''
helpers = r'''    private fun launchYandexAliceOrApkPure() {
        val browserLaunchIntent = packageManager.getLaunchIntentForPackage(YANDEX_BROWSER_PACKAGE)
        if (browserLaunchIntent == null) {
            Log.w(TAG, "YANDEX_BROWSER_MISSING package=$YANDEX_BROWSER_PACKAGE")
            cancelAliceClick("browser_missing")
            openApkPure()
            return
        }

        Log.i(TAG, "YANDEX_BROWSER_FOUND package=$YANDEX_BROWSER_PACKAGE")

        val deepLinkIntent = Intent(Intent.ACTION_VIEW, Uri.parse(YANDEX_ALICE_URI)).apply {
            setPackage(YANDEX_BROWSER_PACKAGE)
            addCategory(Intent.CATEGORY_BROWSABLE)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        val deepLinkLaunched = runCatching {
            startActivity(deepLinkIntent)
            true
        }.getOrElse {
            Log.w(TAG, "YANDEX_BROWSER_DEEPLINK_FAILED error=${it.javaClass.simpleName}:${it.message}")
            false
        }

        val launched = if (deepLinkLaunched) {
            true
        } else {
            runCatching {
                browserLaunchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                startActivity(browserLaunchIntent)
                true
            }.getOrElse {
                Log.e(TAG, "YANDEX_BROWSER_LAUNCH_FALLBACK_FAILED", it)
                false
            }
        }

        Log.i(TAG, "YANDEX_BROWSER_LAUNCH deepLink=$deepLinkLaunched success=$launched")
        if (launched) {
            armAliceClick()
        } else {
            cancelAliceClick("launch_failed")
        }
    }

    private fun openApkPure() {
        val ok = runCatching {
            startActivity(
                Intent(Intent.ACTION_VIEW, Uri.parse(APKPURE_YANDEX_SEARCH_URL)).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
            )
            true
        }.getOrElse {
            Log.e(TAG, "APKPURE_OPEN_FAILED", it)
            false
        }
        Log.i(TAG, "APKPURE_OPEN_RESULT success=$ok")
    }

    private fun armAliceClick() {
        aliceClickPending = true
        aliceClickAttempt = 0
        yandexWindowLogged = false
        val generation = ++aliceClickGeneration
        Log.i(TAG, "ALICE_CLICK_ARMED generation=$generation warmupMs=$ALICE_WARMUP_MS")
        aliceHandler.postDelayed({ retryAliceClick(generation) }, ALICE_WARMUP_MS)
    }

    private fun retryAliceClick(generation: Int) {
        if (!aliceClickPending || generation != aliceClickGeneration) return

        aliceClickAttempt++
        if (tryClickAliceNode("timer:$aliceClickAttempt")) return

        if (aliceClickAttempt >= ALICE_MAX_CLICK_ATTEMPTS) {
            Log.w(TAG, "ALICE_NODE_NOT_FOUND attempts=$aliceClickAttempt")
            cancelAliceClick("retry_exhausted")
            return
        }

        aliceHandler.postDelayed({ retryAliceClick(generation) }, ALICE_CLICK_RETRY_MS)
    }

    private fun tryClickAliceNode(source: String): Boolean {
        if (!aliceClickPending) return false
        val roots = yandexBrowserRoots()
        if (roots.isEmpty()) return false

        // First choice: the exact Yandex Browser Alice control that worked in build95.
        for (root in roots) {
            val exact = runCatching {
                root.findAccessibilityNodeInfosByViewId(ALICE_EXACT_VIEW_ID)
            }.getOrNull().orEmpty()
            for (node in exact) {
                if (clickAliceCandidate(node, "exact_id", source)) return true
            }
        }

        // Fallback: content description used by the old working experiment. We intentionally
        // don't log arbitrary page text; only known Alice descriptions are matched.
        for (root in roots) {
            val queue = ArrayDeque<AccessibilityNodeInfo>()
            queue.add(root)
            var visited = 0
            while (queue.isNotEmpty() && visited < ALICE_NODE_SCAN_LIMIT) {
                val node = queue.removeFirst()
                visited++
                val desc = node.contentDescription?.toString()?.trim()?.lowercase(Locale.ROOT).orEmpty()
                if (desc == "голосовой помощник" || desc == "voice assistant") {
                    if (clickAliceCandidate(node, "content_desc", source)) return true
                }
                val childCount = node.childCount
                for (i in 0 until childCount) {
                    runCatching { node.getChild(i) }.getOrNull()?.let(queue::addLast)
                }
            }
        }
        return false
    }

    private fun clickAliceCandidate(node: AccessibilityNodeInfo, selector: String, source: String): Boolean {
        var target: AccessibilityNodeInfo? = node
        var parentHops = 0
        while (target != null && !target.isClickable && parentHops < ALICE_CLICK_PARENT_LIMIT) {
            target = runCatching { target.parent }.getOrNull()
            parentHops++
        }

        val clickable = target?.isClickable == true
        Log.i(
            TAG,
            "ALICE_NODE_FOUND selector=$selector source=$source " +
                "id=${node.viewIdResourceName ?: "-"} class=${node.className ?: "-"} " +
                "clickable=$clickable parentHops=$parentHops"
        )

        val clicked = clickable && runCatching {
            target?.performAction(AccessibilityNodeInfo.ACTION_CLICK) == true
        }.getOrDefault(false)
        Log.i(TAG, "ALICE_CLICK_RESULT success=$clicked selector=$selector source=$source")
        if (clicked) {
            aliceClickPending = false
            aliceClickGeneration++ // invalidates any timer already queued for this attempt
        }
        return clicked
    }

    private fun yandexBrowserRoots(): List<AccessibilityNodeInfo> {
        val roots = mutableListOf<AccessibilityNodeInfo>()

        runCatching { rootInActiveWindow }.getOrNull()?.let { root ->
            if (root.packageName?.toString() == YANDEX_BROWSER_PACKAGE) roots.add(root)
        }

        val windowList = runCatching {
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                val byDisplay = windowsOnAllDisplays
                (0 until byDisplay.size()).flatMap { byDisplay.valueAt(it) }
            } else {
                windows
            }
        }.getOrNull().orEmpty()

        for (window in windowList) {
            val root = runCatching { window.root }.getOrNull() ?: continue
            if (root.packageName?.toString() == YANDEX_BROWSER_PACKAGE) roots.add(root)
        }
        return roots
    }

    private fun cancelAliceClick(reason: String) {
        if (aliceClickPending) Log.i(TAG, "ALICE_CLICK_CANCEL reason=$reason")
        aliceClickPending = false
        aliceClickAttempt = 0
        yandexWindowLogged = false
        aliceClickGeneration++
    }

'''
s = once(s, anchor, helpers + anchor, "Alice launcher helpers")

# Constants live next to the existing service tag so there is one obvious diagnostic surface.
s = once(
    s,
    '''    companion object {\n        const val TAG = "SteeringWheelKeySvc"\n''',
    '''    companion object {\n        const val TAG = "SteeringWheelKeySvc"\n\n        private const val YANDEX_BROWSER_PACKAGE = "com.yandex.browser"\n        private const val YANDEX_ALICE_URI = "yandexbrowser://alice"\n        private const val APKPURE_YANDEX_SEARCH_URL = "https://apkpure.com/search?q=com.yandex.browser"\n        private const val ALICE_EXACT_VIEW_ID = "com.yandex.browser:id/alice_input_quarknyx"\n        private const val ALICE_WARMUP_MS = 450L\n        private const val ALICE_CLICK_RETRY_MS = 350L\n        private const val ALICE_MAX_CLICK_ATTEMPTS = 8\n        private const val ALICE_NODE_SCAN_LIMIT = 600\n        private const val ALICE_CLICK_PARENT_LIMIT = 4\n''',
    "Alice constants",
)

p.write_text(s)
print("Alice Build 2 Browser/Accessibility patch applied")
