package com.bydmate.app.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class MicLivenessTest {
    private val zeros = ShortArray(1600)
    private val noise = ShortArray(1600) { if (it == 7) 3 else 0 }

    @Test fun `first frame with any signal is live once`() {
        val mic = MicLiveness()
        assertEquals(MicLiveness.Event.LIVE, mic.onFrame(noise, 100))
        assertNull(mic.onFrame(noise, 100))
        assertNull(mic.onFrame(zeros, 100))
    }

    @Test fun `only digital zeros report silent once after the threshold`() {
        val mic = MicLiveness(silentAfterMs = 300)
        assertNull(mic.onFrame(zeros, 100))
        assertNull(mic.onFrame(zeros, 100))
        assertEquals(MicLiveness.Event.SILENT, mic.onFrame(zeros, 100))
        assertNull(mic.onFrame(zeros, 100))
        assertEquals(MicLiveness.Event.LIVE, mic.onFrame(noise, 100))
    }

    @Test fun `a mic that goes quiet after live reports silent, then live again`() {
        val mic = MicLiveness(silentAfterMs = 200)
        assertEquals(MicLiveness.Event.LIVE, mic.onFrame(noise, 100))
        assertNull(mic.onFrame(zeros, 100))
        assertEquals(MicLiveness.Event.SILENT, mic.onFrame(zeros, 100))
        assertNull(mic.onFrame(zeros, 100))
        assertEquals(MicLiveness.Event.LIVE, mic.onFrame(noise, 100))
        assertNull(mic.onFrame(zeros, 100))
        assertNull(mic.onFrame(noise, 100))
    }
}
