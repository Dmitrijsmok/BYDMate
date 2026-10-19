package com.bydmate.app.voice

import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class GigaAmPreRollTest {
    private class Vad : VadHandle {
        var frame = 0
        var pending = false
        var closed = false
        override fun acceptWaveform(samples: FloatArray) { frame++; pending = frame % 3 == 0 }
        override fun isSpeechDetected() = frame % 3 == 2
        override fun empty() = !pending
        private fun segmentStart() = (frame - 3) * 1600L + 2400
        override fun front() = FloatArray(2400) { (segmentStart() + it).toFloat() / 32768f }
        override fun frontWithStart() = segmentStart() to front()
        override fun pop() { pending = false }
        override fun close() { closed = true }
    }

    @Test fun `engine restores quiet PCM trims native overlap and changes configuration between phrases`() = runTest {
        var ms = 200
        val decoded = mutableListOf<FloatArray>()
        val vad = Vad()
        val recognizer = object : RecognizerHandle {
            override fun decode(samples: FloatArray): String { decoded.add(samples); return "exact" }
            override fun close() = Unit
        }
        val manager = mockk<GigaAmModelManager> { every { isReady() } returns true }
        val engine = GigaAmAsrEngine(manager, { recognizer }, { vad }, preRollMs = { ms })
        engine.transcribe(flow {
            repeat(6) { frame ->
                if (frame == 3) ms = 0
                emit(ShortArray(1600) { (frame * 1600 + it).toShort() })
            }
        }).toList()
        assertArrayEquals(FloatArray(4800) { it / 32768f }, decoded[0], 0f)
        assertArrayEquals(FloatArray(2400) { (7200 + it) / 32768f }, decoded[1], 0f)
        assertTrue(vad.closed)
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test fun `cancelled session closes VAD and the restarted microphone has no previous prefix`() = runTest {
        val vads = mutableListOf<Vad>()
        val decoded = mutableListOf<FloatArray>()
        val recognizer = object : RecognizerHandle {
            override fun decode(samples: FloatArray): String { decoded.add(samples); return "" }
            override fun close() = Unit
        }
        val manager = mockk<GigaAmModelManager> { every { isReady() } returns true }
        val engine = GigaAmAsrEngine(manager, { recognizer }, { Vad().also { vads.add(it) } }, preRollMs = { 1000 })
        val job = launch {
            engine.transcribe(flow { repeat(2) { emit(ShortArray(1600) { 123 }) }; awaitCancellation() }).collect {}
        }
        runCurrent()
        job.cancelAndJoin()
        engine.transcribe(flow { repeat(3) { emit(ShortArray(1600)) } }).toList()
        assertEquals(2, vads.size)
        assertTrue(vads.all { it.closed })
        assertTrue(decoded.single().take(2400).all { it == 0f })
    }
}
