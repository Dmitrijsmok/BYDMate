#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, name: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice4.1 anchor missing: {name}")
    return text.replace(old, new, 1)

# Keep the Alice4 application identity so this is an in-place app update when signed
# with the same key. Only advance Android's version code/name.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64001", "versionCode = 64002", "versionCode")
s = once(
    s,
    'versionName = "3.15.2-alice4-unified"',
    'versionName = "3.15.2-alice4.1-handoff"',
    "versionName",
)
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()

# State for the proven two-stage Yandex path:
# cold Browser voice entry -> BroAliceActivity -> exact Alice control -> listening.
s = once(
    s,
    "    private var yandexWindowLogged = false\n",
    "    private var yandexWindowLogged = false\n"
    "    private var aliceColdEntryClicked = false\n"
    "    private var aliceCandidateDumped = false\n",
    "handoff state",
)

# Give slow DiLink3/Yandex transitions a little more time than Build4.
s = once(s, "        private const val ALICE_CLICK_RETRY_MS = 350L\n", "        private const val ALICE_CLICK_RETRY_MS = 300L\n", "retry interval")
s = once(s, "        private const val ALICE_MAX_CLICK_ATTEMPTS = 24\n", "        private const val ALICE_MAX_CLICK_ATTEMPTS = 36\n", "retry attempts")

# Reset phase state whenever a new steering press arms the handoff.
s = once(
    s,
    '''        aliceClickPending = true
        aliceClickAttempt = 0
        yandexWindowLogged = false
        val generation = ++aliceClickGeneration
''',
    '''        aliceClickPending = true
        aliceClickAttempt = 0
        yandexWindowLogged = false
        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        val generation = ++aliceClickGeneration
''',
    "arm state reset",
)

# Replace Build4's too-narrow exact cold-ID matcher with the field-proven Build93
# family matcher. A cold entry click is NON-terminal: keep scanning until the exact
# Alice control appears and click it as phase 2, so one steering press reaches LISTENING.
start = s.find("    private fun tryClickAliceNode(source: String): Boolean {")
end = s.find("    private fun clickAliceCandidate(", start)
if start < 0 or end < 0:
    raise SystemExit("Alice4.1 tryClickAliceNode anchors missing")
