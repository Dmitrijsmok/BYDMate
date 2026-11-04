package com.bydmate.app.data.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AliceBridgeProtocolTest {

    @Test fun `semantic command of the reference worker`() {
        val batch = AliceBridgeProtocol.parsePoll(
            """{"server_time":1700000000000,"commands":[{"id":"a1","action":"Climate.Temperature","value":22.0,""" +
                """"created_at":1699999995000,"age_ms":5000}]}"""
        )!!
        assertEquals(1_700_000_000_000L, batch.serverTimeMs)
        val command = batch.commands.single()
        assertEquals("a1", command.id)
        assertEquals("climate.temperature", command.action)
        assertEquals(22, command.value)
        assertEquals(5_000L, command.ageMs)
        assertEquals(1_699_999_995_000L, command.createdAtMs)
        assertEquals("", command.rawCommand)
    }

    @Test fun `raw command of upstream's worker stays a fallback`() {
        val command = AliceBridgeProtocol.parsePoll("""{"commands":[{"id":7,"command":"自动空调"}]}""")!!
            .commands.single()
        assertEquals("7", command.id)
        assertEquals("", command.action)
        assertEquals("自动空调", command.rawCommand)
        assertNull(command.ageMs)
        assertNull(command.createdAtMs)
        assertEquals(AliceCommandKind.VEHICLE, AliceBridgeRouter.kindOf(command))
    }

    @Test fun `text falls back to prompt and JSON null is no text`() {
        val commands = AliceBridgeProtocol.parsePoll(
            """{"commands":[{"id":"q","action":"agent.query","prompt":"какой заряд"},""" +
                """{"id":"n","action":"vehicle.command","text":null},{"action":"climate.on"}]}"""
        )!!.commands
        assertEquals(2, commands.size)
        assertEquals("какой заряд", commands[0].text)
        assertEquals("", commands[1].text)
    }

    @Test fun `not a poll response`() {
        assertNull(AliceBridgeProtocol.parsePoll("<html>"))
        assertNull(AliceBridgeProtocol.parsePoll("""{"ok":true}"""))
    }

    @Test fun `state report carries the temperatures and leaves absent readings out`() {
        val body = AliceBridgeProtocol.stateBody(
            diParsData(soc = 81, insideTemp = 23, acTemp = 21, exteriorTemp = -4, fanLevel = 3, windowFL = 0),
        )
        assertEquals(81, body.getInt("soc"))
        assertEquals(23, body.getInt("insideTemp"))
        assertEquals(21, body.getInt("acTemp"))
        assertEquals(-4, body.getInt("exteriorTemp"))
        assertEquals(3, body.getInt("fanLevel"))
        assertEquals(0, body.getInt("windowFL"))
        assertFalse(body.has("sunroof"))
        assertFalse(body.has("acWindMode"))
    }

    @Test fun `ack carries ids for upstream and results for the reference worker`() {
        val body = AliceBridgeProtocol.ackBody(
            listOf(AliceAckResult("a", true), AliceAckResult("b", false, AliceCommandTtl.EXPIRED)),
        )
        val ids = body.getJSONArray("ids")
        assertEquals(listOf("a", "b"), (0 until ids.length()).map { ids.getString(it) })
        val results = body.getJSONArray("results")
        assertTrue(results.getJSONObject(0).getBoolean("success"))
        assertFalse(results.getJSONObject(0).has("error"))
        assertFalse(results.getJSONObject(1).getBoolean("success"))
        assertEquals("expired", results.getJSONObject(1).getString("error"))
    }
}
