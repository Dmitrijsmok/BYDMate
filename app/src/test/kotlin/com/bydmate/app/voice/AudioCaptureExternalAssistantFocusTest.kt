package com.bydmate.app.voice

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

/**
 * The external-Alice hand-off holds audio focus and never touches STREAM_MUSIC: Alice in Yandex
 * Browser speaks on that stream, so a volume duck silenced her (field 1.1.1/1.1.2).
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29])
class AudioCaptureExternalAssistantFocusTest {
    private val context: Context get() = ApplicationProvider.getApplicationContext()
    private val audioManager get() = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    private fun capture() = AudioCapture(audioManager, context.getSharedPreferences("duck", Context.MODE_PRIVATE))

    @Test fun `holding focus leaves the media volume alone and repeats keep one request`() {
        audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, 11, 0)
        val capture = capture()

        assertTrue(capture.holdFocusForExternalAssistant())
        val first = shadowOf(audioManager).lastAudioFocusRequest
        assertTrue(capture.holdFocusForExternalAssistant())

        assertEquals(11, audioManager.getStreamVolume(AudioManager.STREAM_MUSIC))
        assertEquals(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK, first.durationHint)
        assertEquals(AudioAttributes.USAGE_ASSISTANT, first.audioFocusRequest.audioAttributes.usage)
        assertTrue(first === shadowOf(audioManager).lastAudioFocusRequest)
    }

    @Test fun `release abandons the held request and a new press requests again`() {
        val capture = capture()
        capture.holdFocusForExternalAssistant()
        val held = shadowOf(audioManager).lastAudioFocusRequest.audioFocusRequest

        capture.releaseExternalAssistantFocus()
        assertEquals(held, shadowOf(audioManager).lastAbandonedAudioFocusRequest)

        assertTrue(capture.holdFocusForExternalAssistant())
        val again = shadowOf(audioManager).lastAudioFocusRequest.audioFocusRequest
        assertTrue(again !== held)
    }

    @Test fun `a refused request is not held`() {
        shadowOf(audioManager).setNextFocusRequestResponse(AudioManager.AUDIOFOCUS_REQUEST_FAILED)
        val capture = capture()

        assertEquals(false, capture.holdFocusForExternalAssistant())
        capture.releaseExternalAssistantFocus()
        assertNull(shadowOf(audioManager).lastAbandonedAudioFocusRequest)
    }
}
