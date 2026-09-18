#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()

s = s.replace(
    '        private const val ALICE_EXACT_VIEW_ID = "com.yandex.browser:id/alice_input_quarknyx"\n',
    '        private const val ALICE_EXACT_VIEW_ID = "com.yandex.browser:id/alice_input_quarknyx"\n'
    '        private const val ALICE_COLD_VIEW_ID = "com.yandex.browser:id/bro_omnibox_button_microphone_inactive"\n',
    1,
)
s = s.replace('        private const val ALICE_WARMUP_MS = 450L\n', '        private const val ALICE_WARMUP_MS = 150L\n', 1)
s = s.replace('        private const val ALICE_MAX_CLICK_ATTEMPTS = 8\n', '        private const val ALICE_MAX_CLICK_ATTEMPTS = 24\n', 1)

old = '        Log.d(TAG, "ALICE_TOOLBAR_EXACT_NOT_FOUND source=$source")\n'
new = '''        for (root in roots) {
            val coldNodes = runCatching { root.findAccessibilityNodeInfosByViewId(ALICE_COLD_VIEW_ID) }
                .getOrNull().orEmpty()
            for (node in coldNodes) {
                if (clickAliceCandidate(node, "cold_omnibox_mic", source)) return true
            }
        }
        Log.d(TAG, "ALICE4_ENTRY_NOT_FOUND source=$source")
'''
if old not in s:
    raise SystemExit("Alice4 cold entry anchor missing")
s = s.replace(old, new, 1)

p.write_text(s)
print("Alice4 cold Yandex entry patch applied")
