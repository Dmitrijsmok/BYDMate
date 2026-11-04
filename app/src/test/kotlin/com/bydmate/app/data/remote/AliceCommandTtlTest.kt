package com.bydmate.app.data.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AliceCommandTtlTest {
    private var mono = 1_000_000L
    private var wall = 1_700_000_000_000L
    private val ttl = AliceCommandTtl(ttlMs = 30_000L, monotonicMs = { mono }, wallMs = { wall })

    private fun cmd(ageMs: Long? = null, createdAtMs: Long? = null) =
        AliceBridgeCommand(id = "c", action = "climate.on", ageMs = ageMs, createdAtMs = createdAtMs)

    @Test fun `server age decides when the worker reports it`() {
        val batch = ttl.onResponse(serverTimeMs = null)
        assertFalse(batch.isExpired(cmd(ageMs = 1_000L)))
        assertFalse(batch.isExpired(cmd(ageMs = 30_000L)))
        assertTrue(batch.isExpired(cmd(ageMs = 30_001L)))
    }

    @Test fun `created_at is read against the server clock, not the head unit clock`() {
        wall += 3_600_000L // the head unit clock runs an hour ahead
        val serverNow = 1_700_000_000_000L
        val batch = ttl.onResponse(serverTimeMs = serverNow)
        assertFalse(batch.isExpired(cmd(createdAtMs = serverNow - 5_000L)))
        assertTrue(batch.isExpired(cmd(createdAtMs = serverNow - 31_000L)))
    }

    @Test fun `created_at without server time falls back to the local clock`() {
        val batch = ttl.onResponse(serverTimeMs = null)
        assertFalse(batch.isExpired(cmd(createdAtMs = wall - 10_000L)))
        assertTrue(batch.isExpired(cmd(createdAtMs = wall - 60_000L)))
        // A command from the future (clock skew) is not negative-aged into eternity.
        assertEquals(0L, batch.ageMs(cmd(createdAtMs = wall + 5_000L)))
    }

    @Test fun `unstamped command on the first answer after start is of unknown age and expires`() {
        val batch = ttl.onResponse(serverTimeMs = null)
        assertNull(batch.ageMs(cmd()))
        assertTrue(batch.isExpired(cmd()))
    }

    @Test fun `unstamped command is at most as old as the previous answer`() {
        ttl.onResponse(serverTimeMs = null)
        mono += 2_500L
        val fresh = ttl.onResponse(serverTimeMs = null)
        assertEquals(2_500L, fresh.ageMs(cmd()))
        assertFalse(fresh.isExpired(cmd()))

        mono += 45_000L // no answer for 45 s: network outage
        val late = ttl.onResponse(serverTimeMs = null)
        assertTrue(late.isExpired(cmd()))
    }

    @Test fun `time spent on earlier commands of the batch counts`() {
        val batch = ttl.onResponse(serverTimeMs = null)
        val command = cmd(ageMs = 20_000L)
        assertFalse(batch.isExpired(command))
        mono += 12_000L // a window move ran before this command
        assertTrue(batch.isExpired(command))
    }

    @Test fun `reset forgets the previous answer`() {
        ttl.onResponse(serverTimeMs = null)
        mono += 1_000L
        ttl.reset()
        assertTrue(ttl.onResponse(serverTimeMs = null).isExpired(cmd()))
    }
}
