#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
old = '''        appContext.getSharedPreferences("voice", Context.MODE_PRIVATE).edit()
            .putInt("voice_keycode", if (disabled) com.bydmate.app.cluster.DILINK3_ALICE_ROUTE else 0)
            .apply()
'''
new = '''        appContext.getSharedPreferences("voice", Context.MODE_PRIVATE).edit()
            .putInt("voice_keycode", if (disabled) com.bydmate.app.cluster.DILINK3_ALICE_ROUTE else 0)
            .putBoolean("alice_native_takeover", disabled)
            .apply()
'''
if old not in s:
    raise SystemExit("Alice4 native mirror anchor missing")
p.write_text(s.replace(old, new, 1))
print("Alice4 native takeover mirror applied")
