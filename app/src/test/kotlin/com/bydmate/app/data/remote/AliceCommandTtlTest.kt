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

    @Test fun `created_at without server time is read against the Date header, never the unit clock`() {
        wall -= 845_000L // the head unit clock runs 14 minutes behind
        val serverNow = 1_700_000_000_000L
        val batch = ttl.onResponse(serverTimeMs = null, dateMs = serverNow)
        assertFalse(batch.isExpired(cmd(createdAtMs = serverNow - 10_000L)))
        assertTrue(batch.isExpired(cmd(createdAtMs = serverNow - 31_000L)))
        // Whole seconds: the age is taken at the upper end of the Date second.
        assertEquals(10_999L, batch.ageMs(cmd(createdAtMs = serverNow - 10_000L)))
        assertEquals(AliceCommandTtl.AgeSource.DATE_HEADER, batch.age(cmd(createdAtMs = serverNow - 10_000L)).source)
        // A command from the future (clock skew) is not negative-aged into eternity.
        assertEquals(0L, batch.ageMs(cmd(createdAtMs = serverNow + 5_000L)))
        assertEquals(-845_000L, batch.clockSkewMs)
    }

    @Test fun `created_at with no server clock at all is not read against the unit clock`() {
        val batch = ttl.onResponse(serverTimeMs = null)
        assertEquals(AliceCommandTtl.AgeSource.UNKNOWN, batch.age(cmd(createdAtMs = wall - 1_000L)).source)
        assertTrue(batch.isExpired(cmd(createdAtMs = wall - 1_000L)))
        assertNull(batch.clockSkewMs)
    }

    @Test fun `server age and server_time outrank the Date header`() {
        val serverNow = 1_700_000_000_000L
        val batch = ttl.onResponse(serverTimeMs = serverNow, dateMs = serverNow - 60_000L)
        assertEquals(AliceCommandTtl.Age(4_000L, AliceCommandTtl.AgeSource.AGE_MS), batch.age(cmd(ageMs = 4_000L)))
        assertEquals(AliceCommandTtl.Age(5_000L, AliceCommandTtl.AgeSource.SERVER_TIME),
            batch.age(cmd(createdAtMs = serverNow - 5_000L)))
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

    // --- the fork's deployed worker 5.10: no timestamp in the poll answer ---

    @Test fun `an unstamped command of the first answer is aged from the worker record`() {
        val serverNow = 1_700_000_000_000L
        val batch = ttl.onResponse(serverTimeMs = null, dateMs = serverNow)
        val fresh = AliceBridgeCommand(id = "fresh", action = "light.interior_on")
        val stale = AliceBridgeCommand(id = "stale", action = "light.interior_on")
        val unlisted = AliceBridgeCommand(id = "gone", action = "light.interior_on")
        assertTrue(batch.needsLookup(fresh))
        mono += 300L // the lookup round trip
        batch.lookup = ttl.lookupOf(mapOf("fresh" to serverNow - 3_000L, "stale" to serverNow - 845_000L), serverNow)
        mono += 200L
        assertEquals(AliceCommandTtl.Age(4_199L, AliceCommandTtl.AgeSource.LOOKUP), batch.age(fresh))
        assertFalse(batch.isExpired(fresh))
        assertTrue(batch.isExpired(stale))
        assertEquals(AliceCommandTtl.AgeSource.UNKNOWN, batch.age(unlisted).source)
        assertTrue(batch.isExpired(unlisted))
    }

    @Test fun `a poll bound inside the limit needs no lookup`() {
        ttl.onResponse(serverTimeMs = null)
        mono += 2_500L
        val batch = ttl.onResponse(serverTimeMs = null, dateMs = wall)
        assertFalse(batch.needsLookup(cmd()))
        assertEquals(AliceCommandTtl.AgeSource.POLL_BOUND, batch.age(cmd()).source)
    }

    @Test fun `a poll bound past the limit is replaced by the worker record`() {
        ttl.onResponse(serverTimeMs = null)
        mono += 45_000L // a network outage
        val serverNow = 1_700_000_000_000L
        val batch = ttl.onResponse(serverTimeMs = null, dateMs = serverNow)
        assertTrue(batch.needsLookup(cmd()))
        assertTrue(batch.isExpired(cmd()))
        batch.lookup = ttl.lookupOf(mapOf("c" to serverNow - 2_000L), serverNow)
        assertFalse(batch.isExpired(cmd()))
    }
}
