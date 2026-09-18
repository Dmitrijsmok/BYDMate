#!/usr/bin/env python3
from pathlib import Path

p = Path("app/build.gradle.kts")
s = p.read_text()

if "versionCode = 64012" not in s:
    raise SystemExit("Alice5.2 anchor missing: expected 5.1 versionCode 64012")
if 'versionName = "3.15.2-alice5.1-app-bridge"' not in s:
    raise SystemExit("Alice5.2 anchor missing: expected 5.1 versionName")

s = s.replace("versionCode = 64012", "versionCode = 64013", 1)
s = s.replace(
    'versionName = "3.15.2-alice5.1-app-bridge"',
    'versionName = "3.15.5-alice5.2-upstream-rebase"',
    1,
)
p.write_text(s)
print("Alice 5.2 identity applied: 64013 / 3.15.5-alice5.2-upstream-rebase")
