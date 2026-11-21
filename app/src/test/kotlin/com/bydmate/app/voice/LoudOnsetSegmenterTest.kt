package com.bydmate.app.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Numbers from the 2026-11-21 log at 100 km/h: floor ~370 RMS, a normal voice 1.6..1.9 times it. */
class LoudOnsetSegmenterTest {

    private val floor = 370.0
    private val frameMs = 100L
    private val noise = 380.0
    private val voice = 650.0

    /** 100 ms frames whose first sample tells them apart in the segment. */
    private var n = 0
    private fun frame(): FloatArray = FloatArray(1600).also { it[0] = (++n).toFloat() }

    private fun LoudOnsetSegmenter.feed(
        rms: Double, frames: Int, noisy: Boolean = true, vad: Boolean = false,
    ): FloatArray? {
        var out: FloatArray? = null
        repeat(frames) { onFrame(frame(), rms, frameMs, floor, noisy, vad)?.let { out = it } }
        return out
    }

    @Test fun `a phrase the VAD missed in a noisy cabin is handed out once the noise is back`() {
        val s = LoudOnsetSegmenter()
        assertNull(s.feed(noise, 10))
        assertNull(s.feed(voice, 12))
        assertTrue(s.active)

        val segment = s.feed(noise, 8)

        assertNotNull(segment)
        assertFalse(s.active)
        assertEquals(1200L, s.lastLoudMs)
        // 400 ms before the onset + 1.2 s of voice + the 800 ms tail.
        assertEquals((4 + 12 + 8) * 1600, segment!!.size)
        assertEquals(7f, segment[0]) // frames 7..10 of the noise before the voice
    }

    @Test fun `a short knock is not a phrase`() {
        val s = LoudOnsetSegmenter()
        s.feed(noise, 10)
        s.feed(voice, 2)

        assertNull(s.feed(noise, 8))
        assertFalse(s.active)
    }

    @Test fun `a quiet cabin never collects`() {
        val s = LoudOnsetSegmenter()

        assertNull(s.feed(voice, 20, noisy = false))
        assertFalse(s.active)
    }

    @Test fun `the VAD hearing speech drops the loudness segment`() {
        val s = LoudOnsetSegmenter()
        s.feed(noise, 10)
        s.feed(voice, 6)
        assertTrue(s.active)

        s.feed(voice, 1, vad = true)
        assertFalse(s.active)
        assertNull(s.feed(noise, 8))
    }

    @Test fun `a pause inside the phrase does not split it`() {
        val s = LoudOnsetSegmenter()
        s.feed(noise, 10)
        s.feed(voice, 5)
        assertNull(s.feed(noise, 5)) // 500 ms pause, shorter than the 800 ms tail
        s.feed(voice, 5)

        val segment = s.feed(noise, 8)

        assertNotNull(segment)
        assertEquals(1000L, s.lastLoudMs)
    }

    @Test fun `talking over the limit is cut there`() {
        val s = LoudOnsetSegmenter(maxMs = 3_000)
        s.feed(noise, 10)

        val segment = s.feed(voice, 26) // 400 ms before + 2.6 s = the 3 s limit

        assertNotNull(segment)
        assertFalse(s.active)
    }

    @Test fun `no floor yet means no segment`() {
        val s = LoudOnsetSegmenter()
        var out: FloatArray? = null
        repeat(20) { s.onFrame(frame(), voice, frameMs, 0.0, true, false)?.let { out = it } }

        assertNull(out)
        assertFalse(s.active)
    }
}
