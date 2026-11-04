package com.bydmate.app.data.remote

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AliceBridgeRouterTest {

    private class RecordingActions : AliceBridgeActions {
        val calls = mutableListOf<String>()
        val queryPermissions = mutableListOf<AliceBridgePermissions>()
        private fun record(kind: String, command: AliceBridgeCommand): Result<Unit> {
            calls += "$kind:${command.action.ifEmpty { command.rawCommand }}"
            return Result.success(Unit)
        }
        override suspend fun vehicle(command: AliceBridgeCommand) = record("vehicle", command)
        override suspend fun navigation(command: AliceBridgeCommand) = record("navigation", command)
        override suspend fun app(command: AliceBridgeCommand) = record("app", command)
        override suspend fun media(command: AliceBridgeCommand) = record("media", command)
        override suspend fun query(command: AliceBridgeCommand, permissions: AliceBridgePermissions): Result<Unit> {
            queryPermissions += permissions
            return record("query", command)
        }
    }

    private val vehicleCommands = listOf(
        AliceBridgeCommand("1", action = "climate.on"),
        AliceBridgeCommand("2", action = "seat.driver.heat", value = 2),
        AliceBridgeCommand("3", action = "light.ambient_on"),
        AliceBridgeCommand("4", action = "trunk.rear.open"),
        AliceBridgeCommand("5", action = "window.driver.position", value = 40),
        AliceBridgeCommand("6", action = "sunroof.position", value = 50),
        AliceBridgeCommand("7", action = "window.all.vent"),
        AliceBridgeCommand("8", action = "vehicle.command", text = "открой двери"),
        AliceBridgeCommand("9", rawCommand = "车门解锁"),
    )
    private val navigationCommands = listOf(
        AliceBridgeCommand("n1", action = "navigation.route", text = """{"destination":"Рига"}"""),
        AliceBridgeCommand("n2", action = "navigation.search", text = """{"query":"заправка"}"""),
        AliceBridgeCommand("n3", action = "navigation.show", text = """{"destination":"Минск"}"""),
    )
    private val alwaysAllowed = listOf(
        AliceBridgeCommand("a1", action = "app.youtube.open") to "app",
        AliceBridgeCommand("a2", action = "app.navigation.open") to "app",
        AliceBridgeCommand("a3", action = "navigation.cluster_on") to "app",
        AliceBridgeCommand("a4", action = "media.next") to "media",
        AliceBridgeCommand("a5", action = "agent.query", text = "какой заряд батареи") to "query",
    )

    private fun run(command: AliceBridgeCommand, permissions: AliceBridgePermissions, actions: AliceBridgeActions) =
        runBlocking { AliceBridgeRouter.execute(command, permissions, actions) }

    @Test fun `with both permissions off no vehicle or navigation command is executed`() {
        val actions = RecordingActions()
        val off = AliceBridgePermissions()
        vehicleCommands.forEach { command ->
            assertEquals(command.toString(), AliceBridgeRouter.VEHICLE_CONTROL_DISABLED,
                run(command, off, actions).exceptionOrNull()?.message)
        }
        navigationCommands.forEach { command ->
            assertEquals(command.toString(), AliceBridgeRouter.NAVIGATION_DISABLED,
                run(command, off, actions).exceptionOrNull()?.message)
        }
        assertTrue(actions.calls.toString(), actions.calls.isEmpty())
    }

    @Test fun `each permission opens only its own kind`() {
        val vehicleOnly = RecordingActions()
        (vehicleCommands + navigationCommands).forEach { run(it, AliceBridgePermissions(vehicleControl = true), vehicleOnly) }
        assertTrue(vehicleOnly.calls.all { it.startsWith("vehicle:") })
        assertEquals(vehicleCommands.size, vehicleOnly.calls.size)

        val navigationOnly = RecordingActions()
        (vehicleCommands + navigationCommands).forEach { run(it, AliceBridgePermissions(navigation = true), navigationOnly) }
        assertTrue(navigationOnly.calls.all { it.startsWith("navigation:") })
        assertEquals(navigationCommands.size, navigationOnly.calls.size)
    }

    @Test fun `apps, media, projection and agent questions never need a permission`() {
        val actions = RecordingActions()
        alwaysAllowed.forEach { (command, _) ->
            assertTrue(command.toString(), run(command, AliceBridgePermissions(), actions).isSuccess)
        }
        assertEquals(alwaysAllowed.map { (command, kind) -> "$kind:${command.action}" }, actions.calls)
    }

    // The question itself needs no permission, but its agent turn must not get around them.
    @Test fun `an agent question carries the permissions to the agent turn`() {
        val actions = RecordingActions()
        val question = AliceBridgeCommand("q", action = "agent.query", text = "какой заряд батареи")
        val all = listOf(
            AliceBridgePermissions(),
            AliceBridgePermissions(vehicleControl = true),
            AliceBridgePermissions(navigation = true),
            AliceBridgePermissions(vehicleControl = true, navigation = true),
        )
        all.forEach { assertTrue(run(question, it, actions).isSuccess) }
        assertEquals(all, actions.queryPermissions)
    }

    @Test fun `unknown actions are refused without executing anything`() {
        val actions = RecordingActions()
        val all = AliceBridgePermissions(vehicleControl = true, navigation = true)
        listOf(AliceBridgeCommand("x", action = "raw.fid.write", value = 1), AliceBridgeCommand("y")).forEach {
            assertEquals(AliceBridgeRouter.UNSUPPORTED_ACTION, run(it, all, actions).exceptionOrNull()?.message)
        }
        assertTrue(actions.calls.isEmpty())
    }
}
