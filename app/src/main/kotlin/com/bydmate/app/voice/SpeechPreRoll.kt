package com.bydmate.app.voice

internal val speechPreRollDurations = listOf(0, 100, 200, 300, 400, 600, 800, 1000)

internal class SpeechPreRoll(private val setting: () -> Int) {
    private val ring = FloatArray(16000)
    private var position = 0L
    private var retained = 0
    private var consumedThrough = 0L
    private var prefix = FloatArray(0)
    private var prefixStart = 0L
    var selectedMs = 0
        private set

    fun speechStart() {
        selectedMs = setting().takeIf { it in speechPreRollDurations } ?: 0
        val count = minOf(retained, selectedMs * 16, (position - consumedThrough).coerceIn(0L, ring.size.toLong()).toInt())
        prefixStart = position - count
        prefix = FloatArray(count) { ring[((prefixStart + it) % ring.size).toInt()] }
    }

    fun append(frame: FloatArray) {
        val start = maxOf(0, frame.size - ring.size)
        for (i in start until frame.size) ring[((position + i) % ring.size).toInt()] = frame[i]
        position += frame.size
        retained = minOf(ring.size, retained + frame.size)
    }

    fun finish(segmentStart: Long, segment: FloatArray): FloatArray {
        // Native VAD start is an absolute sample index, including its own onset padding.
        val count = (segmentStart - prefixStart).coerceIn(0L, prefix.size.toLong()).toInt()
        val result = if (count == 0) segment else FloatArray(count + segment.size).also {
            prefix.copyInto(it, endIndex = count)
            segment.copyInto(it, count)
        }
        consumedThrough = maxOf(consumedThrough, segmentStart + segment.size)
        prefix = FloatArray(0)
        return result
    }

    internal fun retainedSamples() = retained + prefix.size
}
