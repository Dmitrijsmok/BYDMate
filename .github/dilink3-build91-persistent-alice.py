#!/usr/bin/env python3
from pathlib import Path


def once(s, old, new, name):
    if old not in s:
        raise SystemExit(f"Build91 persistent anchor missing: {name}")
    return s.replace(old, new, 1)

p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text().replace("Build90", "Build91")

s = once(s,
    "    @Volatile private var armedTarget: AssistantTarget? = null\n    @Volatile private var consume304UntilUp: Boolean = false\n",
    "    @Volatile private var armedTarget: AssistantTarget? = null\n    @Volatile private var persistentTarget: AssistantTarget? = null\n    @Volatile private var consume304UntilUp: Boolean = false\n",
    "persistent field")

s = once(s, '''    fun armSteering(context: Context, target: AssistantTarget) {
        if (!active) start(context)
        armedTarget = target
        consume304UntilUp = false
        add("ARM next steering mic 304 -> ${target.title}")
    }
''', '''    fun armSteering(context: Context, target: AssistantTarget) {
        if (!active) start(context)
        armedTarget = target
        consume304UntilUp = false
        add("ARM next steering mic 304 -> ${target.title}")
    }

    fun setPersistentAliceMode(context: Context, enabled: Boolean) {
        if (enabled) {
            if (!active) start(context)
            persistentTarget = AssistantTarget.ALICE
            armedTarget = null
            consume304UntilUp = false
            add("ALICE TEST MODE ON")
        } else {
            persistentTarget = null
            armedTarget = null
            consume304UntilUp = false
            add("ALICE TEST MODE OFF")
        }
    }

    fun isPersistentAliceMode(): Boolean = persistentTarget == AssistantTarget.ALICE
''', "persistent helpers")

s = once(s, '''    fun maybeHandleSteering(context: Context, event: KeyEvent): Boolean {
        if (!active || event.keyCode != MIC_KEYCODE) return false
''', '''    fun maybeHandleSteering(context: Context, event: KeyEvent): Boolean {
        if (event.keyCode != MIC_KEYCODE) return false
        if (!active && persistentTarget == null) return false
''', "persistent gate")

s = once(s, '''        val target = armedTarget ?: return false
        if (event.action != KeyEvent.ACTION_DOWN || event.repeatCount != 0) return false

        armedTarget = null
        consume304UntilUp = true
        add("KEY 304 armed hit scan=${event.scanCode}; bypass BYDMate once -> ${target.title}")
''', '''        val oneShot = armedTarget
        val target = oneShot ?: persistentTarget ?: return false
        if (event.action != KeyEvent.ACTION_DOWN || event.repeatCount != 0) return false

        if (oneShot != null) armedTarget = null
        consume304UntilUp = true
        add("KEY 304 route=${if (oneShot != null) "one-shot" else "persistent"} -> ${target.title}")
''', "persistent target")

s = once(s, '''    private var gptButton: Button? = null
    private var minButton: Button? = null
    private var minimized = false
''', '''    private var gptButton: Button? = null
    private var minButton: Button? = null
    private var aliceModeButton: Button? = null
    private var minimized = false
''', "mode field")

s = once(s, '''        gptButton = null
        minButton = null
        handler.removeCallbacks(refreshRunnable)
''', '''        gptButton = null
        minButton = null
        aliceModeButton = null
        handler.removeCallbacks(refreshRunnable)
''', "mode cleanup")

s = once(s, '''        aliceButton = alice
        gptButton = gpt
        content.addView(buttonRow(context, alice, gpt))

        content.addView(buttonRow(context,
''', '''        aliceButton = alice
        gptButton = gpt
        content.addView(buttonRow(context, alice, gpt))

        val aliceMode = actionButton(context, "ALICE TEST MODE: OFF") {
            AssistantLabTrace.setPersistentAliceMode(context, !AssistantLabTrace.isPersistentAliceMode())
            refresh()
        }
        aliceModeButton = aliceMode
        content.addView(buttonRow(context, aliceMode))

        content.addView(buttonRow(context,
''', "mode ui")

s = once(s, '''            append(if (AssistantLabTrace.active) "● TRACE ON" else "○ TRACE OFF")
''', '''            append(if (AssistantLabTrace.active) "● TRACE ON" else "○ TRACE OFF")
            append("  ·  BUILD 91")
            append("\\nAlice Test Mode: ").append(if (AssistantLabTrace.isPersistentAliceMode()) "ON" else "OFF")
''', "status")

s = once(s, '''        aliceButton?.text = if (alice == null) "УСТАНОВИТЬ YANDEX" else "ТЕСТ ALICE"
''', '''        aliceButton?.text = if (alice == null) "УСТАНОВИТЬ YANDEX" else "ТЕСТ ALICE"
        aliceModeButton?.text = if (AssistantLabTrace.isPersistentAliceMode()) "ALICE TEST MODE: ON" else "ALICE TEST MODE: OFF"
''', "mode label")

p.write_text(s)
print("Build91 persistent Alice mode applied")
