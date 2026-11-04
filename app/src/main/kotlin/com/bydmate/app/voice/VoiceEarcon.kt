package com.bydmate.app.voice

import android.media.AudioManager
import android.media.ToneGenerator
import com.bydmate.app.platform.LegacyHeadUnit

/** Short non-spoken confirmation/failure beeps. TTS responses are Spec 2. */
class VoiceEarcon(
    private val volume: Int = 70,
    private val legacyHeadUnit: Boolean = LegacyHeadUnit.isAndroid10,
) {
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

    /**
     * Stream and volume of the ToneGenerator a beep asks for first. Android 10 head units
     * (DiLink 3.0 / ATTO 3): stream 17 constructs but plays nothing audible on-car, so the
     * three short cues take the independent ALARM route at full ToneGenerator volume; spoken
     * TTS keeps its own route (SherpaTtsEngine). Everywhere else: BYD "Voice" stream (17), same
     * route as agent TTS -- beeps stay audible while a session ducks STREAM_MUSIC to near-zero
     * (on the music stream every earcon was swallowed by the session's own duck, field report
     * APK 340).
     */
    internal fun primaryRoute(): Pair<Int, Int> =
        if (legacyHeadUnit) LEGACY_STREAM to LEGACY_VOLUME else SherpaTtsEngine.BYD_STREAM_BTTS to volume

    // Fall back to the music stream if the firmware rejects the stream type.
    private fun toneGenerator(): ToneGenerator {
        val (stream, streamVolume) = primaryRoute()
        return runCatching { ToneGenerator(stream, streamVolume) }
            .getOrElse { ToneGenerator(AudioManager.STREAM_MUSIC, streamVolume) }
    }

    internal companion object {
        const val LEGACY_STREAM = AudioManager.STREAM_ALARM
        const val LEGACY_VOLUME = ToneGenerator.MAX_VOLUME
    }
}
