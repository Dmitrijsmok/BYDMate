#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyDecision.kt")
s = p.read_text()
old = '''fun voiceDecision(keyCode: Int, isDown: Boolean, voiceEnabled: Boolean, voiceKeyCode: Int): VoiceKeyDecision {
    if (!voiceEnabled || keyCode != voiceKeyCode) return VoiceKeyDecision.IGNORE
    return if (isDown) VoiceKeyDecision.TRIGGER else VoiceKeyDecision.CONSUME
}
'''
new = '''const val DILINK3_ALICE_ROUTE = 1304

fun voiceDecision(keyCode: Int, isDown: Boolean, voiceEnabled: Boolean, voiceKeyCode: Int): VoiceKeyDecision {
    // Alice4: the native-assistant takeover toggle owns the DiLink3 route independently from
    // the local BYDMate voice pipeline. This keeps 304/327 handling alive even when the old
    // Voice commands switch is off.
    if (voiceKeyCode == DILINK3_ALICE_ROUTE) {
        if (keyCode == 327) return VoiceKeyDecision.CONSUME
        if (keyCode == 304) return if (isDown) VoiceKeyDecision.TRIGGER else VoiceKeyDecision.CONSUME
        return VoiceKeyDecision.IGNORE
    }
    if (!voiceEnabled || keyCode != voiceKeyCode) return VoiceKeyDecision.IGNORE
    return if (isDown) VoiceKeyDecision.TRIGGER else VoiceKeyDecision.CONSUME
}
'''
if old not in s:
    raise SystemExit("Alice3 voiceDecision anchor missing")
p.write_text(s.replace(old, new, 1))
print("Alice4 DiLink3 voice decision applied")
