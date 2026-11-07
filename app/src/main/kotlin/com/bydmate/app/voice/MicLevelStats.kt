package com.bydmate.app.voice

import kotlin.math.roundToInt

/**
 * How loud the session's microphone was, for the session-stop trace. Field 1.1.7/1.1.8: sessions
 * with a live mic that heard nothing for 30 s; the level tells whether the voice reached the mic
 * at all (a low peak) or the VAD did not take it (a speech-level peak). Written by the capture
 * thread, read once when the session ends.
 */
internal class MicLevelStats {
    @Volatile private var frames = 0
    @Volatile private var sumRms = 0.0
    @Volatile private var peakRms = 0.0

    fun onFrame(samples: ShortArray) {
        val rms = frameRms(samples)
        frames++
        sumRms += rms
        if (rms > peakRms) peakRms = rms
    }

    data class Level(val frames: Int, val avg: Int, val peak: Int)

    /** Frame count, mean and peak frame RMS on the int16 scale. */
    fun snapshot(): Level =
        Level(frames, if (frames == 0) 0 else (sumRms / frames).roundToInt(), peakRms.roundToInt())
}
