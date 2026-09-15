#!/usr/bin/env python3
from pathlib import Path


def replace(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"Alice5.0 test anchor missing: {label}")
    p.write_text(s.replace(old, new, 1))

# The Alice side-by-side helper patch intentionally renames the helper process/log.
p = Path("app/src/test/kotlin/com/bydmate/app/data/autoservice/AdbOnDeviceClientTest.kt")
s = p.read_text()
if "bydmate_helper" not in s:
    raise SystemExit("Alice5.0 test anchor missing: helper test identity")
s = s.replace("bydmate_helper", "bydmate_alice1")
p.write_text(s)

# Alice 5.0 keeps the production split guard keyed to BuildConfig.APPLICATION_ID.
# In this build that identity is com.bydmate.app.alice4, not the base package.
replace(
    "app/src/test/kotlin/com/bydmate/app/split/SplitSessionManagerTest.kt",
    'TopTaskInfo("com.bydmate.app", 50, 1, 1, 0)',
    'TopTaskInfo("com.bydmate.app.alice4", 50, 1, 1, 0)',
    "split own-package identity",
)

# Rear-window full travel in 5.0 deliberately uses the live-validated percentage
# channels instead of the legacy synthetic rear open/close action names.
replace(
    "app/src/test/kotlin/com/bydmate/app/data/vehicle/CommandTranslatorTest.kt",
    '''    @Test fun `rear-left open maps to window_rear_left_open val 1`() {
        val r = one("后左打开100")
        assertEquals("window_rear_left_open", r?.actionName)
        assertEquals(1, r?.value)
    }
''',
    '''    @Test fun `rear-left full open maps to validated percent channel`() {
        val r = one("后左打开100")
        assertEquals("window_rear_left_pos", r?.actionName)
        assertEquals(100, r?.value)
    }
''',
    "rear-left full-open expectation",
)
replace(
    "app/src/test/kotlin/com/bydmate/app/data/vehicle/CommandTranslatorTest.kt",
    '''    @Test fun `rear-right close maps to window_rear_right_close val 2`() {
        val r = one("后右打开0")
        assertEquals("window_rear_right_close", r?.actionName)
        assertEquals(2, r?.value)
    }
''',
    '''    @Test fun `rear-right close maps to validated percent channel`() {
        val r = one("后右打开0")
        assertEquals("window_rear_right_pos", r?.actionName)
        assertEquals(0, r?.value)
    }
''',
    "rear-right close expectation",
)

print("Alice 5.0 test compatibility applied")
