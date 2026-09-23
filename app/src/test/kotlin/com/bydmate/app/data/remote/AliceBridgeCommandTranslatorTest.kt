package com.bydmate.app.data.remote

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AliceBridgeCommandTranslatorTest {
    @Test fun `ATTO 3 temperature maps below 18 to LO and above 32 to HI`() {
        fun command(value: Int) = AliceBridgeCommandTranslator.resolve(
            JSONObject("""{"action":"climate.temperature","value":$value}""")
        )?.vehicleCommand
        assertEquals("设置温度17", command(5))
        assertEquals("设置温度17", command(17))
        assertEquals("设置温度18", command(18))
        assertEquals("设置温度22", command(22))
        assertEquals("设置温度32", command(32))
        assertEquals("设置温度33", command(33))
        assertEquals("设置温度33", command(40))
    }

    @Test fun `Alice seat levels are off low high only`() {
        assertEquals(
            "主驾座椅加热1档",
            AliceBridgeCommandTranslator.resolve(
                JSONObject("""{"action":"seat.driver.heat","value":1}""")
            )?.vehicleCommand,
        )
        assertEquals(
            "主驾座椅加热2档",
            AliceBridgeCommandTranslator.resolve(
                JSONObject("""{"action":"seat.driver.heat","value":2}""")
            )?.vehicleCommand,
        )
        assertNull(
            AliceBridgeCommandTranslator.resolve(
                JSONObject("""{"action":"seat.driver.heat","value":3}""")
            )
        )
    }

    @Test fun `seat level zero means off`() {
        assertEquals(
            "副驾座椅通风关闭",
            AliceBridgeCommandTranslator.resolve(
                JSONObject("""{"action":"seat.passenger.vent","value":0}""")
            )?.vehicleCommand,
        )
    }

    @Test fun `Alice window percentage maps to deterministic vehicle command`() {
        assertEquals(
            "主驾打开37",
            AliceBridgeCommandTranslator.resolve(
                JSONObject("""{"action":"window.driver.position","value":37}""")
            )?.vehicleCommand,
        )
        assertEquals(
            "后右打开65",
            AliceBridgeCommandTranslator.resolve(
                JSONObject("""{"action":"window.rear_right.position","value":65}""")
            )?.vehicleCommand,
        )
    }

    @Test fun `Alice window percentage rejects out of range values`() {
        assertNull(
            AliceBridgeCommandTranslator.resolve(
                JSONObject("""{"action":"window.driver.position","value":101}""")
            )
        )
    }

    @Test fun `airflow and roof actions stay semantic`() {
        assertEquals(
            "吹面吹脚除霜",
            AliceBridgeCommandTranslator.resolve(
                JSONObject("""{"action":"climate.airflow_face_feet_windshield"}""")
            )?.vehicleCommand,
        )
        assertEquals(
            "天窗通风",
            AliceBridgeCommandTranslator.resolve(
                JSONObject("""{"action":"sunroof.vent"}""")
            )?.vehicleCommand,
        )
    }

    @Test fun `raw command injection is rejected`() {
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"command":"车门解锁"}""")))
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"raw.fid.write","value":1}""")))
    }

    @Test fun `unadvertised legacy vehicle actions are rejected`() {
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"doors.unlock"}""")))
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"fridge.cool"}""")))
        assertNull(AliceBridgeCommandTranslator.resolve(JSONObject("""{"action":"light.hazard_on"}""")))
    }
}
