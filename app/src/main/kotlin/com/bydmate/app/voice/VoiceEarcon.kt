package com.bydmate.app.voice

import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build

/** Short non-spoken confirmation/failure beeps. TTS responses are Spec 2. */
class VoiceEarcon(private val volume: Int = 100) {
    fun ok() = beep(ToneGenerator.TONE_PROP_ACK, 150)
    fun fail() = beep(ToneGenerator.TONE_PROP_NACK, 250)
    /** Session-stop cue: distinct from ok() so switching the agent on and off are
     *  tellable apart by ear. */
    fun off() = beep(ToneGenerator.TONE_PROP_BEEP, 150)
    private fun beep(tone: Int, ms: Int) {
        runCatching {
            val tg = toneGenerator()
            tg.startTone(tone, ms)
            Thread { Thread.sleep((ms + 50).toLong()); tg.release() }.start()
        }
    }

    // Field-proven DiLink 3 route from 64027. Stream 17 can be constructible but effectively
    // absent/inaudible on ATTO 3, so use ALARM at full ToneGenerator volume on that firmware.
    private fun toneGenerator(): ToneGenerator {
        if (!SherpaTtsEngine.shouldUseBydVoiceStream(Build.FINGERPRINT.orEmpty())) {
            return ToneGenerator(AudioManager.STREAM_ALARM, volume)
        }
        return runCatching { ToneGenerator(SherpaTtsEngine.BYD_STREAM_BTTS, volume) }
            .getOrElse {
                val fallbackStream =
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) AudioManager.STREAM_ACCESSIBILITY
                    else AudioManager.STREAM_MUSIC
                ToneGenerator(fallbackStream, volume)
            }
    }
}
