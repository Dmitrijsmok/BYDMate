#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60037"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build87 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Monotonic upgrade identity over Build86. Same package/signing chain.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60036", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build86"',
    '            versionNameSuffix = "-dilink3-production-build87"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build86"',
    'android:label="BYDMate DiLink3 Build87"',
    "manifest label",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Assistant Lab UX: make minimization explicit and make the installed-app TEST buttons
#    prepare a true native handoff. The external app gets the microphone/audio path; BYDMate
#    does not transcribe the utterance and does not synthesize the answer for an armed 304.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text()
s = s.replace("Build86", "Build87")

s = replace_once(
    s,
    '''    private var gptButton: Button? = null
    private var minimized = false
''',
    '''    private var gptButton: Button? = null
    private var minButton: Button? = null
    private var minimized = false
''',
    "minimize button state",
)

s = replace_once(
    s,
    '''        aliceButton = null
        gptButton = null
        handler.removeCallbacks(refreshRunnable)
''',
    '''        aliceButton = null
        gptButton = null
        minButton = null
        handler.removeCallbacks(refreshRunnable)
''',
    "minimize button cleanup",
)

s = replace_once(
    s,
    '''        val min = smallButton(context, "—") { toggleSize(context) }
        val close = smallButton(context, "×") { hide() }
        header.addView(min)
''',
    '''        val min = smallButton(context, "СВЕРНУТЬ") { toggleSize(context) }.apply {
            textSize = 10f
            layoutParams = LinearLayout.LayoutParams(dp(context, 150), dp(context, 44))
        }
        minButton = min
        val close = smallButton(context, "×") { hide() }
        header.addView(min)
''',
    "visible minimize button",
)

s = replace_once(
    s,
    '''        if (AssistantLabLauncher.isInstalled(context, target)) {
            AssistantLabLauncher.launch(context, target, preferVoice = true)
        } else {
''',
    '''        if (AssistantLabLauncher.isInstalled(context, target)) {
            // Native handoff test: arm the next physical 304 before launching the external app.
            // That 304 is consumed before the frozen Build85 voice route, so BYDMate ASR/TTS is
            // not started. The external app owns microphone capture and its own voice playback.
            AssistantLabTrace.armSteering(context, target)
            AssistantLabTrace.add("NATIVE HANDOFF prepared for ${target.title}; BYDMate ASR/TTS bypassed for next 304")
            AssistantLabLauncher.launch(context, target, preferVoice = true)
            minimize(context)
        } else {
''',
    "native launch handoff",
)

s = s.replace(
    '''                    AssistantLabTrace.armSteering(context, AssistantTarget.ALICE)
                    Toast.makeText(context, "Следующее нажатие микрофона пойдёт в Alice", Toast.LENGTH_SHORT).show()
''',
    '''                    AssistantLabTrace.armSteering(context, AssistantTarget.ALICE)
                    AssistantLabTrace.add("NATIVE HANDOFF Alice armed; 327 remains blocked by BYDMate")
                    minimize(context)
                    Toast.makeText(context, "Следующее нажатие: нативная Alice, BYDMate TTS выключен для этого запроса", Toast.LENGTH_SHORT).show()
''',
    1,
)
s = s.replace(
    '''                    AssistantLabTrace.armSteering(context, AssistantTarget.CHATGPT)
                    Toast.makeText(context, "Следующее нажатие микрофона пойдёт в ChatGPT", Toast.LENGTH_SHORT).show()
''',
    '''                    AssistantLabTrace.armSteering(context, AssistantTarget.CHATGPT)
                    AssistantLabTrace.add("NATIVE HANDOFF ChatGPT armed; 327 remains blocked by BYDMate")
                    minimize(context)
                    Toast.makeText(context, "Следующее нажатие: нативный ChatGPT, BYDMate TTS выключен для этого запроса", Toast.LENGTH_SHORT).show()
''',
    1,
)

s = replace_once(
    s,
    '''            append("\\nКнопки РУЛЬ→… перенаправляют только ОДНО следующее нажатие 304; обычный Build85 маршрут не меняется.")
''',
    '''            append("\\nNATIVE: для вооружённого 304 BYDMate полностью пропускает ASR/TTS; внешний ассистент сам слушает и говорит. 327 остаётся заблокирован. Обычный Build85 маршрут не меняется.")
''',
    "native status hint",
)

