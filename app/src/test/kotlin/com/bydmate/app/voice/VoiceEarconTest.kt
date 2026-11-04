package com.bydmate.app.voice

import android.media.AudioManager
import org.junit.Assert.assertEquals
import org.junit.Test

class VoiceEarconTest {

    @Test
    fun `android 10 head units beep on the alarm stream at full volume`() {
        assertEquals(AudioManager.STREAM_ALARM to 100, VoiceEarcon(legacyHeadUnit = true).primaryRoute())
        // The caller's volume does not apply there: the DiLink 3.0 cue must not be quiet.
        assertEquals(AudioManager.STREAM_ALARM to 100, VoiceEarcon(volume = 40, legacyHeadUnit = true).primaryRoute())
    }

    @Test
    fun `newer head units keep the BYD voice stream at the configured volume`() {
        assertEquals(SherpaTtsEngine.BYD_STREAM_BTTS to 70, VoiceEarcon(legacyHeadUnit = false).primaryRoute())
        assertEquals(SherpaTtsEngine.BYD_STREAM_BTTS to 40, VoiceEarcon(volume = 40, legacyHeadUnit = false).primaryRoute())
    }
}
