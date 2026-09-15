package com.bydmate.app.data.remote

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AliceBridgeCommandTranslatorTest {
    @Test
    fun `climate temperature stays inside validated range`() {
        assertEquals(
            "设置温度22",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"climate.temperature","value":22}"""))?.vehicleCommand,
        )
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"climate.temperature","value":31}""")))
    }

    @Test
    fun `seat levels translate and zero means off`() {
        assertEquals(
            "主驾座椅加热3档",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"seat.driver.heat","value":3}"""))?.vehicleCommand,
        )
        assertEquals(
            "副驾座椅通风关闭",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"seat.passenger.vent","value":0}"""))?.vehicleCommand,
        )
    }

    @Test
    fun `dangerous and raw vehicle commands are rejected`() {
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"doors.unlock"}""")))
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"window.driver.open"}""")))
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"command":"车门解锁"}""")))
    }
}
