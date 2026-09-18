#!/usr/bin/env python3
from pathlib import Path

p = Path("app/build.gradle.kts")
s = p.read_text()
if 'versionCode = 472' not in s or 'versionName = "3.16.0"' not in s:
    raise SystemExit("Alice5.3 base identity anchor missing: expected upstream v3.16.0 / 472")
s = s.replace('versionCode = 472', 'versionCode = 464', 1)
s = s.replace('versionName = "3.16.0"', 'versionName = "3.15.5"', 1)
p.write_text(s)

# v3.16.0 expanded onAccessibilityEvent() with the CameraStateMonitor foreground
# hint. The historical Alice Browser patch intentionally remains unchanged and
# matches the validated v3.15.5 body, so normalize only this hook before applying
# the old chain. alice-build5-3-final.py restores the v3.16.0 hint alongside Alice.
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
upstream_hook = '''    // Single volatile read when the HUD feature is off - see NavA11yFeed.enabled.\n    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n        NavA11yFeed.onEvent(this, event)\n        // Whoever just took the MAIN screen, reported the moment it happens: the blind-spot\n        // window has to be gone before the native 360 view is drawn, and the UsageStats poll is\n        // half a second behind. Events from the cluster are dropped by the filter, and the poll\n        // stays the fallback for everything the hints miss.\n        if (event?.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {\n            val pkg = event.packageName?.toString()\n            if (pkg != null && ForegroundHintFilter.allows(this, event, pkg)) {\n                entryPoint().cameraStateMonitor().onForegroundHint(pkg)\n            }\n        }\n    }\n'''
legacy_hook = '''    // Single volatile read when the HUD feature is off - see NavA11yFeed.enabled.\n    override fun onAccessibilityEvent(event: AccessibilityEvent?) {\n        NavA11yFeed.onEvent(this, event)\n    }\n'''
if upstream_hook not in s:
    raise SystemExit("Alice5.3 base accessibility anchor missing: expected upstream v3.16.0 foreground hint")
s = s.replace(upstream_hook, legacy_hook, 1)
p.write_text(s)

print("Alice 5.3 base compatibility applied: upstream 3.16.0 identity + accessibility hook normalized for historical Alice patch chain")
