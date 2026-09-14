#!/usr/bin/env python3
from pathlib import Path
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()
old = '        private const val ALICE_COLD_VIEW_ID = "com.yandex.browser:id/bro_omnibox_button_microphone_inactive"\n'
new = old + '        private const val ALICE_COLD_CURRENT_VIEW_ID = "com.yandex.browser:id/bro_omnibox_button_mic"\n'
if old not in s:
    raise SystemExit('Alice4.2 cold id anchor missing')
s = s.replace(old, new, 1)
if '        private const val ALICE_CLICK_RETRY_MS = 300L\n' not in s:
    raise SystemExit('Alice4.2 retry anchor missing')
s = s.replace('        private const val ALICE_CLICK_RETRY_MS = 300L\n', '        private const val ALICE_CLICK_RETRY_MS = 180L\n', 1)
anchor = '''        // Phase 1: on the normal Browser screen the working Build93 entry was the
        // omnibox microphone family. Current Yandex versions may suffix/rename the
        // exact ID, so match the stable family and the known accessibility label.
        if (!aliceColdEntryClicked) {
'''
insert = '''        // Alice4.2 field log exposed the current exact cold id. Probe exact ids first;
        // findAccessibilityNodeInfosByViewId is much cheaper than walking the whole tree.
        if (!aliceColdEntryClicked) {
            for (root in roots) {
                for (coldId in listOf(ALICE_COLD_CURRENT_VIEW_ID, ALICE_COLD_VIEW_ID)) {
                    val nodes = runCatching { root.findAccessibilityNodeInfosByViewId(coldId) }
                        .getOrNull().orEmpty()
                    for (node in nodes) {
                        if (clickAliceCandidate(node, "cold_exact_id", source, terminal = false)) {
                            aliceColdEntryClicked = true
                            Log.i(TAG, "ALICE4_2_COLD_ENTRY_CLICKED id=${node.viewIdResourceName ?: "-"} desc=${node.contentDescription ?: "-"}")
                            return false
                        }
                    }
                }
            }
        }

''' + anchor
if anchor not in s:
    raise SystemExit('Alice4.2 phase1 anchor missing')
s = s.replace(anchor, insert, 1)
p.write_text(s)
print('Alice4.2 Yandex exact-id speed patch applied')
