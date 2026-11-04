package com.bydmate.app.data.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AliceBridgeCommandTranslatorTest {
    private fun command(action: String, value: Int? = null) = AliceBridgeCommandTranslator.resolve(action, value)

    @Test fun `temperature follows the translator 16 to 33 window`() {
        assertEquals("设置温度16", command("climate.temperature", 5))
        assertEquals("设置温度16", command("climate.temperature", 16))
        assertEquals("设置温度17", command("climate.temperature", 17))
        assertEquals("设置温度22", command("climate.temperature", 22))
        assertEquals("设置温度33", command("climate.temperature", 33))
        assertEquals("设置温度33", command("climate.temperature", 40))
        assertNull(command("climate.temperature"))
    }

    @Test fun `Alice seat levels are off low high only`() {
        assertEquals("主驾座椅加热1档", command("seat.driver.heat", 1))
        assertEquals("主驾座椅加热2档", command("seat.driver.heat", 2))
        assertNull(command("seat.driver.heat", 3))
        assertNull(command("seat.driver.heat"))
    }

    @Test fun `seat level zero means off`() {
        assertEquals("副驾座椅通风关闭", command("seat.passenger.vent", 0))
    }

    @Test fun `fan level stays within 1 to 7`() {
        assertEquals("风量3", command("climate.fan_level", 3))
        assertNull(command("climate.fan_level", 0))
        assertNull(command("climate.fan_level", 8))
    }

    @Test fun `Alice window percentage maps to deterministic vehicle command`() {
        assertEquals("主驾打开37", command("window.driver.position", 37))
        assertEquals("后右打开65", command("window.rear_right.position", 65))
        assertEquals("副驾打开0", command("window.passenger.position", 0))
        assertEquals("后左打开100", command("window.rear_left.position", 100))
    }

    @Test fun `Alice window percentage rejects out of range values`() {
        assertNull(command("window.driver.position", 101))
        assertNull(command("window.driver.position", -1))
        assertNull(command("window.driver.position"))
    }

    @Test fun `airflow and roof actions stay semantic`() {
        assertEquals("吹面吹脚除霜", command("climate.airflow_face_feet_windshield"))
        assertEquals("吹面除霜", command("climate.airflow_face_windshield"))
        assertEquals("天窗通风", command("sunroof.vent"))
        assertEquals("天窗停止", command("sunroof.stop"))
        assertEquals("空调自动", command("climate.auto_on"))
    }

    @Test fun `half sunroof is the half slide whichever name the worker uses`() {
        assertEquals("天窗打开50", command("sunroof.half"))
        assertEquals("天窗打开50", command("sunroof.tilt"))
    }

    @Test fun `raw command injection is rejected`() {
        assertNull(command("车门解锁"))
        assertNull(command("raw.fid.write", 1))
        assertNull(command(""))
    }

    @Test fun `unadvertised legacy vehicle actions are rejected`() {
        assertNull(command("doors.unlock"))
        assertNull(command("fridge.cool"))
        assertNull(command("light.hazard_on"))
    }
}
