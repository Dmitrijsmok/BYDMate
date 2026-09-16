#!/usr/bin/env python3
from pathlib import Path

p = Path("app/build.gradle.kts")
s = p.read_text()
if 'versionCode = 472' not in s or 'versionName = "3.16.0"' not in s:
    raise SystemExit("Alice5.3 base identity anchor missing: expected upstream v3.16.0 / 472")
s = s.replace('versionCode = 472', 'versionCode = 464', 1)
s = s.replace('versionName = "3.16.0"', 'versionName = "3.15.5"', 1)
p.write_text(s)

print("Alice 5.3 base compatibility applied: upstream 3.16.0 normalized for historical Alice patch chain")
