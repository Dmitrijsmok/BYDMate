#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice5.3 anchor missing: {label}")
    return text.replace(old, new, 1)

# Final identity after the validated Alice 5.2 patch chain.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64013", "versionCode = 64014", "versionCode")
s = once(
    s,
    'versionName = "3.15.5-alice5.2-upstream-rebase"',
    'versionName = "3.16.0-alice5.3-upstream-rebase"',
    "versionName",
)
p.write_text(s)

# The historical Browser patch expects the pre-3.16.0 accessibility-event body.
# alice-build5-3-base-compat.py temporarily normalizes that single hook so the
# validated Alice chain can apply unchanged. By the end of the 5.2 chain Build95
# has expanded this method with the vrassistant any-event guard. Restore the new
# v3.16.0 foreground hint after eventPkg is known, before that guard can return.
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
post_52_anchor = '''        if (event == null) return\n        val eventPkg = event.packageName?.toString().orEmpty()\n        val nativeTakeover = applicationContext.getSharedPreferences("voice", Context.MODE_PRIVATE)\n'''
merged_anchor = '''        if (event == null) return\n        val eventPkg = event.packageName?.toString().orEmpty()\n\n        // Upstream v3.16.0 fast foreground hint. ForegroundHintFilter keeps Android 10 /\n        // DiLink 3 on the legacy-safe path and only performs display-aware filtering on R+.\n        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED && eventPkg.isNotBlank()) {\n            if (ForegroundHintFilter.allows(this, event, eventPkg)) {\n                entryPoint().cameraStateMonitor().onForegroundHint(eventPkg)\n            }\n        }\n\n        val nativeTakeover = applicationContext.getSharedPreferences("voice", Context.MODE_PRIVATE)\n'''
s = once(s, post_52_anchor, merged_anchor, "post-5.2 v3.16.0 foreground hint merge")
p.write_text(s)

# v3.16.0 adds native BYDMate vocabulary for individual window half-open and
# front/rear paired half/vent commands. Expose those semantics to the Alice bridge
# without adding any raw FID/value surface.
p = Path("app/src/main/kotlin/com/bydmate/app/data/remote/AliceBridgeCommandTranslator.kt")
s = p.read_text()
s = s.replace(
    " * 5.2 is rebased on upstream BYDMate v3.15.5 and deliberately reuses upstream\n * vehicle command mappings wherever they exist (fan level and airflow included).",
    " * 5.3 is rebased on upstream BYDMate v3.16.0 and deliberately reuses upstream\n * vehicle command mappings wherever they exist (fan, airflow and window presets included).",
)

replacements = [
    (
        '            "window.driver.vent" -> "主驾通风"\n            "window.driver.position" -> windowPosition("主驾", json) ?: return null\n',
        '            "window.driver.vent" -> "主驾通风"\n            "window.driver.half" -> "主驾半开"\n            "window.driver.position" -> windowPosition("主驾", json) ?: return null\n',
        "driver half",
    ),
    (
        '            "window.passenger.vent" -> "副驾通风"\n            "window.passenger.position" -> windowPosition("副驾", json) ?: return null\n',
        '            "window.passenger.vent" -> "副驾通风"\n            "window.passenger.half" -> "副驾半开"\n            "window.passenger.position" -> windowPosition("副驾", json) ?: return null\n',
        "passenger half",
    ),
    (
        '            "window.rear_left.vent" -> "后左通风"\n            "window.rear_left.position" -> windowPosition("后左", json) ?: return null\n',
        '            "window.rear_left.vent" -> "后左通风"\n            "window.rear_left.half" -> "后左半开"\n            "window.rear_left.position" -> windowPosition("后左", json) ?: return null\n',
        "rear-left half",
    ),
    (
        '            "window.rear_right.vent" -> "后右通风"\n            "window.rear_right.position" -> windowPosition("后右", json) ?: return null\n',
        '            "window.rear_right.vent" -> "后右通风"\n            "window.rear_right.half" -> "后右半开"\n            "window.rear_right.position" -> windowPosition("后右", json) ?: return null\n',
        "rear-right half",
    ),
    (
        '            "window.all.vent" -> "车窗通风"\n\n            // Locks / trunks\n',
        '            "window.all.vent" -> "车窗通风"\n            "window.front.open" -> "前排车窗全开"\n            "window.front.close" -> "前排车窗关闭"\n            "window.front.half" -> "前排车窗半开"\n            "window.front.vent" -> "前排车窗通风"\n            "window.rear.open" -> "后排车窗全开"\n            "window.rear.close" -> "后排车窗关闭"\n            "window.rear.half" -> "后排车窗半开"\n            "window.rear.vent" -> "后排车窗通风"\n\n            // Locks / trunks\n',
        "paired window presets",
    ),
]
for old, new, label in replacements:
    if new not in s:
        s = once(s, old, new, label)

supported_anchor = '        "window.driver.vent",\n        "window.driver.position",\n'
if '        "window.driver.half",\n' not in s:
    s = once(s, supported_anchor,
        '        "window.driver.vent",\n        "window.driver.half",\n        "window.driver.position",\n',
        "supported driver half")

for old, new, label in [
    ('        "window.passenger.vent",\n        "window.passenger.position",\n',
     '        "window.passenger.vent",\n        "window.passenger.half",\n        "window.passenger.position",\n', "supported passenger half"),
    ('        "window.rear_left.vent",\n        "window.rear_left.position",\n',
     '        "window.rear_left.vent",\n        "window.rear_left.half",\n        "window.rear_left.position",\n', "supported rear-left half"),
    ('        "window.rear_right.vent",\n        "window.rear_right.position",\n',
     '        "window.rear_right.vent",\n        "window.rear_right.half",\n        "window.rear_right.position",\n', "supported rear-right half"),
]:
    if new not in s:
        s = once(s, old, new, label)

if '        "window.front.open",\n' not in s:
    s = once(
        s,
        '        "window.all.vent",\n\n        "doors.lock",\n',
        '        "window.all.vent",\n        "window.front.open",\n        "window.front.close",\n        "window.front.half",\n        "window.front.vent",\n        "window.rear.open",\n        "window.rear.close",\n        "window.rear.half",\n        "window.rear.vent",\n\n        "doors.lock",\n',
        "supported paired windows",
    )

p.write_text(s)

# v3.16.0 added CameraForegroundHintTest with the upstream package literal.
# In the side-by-side Alice build the real application id is com.bydmate.app.alice4,
# so adapt only that identity assertion; production CameraStateMonitor already uses
# context.packageName and therefore behaves correctly for the renamed package.
p = Path("app/src/test/kotlin/com/bydmate/app/data/camera/CameraForegroundHintTest.kt")
s = p.read_text()
s = once(
    s,
    '        monitor.onForegroundHint("com.bydmate.app")\n',
    '        monitor.onForegroundHint("com.bydmate.app.alice4")\n',
    "CameraForegroundHintTest side-by-side package identity",
)
p.write_text(s)

print("Alice 5.3 final patch applied: v3.16.0 accessibility merge + identity + upstream window preset semantics + camera test identity")
