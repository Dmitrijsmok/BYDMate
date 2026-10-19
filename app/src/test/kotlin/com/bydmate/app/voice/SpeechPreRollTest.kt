package com.bydmate.app.voice

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class SpeechPreRollTest {
    @Test fun `every duration retains exactly the selected context without overlap`() {
        for (ms in speechPreRollDurations) {
            val roll = SpeechPreRoll { ms }
            val original = FloatArray(20000) { it.toFloat() }
            roll.append(original)
            roll.speechStart()
            val segment = floatArrayOf(20000f, 20001f)
            val result = roll.finish(20000, segment)
            assertEquals(ms * 16 + segment.size, result.size)
            assertArrayEquals(original.takeLast(ms * 16).toFloatArray() + segment, result, 0f)
            if (ms == 0) assertSame(segment, result)
        }
    }

    @Test fun `quiet onset is preserved and native segment padding is not duplicated`() {
        val roll = SpeechPreRoll { 100 }
        val quiet = FloatArray(1600) { it / 32768f }
        roll.append(quiet)
        roll.speechStart()
        val segment = quiet.copyOfRange(800, 1600) + floatArrayOf(1f)
        assertArrayEquals(quiet + floatArrayOf(1f), roll.finish(800, segment), 0f)
    }

    @Test fun `native segment beginning before prefix is returned unchanged`() {
        val roll = SpeechPreRoll { 100 }
        roll.append(FloatArray(3200))
        roll.speechStart()
        val segment = FloatArray(4000)
        assertSame(segment, roll.finish(0, segment))
    }

    @Test fun `configuration changes only take effect at the next speech onset`() {
        var setting = 100
        val roll = SpeechPreRoll { setting }
        roll.append(FloatArray(3200))
        roll.speechStart()
        setting = 200
        assertEquals(1601, roll.finish(3200, floatArrayOf(1f)).size)
        roll.append(FloatArray(6400))
        roll.speechStart()
        assertEquals(3201, roll.finish(9600, floatArrayOf(2f)).size)
        setting = 0
        roll.append(FloatArray(6400))
        roll.speechStart()
        val segment = floatArrayOf(3f)
        assertSame(segment, roll.finish(16000, segment))
    }

    @Test fun `consecutive phrases never prepend samples consumed by a prior utterance`() {
        val roll = SpeechPreRoll { 1000 }
        roll.append(FloatArray(1600) { 1f })
        roll.speechStart()
        roll.append(FloatArray(1600) { 1f })
        roll.finish(0, FloatArray(3200) { 1f })
        repeat(4) { index ->
            roll.append(FloatArray(1600) { 2f })
            roll.speechStart()
            val start = 4800L + index * 1601L
            val result = roll.finish(start, floatArrayOf(2f))
            assertTrue(result.all { it == 2f })
            roll.append(floatArrayOf(2f))
        }
    }

    @Test fun `rolling and frozen buffers stay bounded even for huge frames and long phrases`() {
        val roll = SpeechPreRoll { 1000 }
        repeat(100) { roll.append(FloatArray(20000)) }
        roll.speechStart()
        repeat(100) { roll.append(FloatArray(20000)) }
        assertTrue(roll.retainedSamples() <= 32000)
    }

    @Test fun `a new collection has no prefix from the old session`() {
        val old = SpeechPreRoll { 1000 }
        old.append(FloatArray(16000) { 1f })
        old.speechStart()
        val fresh = SpeechPreRoll { 1000 }
        fresh.speechStart()
        val segment = floatArrayOf(2f)
        assertSame(segment, fresh.finish(0, segment))
    }

    @Test fun `unsupported persisted values safely select the control`() {
        val roll = SpeechPreRoll { 101 }
        roll.append(FloatArray(1600))
        roll.speechStart()
        assertEquals(0, roll.selectedMs)
    }
}
