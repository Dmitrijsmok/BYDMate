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
    fun `fan level accepts byd zero through seven`() {
        assertEquals(
            "风量3",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"climate.fan_level","value":3}"""))?.vehicleCommand,
        )
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"climate.fan_level","value":8}""")))
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
    fun `window open close aggregate and percentage translate without raw fids`() {
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
        assertEquals(
            "车窗全开",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"window.all.open"}"""))?.vehicleCommand,
        )
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"window.driver.position","value":101}""")))
    }

    @Test
    fun `locks trunks roof and shade are semantic only`() {
        assertEquals(
            "车门解锁",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"doors.unlock"}"""))?.vehicleCommand,
        )
        assertEquals(
            "开后备箱",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"trunk.rear.open"}"""))?.vehicleCommand,
        )
        assertEquals(
            "前备箱打开",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"trunk.front.open"}"""))?.vehicleCommand,
        )
        assertEquals(
            "天窗通风",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"sunroof.vent"}"""))?.vehicleCommand,
        )
        assertEquals(
            "遮阳帘关闭",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"sunshade.close"}"""))?.vehicleCommand,
        )
        // Raw command injection remains impossible.
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"command":"车门解锁"}""")))
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"raw.fid.write","value":1}""")))
    }

    @Test
    fun `fridge ranges are bounded`() {
        assertEquals(
            "冰箱制冷-3度",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"fridge.cool_temperature","value":-3}"""))?.vehicleCommand,
        )
        assertEquals(
            "冰箱制热45度",
            AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"fridge.heat_temperature","value":45}"""))?.vehicleCommand,
        )
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"fridge.cool_temperature","value":-7}""")))
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"fridge.heat_temperature","value":51}""")))
    }
}
