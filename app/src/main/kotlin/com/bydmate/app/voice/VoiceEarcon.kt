package com.bydmate.app.voice

import android.media.AudioManager
import android.media.ToneGenerator
import android.os.SystemClock

/** Short non-spoken confirmation/failure beeps. TTS responses are Spec 2. */
class VoiceEarcon(private val volume: Int = 70) {
    /** Normal session-start cue. A short debounce also suppresses the second cue when
     * DiLink3 already played the immediate steering-button acknowledgement before VoiceController
     * entered the capture session. */
    fun ok() {
        if (!claimStartCue()) return
        beep(ToneGenerator.TONE_PROP_ACK, 150)
    }

    /**
     * DiLink3 steering-button acknowledgement. Play it immediately on STREAM_MUSIC, before the
     * capture path ducks music or spends time constructing GigaAM. This restores the instant
     * "button accepted" feedback even when the voice model/API later fails to start.
     * The shared debounce makes the following [ok] call from VoiceController a no-op, so the user
     * hears one beep, not two.
     */
    fun steeringStart() {
        if (!claimStartCue()) return
        beepOn(ToneGenerator(AudioManager.STREAM_MUSIC, volume), ToneGenerator.TONE_PROP_ACK, 150)
    }

    fun fail() = beep(ToneGenerator.TONE_PROP_NACK, 250)
    /** Session-stop cue: distinct from ok() so switching the agent on and off are
     *  tellable apart by ear. */
    fun off() = beep(ToneGenerator.TONE_PROP_BEEP, 150)

    private fun claimStartCue(): Boolean = synchronized(VoiceEarcon::class.java) {
        val now = SystemClock.elapsedRealtime()
        if (now - lastStartCueAtMs < START_CUE_DEBOUNCE_MS) {
            false
        } else {
            lastStartCueAtMs = now
            true
        }
    }

    private fun beep(tone: Int, ms: Int) {
        runCatching { beepOn(toneGenerator(), tone, ms) }
    }

    private fun beepOn(tg: ToneGenerator, tone: Int, ms: Int) {
        runCatching {
            tg.startTone(tone, ms)
            Thread { Thread.sleep((ms + 50).toLong()); tg.release() }.start()
        }.onFailure {
            runCatching { tg.release() }
        }
    }

    // BYD "Voice" stream (17), same route as agent TTS: beeps stay audible while a session
    // ducks STREAM_MUSIC to near-zero -- on the music stream every earcon was swallowed by
    // the session's own duck (field report APK 340). Fall back to the music stream if the
    // firmware rejects the custom stream type.
    private fun toneGenerator(): ToneGenerator =
        runCatching { ToneGenerator(SherpaTtsEngine.BYD_STREAM_BTTS, volume) }
            .getOrElse { ToneGenerator(AudioManager.STREAM_MUSIC, volume) }

    private companion object {
        const val START_CUE_DEBOUNCE_MS = 400L
        @Volatile var lastStartCueAtMs = 0L
    }
}
