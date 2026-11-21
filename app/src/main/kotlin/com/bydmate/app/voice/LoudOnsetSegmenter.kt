package com.bydmate.app.voice

/**
 * The start of a phrase in road noise, for the case Silero VAD never hears it (field log
 * 2026-11-21, DiLink 3.0 at 100 km/h): the cabin floor was 340..375 RMS, a phrase said at a
 * normal voice peaked at 1.6..1.9 times that, the VAD reported no speech for 30 s and the
 * session closed without a command; said loudly (2.4 times the floor) it worked.
 *
 * Only while the cabin is noisy ([NoiseEndpointer.noisy]) and the VAD is silent: a run of frames
 * clearly louder than the floor starts a segment, with [preRollMs] of audio before it so the first
 * syllable is kept; frames back at the floor for [quietTailMs] end it. The segment goes to the
 * recognizer when it held [minLoudMs] of loud frames (a short knock or a pothole does not); a
 * segment longer than [maxMs] is cut there. The VAD hearing speech drops the segment: its own
 * segment carries the phrase. A quiet cabin never gets here.
 *
 * Pure: frames, loudness and the floor in, a segment to decode out.
 */
@Suppress("LongParameterList") // the thresholds, injectable for the tests
internal class LoudOnsetSegmenter(
    /** A frame this many times the floor is the driver's voice over the noise (as NoiseEndpointer). */
    private val loudRatio: Double = 1.35,
    /** A frame below this many times the floor is the noise alone (as NoiseEndpointer). */
    private val quietRatio: Double = 1.15,
    private val minLoudMs: Long = 400,
    /** The VAD's own minimum silence, so a pause inside a phrase does not split it. */
    private val quietTailMs: Long = 800,
    private val preRollMs: Long = 400,
    private val maxMs: Long = 10_000,
) {
    private val preRoll = ArrayDeque<Pair<FloatArray, Long>>()
    private var preRollHeldMs = 0L
    private val collected = ArrayList<FloatArray>()
    private var collectedMs = 0L
    private var loudMs = 0L
    private var quietMs = 0L

    /** True while a segment is being collected (the driver is talking, as far as loudness says). */
    var active: Boolean = false
        private set

    /** Loud speech in the segment that was handed out last, for the log. */
    var lastLoudMs: Long = 0
        private set

    /** The segment to decode once it ended, else null. */
    @Suppress("ReturnCount")
    fun onFrame(frame: FloatArray, rms: Double, frameMs: Long, floor: Double, noisy: Boolean, vadInSpeech: Boolean): FloatArray? {
        if (frameMs <= 0) return null
        if (vadInSpeech || !noisy || floor <= 0.0) {
            reset()
            keep(frame, frameMs)
            return null
        }
        val loud = rms >= floor * loudRatio
        if (!active) {
            if (!loud) {
                keep(frame, frameMs)
                return null
            }
            active = true
            preRoll.forEach { collected.add(it.first) }
            collectedMs = preRollHeldMs
            preRoll.clear()
            preRollHeldMs = 0L
            loudMs = 0L
            quietMs = 0L
        }
        collected.add(frame)
        collectedMs += frameMs
        if (loud) loudMs += frameMs
        quietMs = if (rms < floor * quietRatio) quietMs + frameMs else 0L
        if (quietMs < quietTailMs && collectedMs < maxMs) return null
        val segment = if (loudMs >= minLoudMs) concat(collected) else null
        if (segment != null) lastLoudMs = loudMs
        reset()
        return segment
    }

    /** The last [preRollMs] of audio before a segment starts, so its first syllable is kept. */
    private fun keep(frame: FloatArray, frameMs: Long) {
        preRoll.addLast(frame to frameMs)
        preRollHeldMs += frameMs
        while (preRoll.size > 1 && preRollHeldMs - preRoll.first().second >= preRollMs) {
            preRollHeldMs -= preRoll.removeFirst().second
        }
    }

    private fun reset() {
        active = false
        collected.clear()
        collectedMs = 0L
        loudMs = 0L
        quietMs = 0L
    }

    private fun concat(frames: List<FloatArray>): FloatArray {
        val out = FloatArray(frames.sumOf { it.size })
        var at = 0
        for (f in frames) {
            f.copyInto(out, at)
            at += f.size
        }
        return out
    }
}
