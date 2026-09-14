#!/usr/bin/env python3
from pathlib import Path

p = Path('.github/alice-build4-7-fix.py')
s = p.read_text()
old = '&&\n            event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {'
new = '&& event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {'
if old not in s:
    raise SystemExit('Alice4.7 formatting anchor not found')
p.write_text(s.replace(old, new, 1))
print('Alice4.7 formatting anchor normalized')
