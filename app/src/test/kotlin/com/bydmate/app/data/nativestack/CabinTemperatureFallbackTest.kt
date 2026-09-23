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

class CabinTemperatureFallbackTest {
    private fun fid(field: String) = FidMap.entries.first { it.field == field }

    private fun mostlySentinelPairs(okFields: Map<String, Int>): List<Pair<Int, Int>> =
        FidMap.entries.map { entry -> 0 to (okFields[entry.field] ?: -10011) }

    private fun settingsWithCapacity(): SettingsRepository {
        val settings = mockk<SettingsRepository>()
        coEvery { settings.getBatteryCapacity() } returns 72.9
        return settings
    }

    private fun gateActive(): BatchReadGate {
        val gate = mockk<BatchReadGate>()
        coEvery { gate.mode() } returns BatchMode.ACTIVE
        coEvery { gate.recordComparison(any(), any()) } just Runs
        every { gate.recordBatchUnavailable() } just Runs
        return gate
    }

    @Test
    fun `insideTemp prefers the primary generation fid`() = runTest {
        val helper = mockk<HelperClient>()
        coEvery { helper.readBatch(any()) } returns mostlySentinelPairs(
            mapOf(
                fid("soc").field to java.lang.Float.floatToRawIntBits(50.0f),
                fid("insideTemp").field to 21,
                fid("insideTempAlt").field to 24,
            ),
        )
        val data = NativeParsReader(
            mockk<AutoserviceClient>(),
            settingsWithCapacity(),
            helper,
            gateActive(),
        ).fetch()

        assertEquals(21, data!!.insideTemp)
    }

    @Test
    fun `insideTemp falls back to alternate BYD SDK fid on feature link error`() = runTest {
        val helper = mockk<HelperClient>()
        coEvery { helper.readBatch(any()) } returns mostlySentinelPairs(
            mapOf(
                fid("soc").field to java.lang.Float.floatToRawIntBits(50.0f),
                fid("insideTemp").field to -10011,
                fid("insideTempAlt").field to 24,
            ),
        )
        val data = NativeParsReader(
            mockk<AutoserviceClient>(),
            settingsWithCapacity(),
            helper,
            gateActive(),
        ).fetch()

        assertEquals(24, data!!.insideTemp)
    }

    @Test
    fun `insideTemp does not fall back on transient sentinel`() = runTest {
        val helper = mockk<HelperClient>()
        coEvery { helper.readBatch(any()) } returns mostlySentinelPairs(
            mapOf(
                fid("soc").field to java.lang.Float.floatToRawIntBits(50.0f),
                fid("insideTemp").field to -10013,
                fid("insideTempAlt").field to 24,
            ),
        )
        val data = NativeParsReader(
            mockk<AutoserviceClient>(),
            settingsWithCapacity(),
            helper,
            gateActive(),
        ).fetch()

        assertNull(data!!.insideTemp)
    }

    @After
    fun restoreConstants() {
        FidAddresses.resetToConstants()
    }
}
