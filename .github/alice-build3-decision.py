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
    if (!voiceEnabled) return VoiceKeyDecision.IGNORE
    if (voiceKeyCode == DILINK3_ALICE_ROUTE) {
        if (keyCode == 327) return VoiceKeyDecision.CONSUME
        if (keyCode == 304) return if (isDown) VoiceKeyDecision.TRIGGER else VoiceKeyDecision.CONSUME
        return VoiceKeyDecision.IGNORE
    }
    if (keyCode != voiceKeyCode) return VoiceKeyDecision.IGNORE
    return if (isDown) VoiceKeyDecision.TRIGGER else VoiceKeyDecision.CONSUME
}
'''
if old not in s:
    raise SystemExit("Alice3 voiceDecision anchor missing")
p.write_text(s.replace(old, new, 1))
print("Alice3 DiLink3 voice decision applied")
