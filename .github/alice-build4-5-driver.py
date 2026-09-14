#!/usr/bin/env python3
from pathlib import Path
import subprocess

p = Path('.github/alice-build4-5-fix.py')
s = p.read_text()
old = '''pat = re.compile(r'(Log\\.i\\(TAG, "DILINK3_304_TRIGGER"\\)\\s*\\n)(\\s*)(launchYandexAliceOrApkPure\\(\\))')
'''
new = '''pat = re.compile(r'(Log\\.i\\(TAG, "DILINK3_304_TRIGGER"\\)\\s*\\n(?:\\s*aliceBootPrewarm\\s*=\\s*false\\s*\\n)?)(\\s*)(launchYandexAliceOrApkPure\\(\\))')
'''
if old not in s:
    raise SystemExit('Alice4.5 driver regex anchor missing')
p.write_text(s.replace(old, new, 1))
subprocess.run(['python3', str(p)], check=True)
