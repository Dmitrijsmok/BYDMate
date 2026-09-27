package com.bydmate.app.cluster

/** DiLink 3 / Android 10 microphone key path observed on the user's head unit. */
fun diLink3VoiceDecision(keyCode: Int, isDown: Boolean, voiceEnabled: Boolean): VoiceKeyDecision {
    if (!voiceEnabled) return VoiceKeyDecision.IGNORE
    return when (keyCode) {
        304 -> if (isDown) VoiceKeyDecision.TRIGGER else VoiceKeyDecision.CONSUME
        327 -> VoiceKeyDecision.CONSUME
        else -> VoiceKeyDecision.IGNORE
    }
}
