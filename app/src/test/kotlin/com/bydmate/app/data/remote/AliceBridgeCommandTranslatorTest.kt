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
    fun `window open close and percentage translate without raw fids`() {
        assertEquals(
            "主驾打开100",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"window.driver.open"}"""))?.vehicleCommand,
        )
        assertEquals(
            "主驾打开0",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"window.driver.close"}"""))?.vehicleCommand,
        )
        assertEquals(
            "后左打开35",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"window.rear_left.position","value":35}"""))?.vehicleCommand,
        )
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"window.driver.position","value":101}""")))
    }

    @Test
    fun `dangerous and raw vehicle commands are rejected`() {
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"doors.unlock"}""")))
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"trunk.open"}""")))
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"command":"车门解锁"}""")))
    }
}
