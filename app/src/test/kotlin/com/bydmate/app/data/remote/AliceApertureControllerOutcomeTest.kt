package com.bydmate.app.data.remote

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AliceApertureControllerOutcomeTest {

    @Test
    fun `reached target plus accepted stop is success even when late readback drifts`() {
        assertTrue(
            windowMoveSucceeded(
                reached = 10,
                stopAccepted = true,
                finalPosition = 18,
                target = 10,
            )
        )
    }

    @Test
    fun `late final readback can confirm success when threshold sample was missed`() {
        assertTrue(
            windowMoveSucceeded(
                reached = null,
                stopAccepted = true,
                finalPosition = 12,
                target = 10,
            )
        )
    }

    @Test
    fun `never reached target remains a miss`() {
        assertFalse(
            windowMoveSucceeded(
                reached = null,
                stopAccepted = true,
                finalPosition = 35,
                target = 10,
            )
        )
    }

    @Test
    fun `failed stop is never reported as success`() {
        assertFalse(
            windowMoveSucceeded(
                reached = 10,
                stopAccepted = false,
                finalPosition = 10,
                target = 10,
            )
        )
    }
}
