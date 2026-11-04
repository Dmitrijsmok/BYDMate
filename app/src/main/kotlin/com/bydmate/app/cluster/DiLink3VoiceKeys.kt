package com.bydmate.app.cluster

// Fork (DiLink3 / Yandex Alice) voice-key decisions, kept out of SteeringWheelKeyDecision.kt so
// upstream's file stays within its detekt function budget. Pure, unit-tested in
// SteeringWheelKeyDecisionVoiceTest.

/**
 * Double-press shortcut while Local BYDMate is selected. Hold the first press briefly instead
 * of starting Local immediately. A second DOWN edge cancels the pending Local start and routes
 * directly to Alice, so the two providers never compete for the microphone.
 */
const val VOICE_DOUBLE_PRESS_WINDOW_MS = 250L

fun isVoiceDoublePress(previousDownMs: Long, nowMs: Long): Boolean =
    previousDownMs > 0L &&
        nowMs >= previousDownMs &&
        nowMs - previousDownMs <= VOICE_DOUBLE_PRESS_WINDOW_MS

/**
 * DiLink 3 / Android 10 microphone key path observed in the field. The firmware emits 304 for
 * the actual press and also surfaces 327 on the same hardware path. Alice previously had an
 * inline special case for these codes, which meant the physical mic button only worked when
 * Alice was selected. Keep the firmware quirk provider-agnostic: 304 triggers whichever voice
 * provider BYDMate selected; 327 is swallowed so the stock BYD assistant does not also react.
 */
fun diLink3VoiceDecision(keyCode: Int, isDown: Boolean, voiceEnabled: Boolean): VoiceKeyDecision {
    if (!voiceEnabled) return VoiceKeyDecision.IGNORE
    return when (keyCode) {
        304 -> if (isDown) VoiceKeyDecision.TRIGGER else VoiceKeyDecision.CONSUME
        327 -> VoiceKeyDecision.CONSUME
        else -> VoiceKeyDecision.IGNORE
    }
}
