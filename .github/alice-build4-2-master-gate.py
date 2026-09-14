#!/usr/bin/env python3
from pathlib import Path
p = Path('app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt')
s = p.read_text()
old = '''        val voiceEnabled = voicePrefs.getBoolean("voice_enabled", false)
        val voiceKey = voicePrefs.getInt("voice_keycode", DEFAULT_VOICE_KEYCODE)
        when (voiceDecision(event.keyCode, isDown, voiceEnabled, voiceKey)) {
'''
new = '''        val voiceEnabled = voicePrefs.getBoolean("voice_enabled", false)
        val voiceKey = voicePrefs.getInt("voice_keycode", DEFAULT_VOICE_KEYCODE)
        val nativeTakeover = voicePrefs.getBoolean("alice_native_takeover", false)

        if (event.keyCode == 304 || event.keyCode == 327) {
            if (!nativeTakeover) {
                Log.i(TAG, "DILINK3_MIC_PASS_THROUGH keyCode=${event.keyCode} action=${event.action}")
                return false
            }
            if (event.keyCode == 327) {
                Log.i(TAG, "DILINK3_327_BLOCKED action=${event.action} repeat=${event.repeatCount}")
                return true
            }
            if (isDown && event.repeatCount == 0) {
                Log.i(TAG, "DILINK3_304_TRIGGER")
                launchYandexAliceOrApkPure()
            }
            Log.i(TAG, "DILINK3_304_CONSUMED action=${event.action} repeat=${event.repeatCount}")
            return true
        }

        when (voiceDecision(event.keyCode, isDown, voiceEnabled, voiceKey)) {
'''
if old not in s:
    raise SystemExit('Alice4.2 master gate anchor missing')
p.write_text(s.replace(old, new, 1))
print('Alice4.2 DiLink3 master gate applied')
