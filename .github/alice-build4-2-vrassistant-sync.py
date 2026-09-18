#!/usr/bin/env python3
from pathlib import Path
p = Path('app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt')
s = p.read_text()
old = '            helperClient.setAppHidden("com.byd.autovoice", disabled)\n'
new = old + '            helperClient.setAppHidden("com.byd.vrassistant", disabled)\n'
if old not in s:
    raise SystemExit('settings assistant package anchor missing')
s = s.replace(old, new, 1)
s = s.replace('listOf("com.byd.autovoice", "com.byd.autovoice.engine", "com.byd.autovoice.tts")', 'listOf("com.byd.autovoice", "com.byd.autovoice.engine", "com.byd.autovoice.tts", "com.byd.vrassistant")', 1)
p.write_text(s)

p = Path('app/src/main/kotlin/com/bydmate/app/service/TrackingService.kt')
s = p.read_text()
old = '                        helperClient.setAppHidden("com.byd.autovoice", pref == "true")\n'
new = old + '                        helperClient.setAppHidden("com.byd.vrassistant", pref == "true")\n'
if old not in s:
    raise SystemExit('startup assistant package anchor missing')
s = s.replace(old, new, 1)
p.write_text(s)
print('Alice4.2 DiLink3 assistant package sync applied')
