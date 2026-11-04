package com.bydmate.app.data.remote

import com.bydmate.app.data.vehicle.VehicleApi
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AliceApertureControllerTest {
    private val vehicleApi = mockk<VehicleApi>(relaxed = true)
    private val controller = AliceApertureController(vehicleApi)
    private var speedReads = 0
    private fun speed(value: Int?): suspend () -> Int? = { speedReads++; value }

    @Test fun `opening a window at an unknown speed is refused before any write`() = runBlocking {
        coEvery { vehicleApi.readWindowDriver() } returns 0
        val result = controller.positionWindow("window.driver.position", 40, speed(null))
        assertEquals("SpeedUnknown", result.exceptionOrNull()?.message)
        coVerify(exactly = 0) { vehicleApi.writeWindowDriver(any()) }
        coVerify(exactly = 0) { vehicleApi.dispatch(any()) }
    }

    @Test fun `full open goes through the speed gate, full close does not need the speed`() = runBlocking {
        coEvery { vehicleApi.dispatch(any()) } returns Result.success(Unit)
        assertEquals("WindowsSpeed", controller.positionWindow("window.passenger.position", 100, speed(130))
            .exceptionOrNull()?.message)
        assertTrue(controller.positionWindow("window.passenger.position", 0, speed(130)).isSuccess)
        coVerify(exactly = 0) { vehicleApi.dispatch("副驾打开100") }
        coVerify(exactly = 1) { vehicleApi.dispatch("副驾打开0") }
    }

    @Test fun `a percentage the percent write reaches is done without driving the pane`() = runBlocking {
        coEvery { vehicleApi.readWindowRearLeft() } returnsMany listOf(0, 38, 40)
        coEvery { vehicleApi.writeWindowRearLeft(40) } returns Result.success(Unit)
        assertTrue(controller.positionWindow("window.rear_left.position", 40, speed(0)).isSuccess)
        coVerify(exactly = 0) { vehicleApi.dispatch(any()) }
    }

    @Test fun `sunroof takes the three detents only, the half one being the half slide`() = runBlocking {
        coEvery { vehicleApi.dispatch(any()) } returns Result.success(Unit)
        assertTrue(controller.positionSunroof(50, speed(20)).isSuccess)
        coVerify { vehicleApi.dispatch("天窗打开50") }
        assertEquals("SunroofSpeed", controller.positionSunroof(100, speed(90)).exceptionOrNull()?.message)
        assertEquals("sunroof_percent_not_supported", controller.positionSunroof(30, speed(0)).exceptionOrNull()?.message)
        assertTrue(controller.positionSunroof(0, speed(null)).isSuccess)
    }
}
