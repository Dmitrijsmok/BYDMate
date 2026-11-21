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
     * (DiLink 3.0 / ATTO 3): the navigation stream (14) the assistant's voice already speaks on
     * (SherpaTtsEngine.BYD_STREAM_NAVI), at full ToneGenerator volume, so the start / stop / error
     * cues follow the same volume as the voice. On the alarm stream they sounded at a level of
     * their own next to the ducked music (2026-11-21); stream 17 constructs there but plays
     * nothing audible. Everywhere else: BYD "Voice" stream (17), same route as agent TTS --
     * beeps stay audible while a session ducks STREAM_MUSIC to near-zero (on the music stream
     * every earcon was swallowed by the session's own duck, field report APK 340).
     */
    internal fun primaryRoute(): Pair<Int, Int> =
        if (legacyHeadUnit) LEGACY_STREAM to LEGACY_VOLUME else SherpaTtsEngine.BYD_STREAM_BTTS to volume

    /** The streams tried in order when the firmware rejects one: Android 10 keeps the alarm
     *  stream it beeped on before, then the music stream as everywhere. */
    internal fun fallbackStreams(): List<Int> =
        if (legacyHeadUnit) listOf(AudioManager.STREAM_ALARM, AudioManager.STREAM_MUSIC) else listOf(AudioManager.STREAM_MUSIC)

    private fun toneGenerator(): ToneGenerator {
        val (stream, streamVolume) = primaryRoute()
        var made = runCatching { ToneGenerator(stream, streamVolume) }
        for (fallback in fallbackStreams()) {
            if (made.isSuccess) break
            made = runCatching { ToneGenerator(fallback, streamVolume) }
        }
        return made.getOrThrow()
    }

    internal companion object {
        const val LEGACY_STREAM = SherpaTtsEngine.BYD_STREAM_NAVI
        const val LEGACY_VOLUME = ToneGenerator.MAX_VOLUME
    }
}