new_try = r'''    private fun tryClickAliceNode(source: String): Boolean {
        if (!aliceClickPending) return false
        val roots = yandexBrowserRoots()
        if (roots.isEmpty()) return false

        // Phase 2 / warm path: this exact control is present in the Alice surface.
        // Clicking it is the final action that should put Alice into listening mode.
        for (root in roots) {
            val exact = runCatching {
                root.findAccessibilityNodeInfosByViewId(ALICE_EXACT_VIEW_ID)
            }.getOrNull().orEmpty()
            for (node in exact) {
                if (clickAliceCandidate(node, "exact_alice", source, terminal = true)) {
                    Log.i(TAG, "ALICE4_1_LISTENING_CLICK exact=true coldFirst=$aliceColdEntryClicked")
                    return true
                }
            }
        }

        // Build92/93 also accepted the known Alice accessibility description when
        // Yandex did not expose the exact resource ID on a particular Browser build.
        for (root in roots) {
            val queue = ArrayDeque<AccessibilityNodeInfo>()
            queue.add(root)
            var visited = 0
            while (queue.isNotEmpty() && visited < ALICE_NODE_SCAN_LIMIT) {
                val node = queue.removeFirst()
                visited++
                val desc = node.contentDescription?.toString()?.trim()?.lowercase(Locale.ROOT).orEmpty()
                if (desc == "голосовой помощник" || desc == "voice assistant") {
                    if (clickAliceCandidate(node, "alice_description", source, terminal = true)) {
                        Log.i(TAG, "ALICE4_1_LISTENING_CLICK desc=true coldFirst=$aliceColdEntryClicked")
                        return true
                    }
                }
                for (i in 0 until node.childCount) {
                    runCatching { node.getChild(i) }.getOrNull()?.let(queue::addLast)
                }
            }
        }

        // Phase 1: on the normal Browser screen the working Build93 entry was the
        // omnibox microphone family. Current Yandex versions may suffix/rename the
        // exact ID, so match the stable family and the known accessibility label.
        if (!aliceColdEntryClicked) {
            for (root in roots) {
                val queue = ArrayDeque<AccessibilityNodeInfo>()
                queue.add(root)
                var visited = 0
                while (queue.isNotEmpty() && visited < ALICE_NODE_SCAN_LIMIT) {
                    val node = queue.removeFirst()
                    visited++
                    val id = node.viewIdResourceName?.lowercase(Locale.ROOT).orEmpty()
                    val desc = node.contentDescription?.toString()?.trim()?.lowercase(Locale.ROOT).orEmpty()
                    val coldId = id == ALICE_COLD_VIEW_ID.lowercase(Locale.ROOT) ||
                        id.contains("bro_omnibox_button_microphone")
                    val coldDesc = desc == "активировать голосовой поиск" ||
                        desc == "голосовой поиск" ||
                        desc == "activate voice search" ||
                        desc == "voice search"
                    if (coldId || coldDesc) {
                        if (clickAliceCandidate(node, "cold_voice_entry", source, terminal = false)) {
                            aliceColdEntryClicked = true
                            Log.i(
                                TAG,
                                "ALICE4_1_COLD_ENTRY_CLICKED id=${node.viewIdResourceName ?: "-"} desc=${node.contentDescription ?: "-"}"
                            )
                            // Return false deliberately: the pending timer/event loop must keep
                            // scanning for alice_input_quarknyx and perform phase 2 automatically.
                            return false
                        }
                    }
                    for (i in 0 until node.childCount) {
                        runCatching { node.getChild(i) }.getOrNull()?.let(queue::addLast)
                    }
                }
            }
        }

        // If Yandex changes its IDs again, capture a privacy-safe candidate inventory once.
        // No arbitrary page text is logged: only resource IDs/descriptions containing
        // Alice/voice/microphone-related keywords.
        if (!aliceCandidateDumped && aliceClickAttempt >= 3) {
            aliceCandidateDumped = true
            dumpYandexVoiceCandidates(roots, source)
        }

        Log.d(
            TAG,
            "ALICE4_1_ENTRY_WAIT source=$source coldClicked=$aliceColdEntryClicked attempt=$aliceClickAttempt"
        )
        return false
    }

    private fun dumpYandexVoiceCandidates(roots: List<AccessibilityNodeInfo>, source: String) {
        var emitted = 0
        val seen = mutableSetOf<String>()
        for (root in roots) {
            val queue = ArrayDeque<AccessibilityNodeInfo>()
            queue.add(root)
            var visited = 0
            while (queue.isNotEmpty() && visited < ALICE_NODE_SCAN_LIMIT && emitted < 40) {
                val node = queue.removeFirst()
                visited++
                val id = node.viewIdResourceName?.toString().orEmpty()
                val desc = node.contentDescription?.toString().orEmpty()
                val hay = (id + " " + desc).lowercase(Locale.ROOT)
                val relevant = hay.contains("alice") || hay.contains("алис") ||
                    hay.contains("voice") || hay.contains("голос") ||
                    hay.contains("microphone") || hay.contains("mic")
                if (relevant) {
                    val key = "$id|$desc|${node.className}"
                    if (seen.add(key)) {
                        val r = android.graphics.Rect()
                        runCatching { node.getBoundsInScreen(r) }
                        Log.i(
                            TAG,
                            "YANDEX_A11Y_CANDIDATE source=$source id=${id.ifBlank { "-" }} " +
                                "desc=${desc.ifBlank { "-" }} class=${node.className ?: "-"} " +
                                "clickable=${node.isClickable} bounds=$r"
                        )
                        emitted++
                    }
                }
                for (i in 0 until node.childCount) {
                    runCatching { node.getChild(i) }.getOrNull()?.let(queue::addLast)
                }
            }
        }
        Log.i(TAG, "YANDEX_A11Y_CANDIDATE_DUMP count=$emitted source=$source")
    }

'''
s = s[:start] + new_try + s[end:]

# A cold phase-1 click must not cancel the retry generation. Exact Alice phase-2
# remains terminal and cancels all pending timers exactly as before.
old_sig = "    private fun clickAliceCandidate(node: AccessibilityNodeInfo, selector: String, source: String): Boolean {\n"
new_sig = "    private fun clickAliceCandidate(node: AccessibilityNodeInfo, selector: String, source: String, terminal: Boolean = true): Boolean {\n"
s = once(s, old_sig, new_sig, "click candidate signature")
s = once(
    s,
    '''        if (clicked) {
            aliceClickPending = false
            aliceClickGeneration++ // invalidates any timer already queued for this attempt
        }
        return clicked
''',
    '''        if (clicked && terminal) {
            aliceClickPending = false
            aliceClickGeneration++ // invalidates any timer already queued for this attempt
        }
        return clicked
''',
    "terminal click behavior",
)

# Clear staged state when the handoff is cancelled/unbound/destroyed.
s = once(
    s,
    '''        aliceClickPending = false
        aliceClickAttempt = 0
        yandexWindowLogged = false
        aliceClickGeneration++
''',
    '''        aliceClickPending = false
        aliceClickAttempt = 0
        yandexWindowLogged = false
        aliceColdEntryClicked = false
        aliceCandidateDumped = false
        aliceClickGeneration++
''',
    "cancel state reset",
)

p.write_text(s)
print("Alice Build 4.1 staged Yandex handoff applied")
