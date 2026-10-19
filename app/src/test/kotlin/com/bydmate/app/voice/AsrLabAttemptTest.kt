package com.bydmate.app.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AsrLabAttemptTest {
    @Test fun `monotonic stage timing ignores wall clock and records missing stages`() {
        var now = 10L
        val attempt = AsrLabAttempt(400, { now++ * 1_000_000 }, 123)
        attempt.opening()
        attempt.ready()
        attempt.firstPcm()
        attempt.firstPcm()
        attempt.speechStart(200)
        attempt.decodeStart(100, 200, 300)
        attempt.decoded("Открой, \"навигатор\"\nсейчас")
        val result = attempt.result()
        assertEquals(123L, result.timestampMs)
        assertEquals(200, result.preRollMs)
        assertEquals(listOf(10L, 11L, 12L, 13L, 14L, 15L, 16L).map { it * 1_000_000 }, result.stagesNs)
        val csv = labCsv(listOf(result), "4.0.1-asr-lab.1", 100002, "baseline")
        assertTrue(csv.contains("\"Открой, \"\"навигатор\"\"\nсейчас\""))
        assertTrue(csv.contains("\"4.0.1-asr-lab.1\",\"100002\",\"baseline\",\"16000\",\"200\""))
        assertTrue(labCsv(listOf(AsrLabAttempt(0).result("cancelled")), "v", 1, "b").contains("cancelled"))
    }
}
