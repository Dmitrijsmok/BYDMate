package com.bydmate.app.data.automation

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AgentQueryPermissionsTest {

    @Test fun `a rule's payload carries no permissions and stays unrestricted`() {
        assertNull(AgentQueryPermissions.from(null))
        assertNull(AgentQueryPermissions.from(JSONObject().put("prompt", "сводка")))
    }

    @Test fun `the bridge's permissions survive the payload round trip`() {
        listOf(false to false, true to false, false to true, true to true).forEach { (vehicle, navigation) ->
            val payload = AgentQueryPermissions(vehicle, navigation).writeTo(JSONObject().put("prompt", "какой заряд"))
            val parsed = JSONObject(payload.toString())
            assertEquals("какой заряд", parsed.getString("prompt"))
            assertEquals(AgentQueryPermissions(vehicle, navigation), AgentQueryPermissions.from(parsed))
        }
    }

    @Test fun `a malformed or partial permissions value fails closed`() {
        val closed = AgentQueryPermissions(vehicleControl = false, navigation = false)
        assertEquals(closed, AgentQueryPermissions.from(JSONObject("""{"prompt":"x","permissions":"all"}""")))
        assertEquals(closed, AgentQueryPermissions.from(JSONObject("""{"prompt":"x","permissions":null}""")))
        assertEquals(closed, AgentQueryPermissions.from(JSONObject("""{"prompt":"x","permissions":{}}""")))
        assertEquals(
            AgentQueryPermissions(vehicleControl = true, navigation = false),
            AgentQueryPermissions.from(JSONObject("""{"prompt":"x","permissions":{"vehicle_control":true}}""")),
        )
    }
}
