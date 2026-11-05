package com.bydmate.app.voice

/**
 * Audio kept from before the VAD's speech onset. [sampleCount] is how far back the history
 * reaches from the frame the speech was detected in; [maxPrepend] caps what is prepended before
 * the native segment start. Silero only reports speech after its minimum speech duration plus two
 * windows (and at the end of a whole capture frame), so the native start already lies ~0.3-0.4 s
 * before the detection frame: a history of just [maxPrepend] would add almost nothing before it.
 */
internal class SpeechPreRoll(sampleCount: Int, private val maxPrepend: Int = sampleCount) {
    private val ring = FloatArray(sampleCount)
    private var position = 0L
    private var retained = 0
    private var consumedThrough = 0L
    private var prefix = FloatArray(0)
    private var prefixStart = 0L

    fun append(frame: FloatArray) {
        if (ring.isEmpty()) return
        val offset = maxOf(0, frame.size - ring.size)
        val start = ((position + offset) % ring.size).toInt()
        val first = minOf(frame.size - offset, ring.size - start)
        frame.copyInto(ring, start, offset, offset + first)
        frame.copyInto(ring, 0, offset + first, frame.size)
        position += frame.size
        retained = minOf(ring.size, retained + frame.size)
    }

    fun speechStart() {
        val count = minOf(retained, (position - consumedThrough).coerceIn(0L, ring.size.toLong()).toInt())
        prefixStart = position - count
        prefix = FloatArray(count) { ring[((prefixStart + it) % ring.size).toInt()] }
    }

    fun finish(segmentStart: Long, segment: FloatArray): FloatArray {
        // Native start includes VAD onset padding; prepend only samples before it, the newest
        // [maxPrepend] of them.
        val before = (segmentStart - prefixStart).coerceIn(0L, prefix.size.toLong()).toInt()
        val count = minOf(before, maxPrepend.coerceAtLeast(0))
        val result = if (count == 0) segment else FloatArray(count + segment.size).also {
            prefix.copyInto(it, startIndex = before - count, endIndex = before)
            segment.copyInto(it, count)
        }
        consumedThrough = maxOf(consumedThrough, segmentStart + segment.size)
        prefix = FloatArray(0)
        return result
    }
}
