package com.bydmate.app.data.nativestack

import com.bydmate.app.data.autoservice.AutoserviceClient
import com.bydmate.app.data.repository.SettingsRepository
import com.bydmate.app.data.vehicle.HelperClient
import io.mockk.Runs
import io.mockk.coEvery
import io.mockk.every
import io.mockk.just
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * insideTemp reads the DiLink 5.0 AC_TEMP_INSIDE fid first; the older BYD SDK address
 * (insideTempAlt, 1320181776) stands in only when the primary answers link-error (65535) or
 * wrong-direction (-10011), never on a transient sentinel.
 */
class CabinTemperatureFallbackTest {
    private fun fid(field: String) = FidMap.entries.first { it.field == field }

    private fun mostlySentinelPairs(okFields: Map<String, Int>): List<Pair<Int, Int>> =
        FidMap.entries.map { entry -> 0 to (okFields[entry.field] ?: -10011) }

    private fun settingsWithCapacity(): SettingsRepository {
        val settings = mockk<SettingsRepository>()
        coEvery { settings.getBatteryCapacity() } returns 72.9
        return settings
    }

    private fun gateFixedAt(mode: BatchMode): BatchReadGate {
        val gate = mockk<BatchReadGate>()
        coEvery { gate.mode() } returns mode
        coEvery { gate.recordComparison(any(), any()) } just Runs
        every { gate.recordBatchUnavailable() } just Runs
        return gate
    }

    private suspend fun batchInsideTemp(primary: Int, alt: Int): Int? {
        val helper = mockk<HelperClient>()
        coEvery { helper.readBatch(any()) } returns mostlySentinelPairs(
            mapOf(
                "soc" to java.lang.Float.floatToRawIntBits(50.0f),
                "insideTemp" to primary,
                "insideTempAlt" to alt,
            ),
        )
        val data = NativeParsReader(
            mockk<AutoserviceClient>(),
            settingsWithCapacity(),
            helper,
            gateFixedAt(BatchMode.ACTIVE),
            kindMonitor(),
        ).fetch()
        return data!!.insideTemp
    }

    @Test
    fun `insideTemp prefers the primary generation fid`() = runTest {
        assertEquals(21, batchInsideTemp(primary = 21, alt = 24))
    }

    @Test
    fun `insideTemp falls back to the alternate BYD SDK fid on wrong direction`() = runTest {
        assertEquals(24, batchInsideTemp(primary = -10011, alt = 24))
    }

    @Test
    fun `insideTemp falls back to the alternate BYD SDK fid on feature link error`() = runTest {
        assertEquals(24, batchInsideTemp(primary = 65535, alt = 24))
    }

    @Test
    fun `insideTemp does not fall back on transient sentinel`() = runTest {
        assertNull(batchInsideTemp(primary = -10013, alt = 24))
    }

    @Test
    fun `a failed primary read item does not fall back`() = runTest {
        val helper = mockk<HelperClient>()
        val insideTempIndex = FidMap.entries.indexOf(fid("insideTemp"))
        coEvery { helper.readBatch(any()) } returns mostlySentinelPairs(
            mapOf(
                "soc" to java.lang.Float.floatToRawIntBits(50.0f),
                "insideTempAlt" to 24,
            ),
        ).mapIndexed { i, pair -> if (i == insideTempIndex) -998 to 0 else pair }
        val data = NativeParsReader(
            mockk<AutoserviceClient>(),
            settingsWithCapacity(),
            helper,
            gateFixedAt(BatchMode.ACTIVE),
            kindMonitor(),
        ).fetch()

        assertNull(data!!.insideTemp)
    }

    @Test
    fun `the ADB path decides the fallback from the raw primary sample`() = runTest {
        val primary = fid("insideTemp")
        val alt = fid("insideTempAlt")
        val auto = mockk<AutoserviceClient>()
        coEvery { auto.isAvailable() } returns true
        coEvery { auto.getInt(any(), any()) } returns null
        coEvery { auto.getIntRaw(any(), any()) } returns null
        coEvery { auto.getFloat(any(), any()) } returns null
        coEvery { auto.getFloat(fid("soc").device, fid("soc").fid) } returns 55.0f
        coEvery { auto.getIntRaw(primary.device, primary.fid) } returns 65535
        coEvery { auto.getInt(alt.device, alt.fid) } returns 23

        val data = NativeParsReader(
            auto,
            settingsWithCapacity(),
            mockk<HelperClient>(),
            gateFixedAt(BatchMode.OFF),
            kindMonitor(),
        ).fetch()

        assertEquals(23, data!!.insideTemp)
    }

    @After
    fun restoreConstants() {
        FidAddresses.resetToConstants()
    }
}
