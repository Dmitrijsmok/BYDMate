#!/usr/bin/env python3
from pathlib import Path

p = Path('app/build.gradle.kts')
s = p.read_text()
if 'versionCode = 64003' not in s or 'versionName = "3.15.2-alice4.2-fast-guard"' not in s:
    raise SystemExit('Alice4.3 stable identity anchors missing')
s = s.replace('versionCode = 64003', 'versionCode = 64004', 1)
s = s.replace('versionName = "3.15.2-alice4.2-fast-guard"', 'versionName = "3.15.2-alice4.3-stable"', 1)
p.write_text(s)
print('Alice4.3 stable identity applied')
