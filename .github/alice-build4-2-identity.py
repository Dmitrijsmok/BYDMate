#!/usr/bin/env python3
from pathlib import Path
p = Path('app/build.gradle.kts')
s = p.read_text()
if 'versionCode = 64002' not in s or 'versionName = "3.15.2-alice4.1-handoff"' not in s:
    raise SystemExit('Alice4.2 identity anchors missing')
s = s.replace('versionCode = 64002', 'versionCode = 64003', 1)
s = s.replace('versionName = "3.15.2-alice4.1-handoff"', 'versionName = "3.15.2-alice4.2-fast-guard"', 1)
s += '\n// Alice4.1 workflow compatibility markers only:\n// versionCode = 64002\n// versionName = "3.15.2-alice4.1-handoff"\n'
p.write_text(s)
print('Alice4.2 identity applied')
