#!/usr/bin/env python3
from pathlib import Path

# The Alice side-by-side build progressively renames the helper process.
p = Path("app/src/test/kotlin/com/bydmate/app/data/autoservice/AdbOnDeviceClientTest.kt")
s = p.read_text()
if "bydmate_helper" in s:
    s = s.replace("bydmate_helper", "bydmate_alice4")
p.write_text(s)

# Production split guard is keyed to BuildConfig.APPLICATION_ID in this build.
p = Path("app/src/test/kotlin/com/bydmate/app/split/SplitSessionManagerTest.kt")
s = p.read_text()
s = s.replace(
    'TopTaskInfo("com.bydmate.app", 50, 1, 1, 0)',
    'TopTaskInfo("com.bydmate.app.alice4", 50, 1, 1, 0)',
)
p.write_text(s)

# Do NOT rewrite upstream v3.15.5 rear-window expectations. Upstream now owns the
# cross-generation dedicated open/close routing and its tests are authoritative.
print("Alice 5.2 v3.15.5 test compatibility applied")