s = replace_once(
    s,
    '''    private fun toggleSize(context: Context) {
        minimized = !minimized
        expandedContent?.visibility = if (minimized) View.GONE else View.VISIBLE
        val p = params ?: return
        p.width = dp(context, if (minimized) 430 else 900)
        p.height = if (minimized) WindowManager.LayoutParams.WRAP_CONTENT else dp(context, 690)
        root?.let { runCatching { wm?.updateViewLayout(it, p) } }
    }
''',
    '''    private fun toggleSize(context: Context) = setMinimized(context, !minimized)

    private fun minimize(context: Context) = setMinimized(context, true)

    private fun setMinimized(context: Context, value: Boolean) {
        minimized = value
        expandedContent?.visibility = if (minimized) View.GONE else View.VISIBLE
        minButton?.text = if (minimized) "РАЗВЕРНУТЬ" else "СВЕРНУТЬ"
        val p = params ?: return
        p.width = dp(context, if (minimized) 520 else 900)
        p.height = if (minimized) WindowManager.LayoutParams.WRAP_CONTENT else dp(context, 690)
        root?.let { runCatching { wm?.updateViewLayout(it, p) } }
        AssistantLabTrace.add(if (minimized) "OVERLAY minimized; trace continues" else "OVERLAY expanded")
    }
''',
    "explicit minimize-expand",
)

p.write_text(s)


# ---------------------------------------------------------------------------
# 3) Hard native handoff guard. Even if a previous BYDMate voice turn is still speaking/listening,
#    an armed external 304 stops BYDMate TTS/capture before the posted Alice/ChatGPT launch runs.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/voice/VoiceController.kt")
s = p.read_text()
s = replace_once(
    s,
    "import com.bydmate.app.agent.AgentResult\n",
    "import com.bydmate.app.agent.AgentResult\nimport com.bydmate.app.assistantlab.AssistantLabTrace\n",
    "AssistantLabTrace import",
)

anchor = '''    /** DiLink3 physical steering microphone: one command per press. */
    fun onSteeringPttPressed() {
'''
insert = '''    /** Build87: relinquish BYDMate voice resources before a native external-assistant handoff.
     *  This does not change the normal Build85 route; it is called only after Assistant Lab has
     *  consumed an explicitly armed 304. */
    fun stopForExternalAssistant() {
        AssistantLabTrace.add("BYDMATE native handoff: stop local capture/TTS before external assistant")
        stopRequested.set(true)
        runCatching { ttsEngine.stop() }
        cancellableAskJob?.cancel()
        routingJob?.cancel()
        sessionJob?.cancel()
        runCatching { hideListeningOverlay() }
    }

    /** DiLink3 physical steering microphone: one command per press. */
    fun onSteeringPttPressed() {
'''
s = replace_once(s, anchor, insert, "external handoff stop method")
p.write_text(s)


# ---------------------------------------------------------------------------
# 4) Call the hard handoff guard before returning from the Assistant Lab key interceptor.
#    The posted launcher runs on the main loop after this method returns, so mic/TTS teardown wins.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()
s = replace_once(
    s,
    '''        AssistantLabTrace.onKeyEvent(event)
        if (AssistantLabTrace.maybeHandleSteering(applicationContext, event)) return true
''',
    '''        AssistantLabTrace.onKeyEvent(event)
        if (AssistantLabTrace.maybeHandleSteering(applicationContext, event)) {
            entryPoint().voiceController().stopForExternalAssistant()
            AssistantLabTrace.add("STEERING external route consumed 304 before Build85 voice decision")
            return true
        }
''',
    "hard native steering handoff",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 5) Visible Settings copy for Build87. Build85 baseline remains frozen beneath the lab.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
s = s.replace('SectionHeader(text = "Assistant Lab · Build86")', 'SectionHeader(text = "Assistant Lab · Build87")', 1)
s = s.replace(
    "Плавающее окно остаётся поверх внешнего приложения и сворачивается в компактную панель.",
    "Плавающее окно остаётся поверх внешнего приложения. Кнопка СВЕРНУТЬ делает его компактным; trace продолжает писаться. В нативном тесте BYDMate освобождает микрофон/TTS и не озвучивает ответ Дмитрием.",
    1,
)
p.write_text(s)

print("Build87 applied: frozen Build85 + Build86 lab + native Alice/ChatGPT audio handoff + explicit minimize")
