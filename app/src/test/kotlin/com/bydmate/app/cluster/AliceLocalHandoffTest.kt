package com.bydmate.app.cluster

import org.junit.Assert.assertEquals
import org.junit.Test

class AliceLocalHandoffTest {
    @Test fun `unknown or Yandex foreground never releases local`() {
        val gate = AliceLocalHandoff(1_000)
        assertEquals(HandoffResult.WAIT, gate.observe(1_100, false))
        assertEquals(HandoffResult.WAIT, gate.observe(2_500, false))
        assertEquals(HandoffResult.TIMEOUT, gate.observe(5_001, false))
    }

    @Test fun `release requires a continuously confirmed exit grace period`() {
        val gate = AliceLocalHandoff(1_000)
        assertEquals(HandoffResult.WAIT, gate.observe(1_100, true))
        assertEquals(HandoffResult.WAIT, gate.observe(2_299, true))
        assertEquals(HandoffResult.READY, gate.observe(2_300, true))
    }

    @Test fun `Yandex reappearing resets exit confirmation`() {
        val gate = AliceLocalHandoff(1_000)
        gate.observe(1_100, true)
        gate.observe(2_000, false)
        assertEquals(HandoffResult.WAIT, gate.observe(2_100, true))
        assertEquals(HandoffResult.WAIT, gate.observe(3_000, true))
    }
}
