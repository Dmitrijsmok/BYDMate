#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt")
s = p.read_text()
old = '        if (!mirrorEnabled && !voiceEnabled && !knobEnabled && !hudController.requiresA11y()) return\n'
new = '''        val nativeAssistantTakeover = getSharedPreferences("voice", Context.MODE_PRIVATE)
            .getBoolean("alice_native_takeover", false)
        if (!mirrorEnabled && !voiceEnabled && !knobEnabled && !nativeAssistantTakeover && !hudController.requiresA11y()) return
'''
if old not in s:
    raise SystemExit("Alice4 recovery gate anchor missing")
p.write_text(s.replace(old, new, 1))
print("Alice4 recovery gate applied")
