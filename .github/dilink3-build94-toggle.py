#!/usr/bin/env python3
from pathlib import Path

def once(s, old, new, name):
    if old not in s:
        raise SystemExit(f"Build94 toggle anchor missing: {name}")
    return s.replace(old, new, 1)

p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
s = once(s,
'''        val diLink3Platform = diLink3TakeoverSupported(android.os.Build.VERSION.SDK_INT)
        val diLink3Takeover = diLink3Platform && voiceEnabled
''',
'''        val diLink3Platform = diLink3TakeoverSupported(android.os.Build.VERSION.SDK_INT)
        val ownershipPref = if (voicePrefs.contains("dilink3_steering_assistant")) {
            voicePrefs.getBoolean("dilink3_steering_assistant", false)
        } else voiceEnabled
        val diLink3Takeover = diLink3Platform && voiceEnabled && ownershipPref
''', "ownership")
s = once(s,
'''        if (AssistantLabTrace.shouldHardBlockStock327(event)) {
''',
'''        if (AssistantLabTrace.shouldHardBlockStock327(applicationContext, event)) {
''', "gate context")
p.write_text(s)

p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text()
anchor = '''    fun armAliceHard327Block(durationMs: Long = 4_000L) {
'''
helper = '''    private fun steeringOwnershipEnabled(context: Context): Boolean {
        val p = context.applicationContext.getSharedPreferences("voice", Context.MODE_PRIVATE)
        return if (p.contains("dilink3_steering_assistant")) {
            p.getBoolean("dilink3_steering_assistant", false)
        } else p.getBoolean("voice_enabled", false)
    }

'''
s = once(s, anchor, helper + anchor, "helper")
s = once(s,
'''    fun shouldHardBlockStock327(event: KeyEvent): Boolean {
        if (event.keyCode != 327) return false
''',
'''    fun shouldHardBlockStock327(context: Context, event: KeyEvent): Boolean {
        if (event.keyCode != 327) return false
        if (!steeringOwnershipEnabled(context)) return false
''', "gate setting")
s = once(s,
'''    fun maybeHandleSteering(context: Context, event: KeyEvent): Boolean {
        if (event.keyCode != MIC_KEYCODE) return false
''',
'''    fun maybeHandleSteering(context: Context, event: KeyEvent): Boolean {
        if (event.keyCode != MIC_KEYCODE) return false
        if (!steeringOwnershipEnabled(context)) return false
''', "route setting")
p.write_text(s)

print("Build94 steering ownership setting applied")
