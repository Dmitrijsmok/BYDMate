package com.bydmate.app.data.remote

import com.bydmate.app.agent.AgentTools
import com.bydmate.app.data.automation.ActionDispatcher
import com.bydmate.app.data.automation.AgentQueryPermissions
import com.bydmate.app.data.automation.DispatchResult
import com.bydmate.app.data.local.entity.ActionDef
import com.bydmate.app.data.loop.SharedAdaptiveLoop
import com.bydmate.app.data.repository.SettingsRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.confirmVerified
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.flow.MutableSharedFlow
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Test
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.ConcurrentLinkedQueue

/**
 * End to end through the real poll loop, router and executor against a fake worker: with the two
 * Alice permissions off nothing reaches ActionDispatcher and the worker is told why per command.
 */
class AlicePollingPermissionTest {

    private val server = MockWebServer()
    private val acks = LinkedBlockingQueue<JSONObject>()
    private val pollBodies = ConcurrentLinkedQueue<String>()
    private val settings = mockk<SettingsRepository>()
    private val actionDispatcher = mockk<ActionDispatcher>(relaxed = true)
    private val aperture = mockk<AliceApertureController>(relaxed = true)
    private val apps = mockk<AliceAppActionDispatcher>(relaxed = true)
    private val agentTools = mockk<AgentTools>(relaxed = true)
    private val loop = mockk<SharedAdaptiveLoop>()
    private lateinit var manager: AlicePollingManager

    private val pollBody = JSONObject().put("commands", org.json.JSONArray()
        .put(command("v1", "climate.on"))
        .put(command("v2", "window.driver.position").put("value", 40))
        .put(command("v3", "vehicle.command").put("text", "открой двери"))
        .put(JSONObject().put("id", "v4").put("command", "车门解锁").put("age_ms", 1_000))
        .put(command("n1", "navigation.route").put("text", """{"destination":"Рига"}"""))
        .put(command("n2", "navigation.search").put("text", """{"query":"заправка"}""")),
    ).toString()

    private fun command(id: String, action: String) = JSONObject().put("id", id).put("action", action).put("age_ms", 1_000)

    @Before fun setUp() {
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when (request.requestUrl?.encodedPath) {
                "/api/poll" -> MockResponse().setBody(pollBodies.poll() ?: """{"commands":[]}""")
                "/api/ack" -> {
                    acks.put(JSONObject(request.body.readUtf8()))
                    MockResponse().setBody("""{"ok":true}""")
                }
                else -> MockResponse().setBody("""{"ok":true}""")
            }
        }
        server.start()
        coEvery { settings.getString(SettingsRepository.KEY_ALICE_ENDPOINT, any()) } returns server.url("/").toString()
        coEvery { settings.getString(SettingsRepository.KEY_ALICE_API_KEY, any()) } returns "test-key"
        every { loop.flow } returns MutableSharedFlow()
        coEvery { actionDispatcher.dispatch(any(), any()) } returns DispatchResult(true)
        coEvery { aperture.positionWindow(any(), any(), any()) } returns Result.success(Unit)
        coEvery { agentTools.navigateDirect(any(), any(), any()) } returns """{"ok":true,"mode":"route"}"""
        coEvery { agentTools.searchMapDirect(any(), any()) } returns """{"error":"не получилось открыть Навигатор"}"""
    }

    @After fun tearDown() {
        if (::manager.isInitialized) manager.stop()
        server.shutdown()
    }

    private fun permissions(vehicle: Boolean, navigation: Boolean) {
        coEvery { settings.getString(SettingsRepository.KEY_ALICE_VEHICLE_CONTROL, any()) } returns vehicle.toString()
        coEvery { settings.getString(SettingsRepository.KEY_ALICE_NAVIGATION, any()) } returns navigation.toString()
    }

    private fun runOnce(vararg bodies: String = arrayOf(pollBody)): Map<String, JSONObject> {
        pollBodies.addAll(bodies)
        manager = AlicePollingManager(OkHttpClient(), settings, loop, AliceBridgeExecutor(actionDispatcher, aperture, apps, dagger.Lazy { agentTools }))
        manager.start()
        val ack = acks.poll(10, TimeUnit.SECONDS)
        assertNotNull("the worker got no ack", ack)
        val results = ack!!.getJSONArray("results")
        return (0 until results.length()).associate { results.getJSONObject(it).let { r -> r.getString("id") to r } }
    }

    @Test fun `with both permissions off nothing reaches ActionDispatcher and the worker hears why`() {
        permissions(vehicle = false, navigation = false)
        val results = runOnce()

        listOf("v1", "v2", "v3", "v4").forEach { id ->
            assertEquals(id, false, results.getValue(id).getBoolean("success"))
            assertEquals(id, AliceBridgeRouter.VEHICLE_CONTROL_DISABLED, results.getValue(id).getString("error"))
        }
        listOf("n1", "n2").forEach { id ->
            assertEquals(id, false, results.getValue(id).getBoolean("success"))
            assertEquals(id, AliceBridgeRouter.NAVIGATION_DISABLED, results.getValue(id).getString("error"))
        }
        coVerify(exactly = 0) { actionDispatcher.dispatch(any(), any()) }
        confirmVerified(actionDispatcher, aperture, apps, agentTools)
    }

    @Test fun `with vehicle control on the commands run as gated ActionDispatcher steps`() {
        permissions(vehicle = true, navigation = false)
        val results = runOnce()

        assertEquals(true, results.getValue("v1").getBoolean("success"))
        assertEquals(true, results.getValue("v4").getBoolean("success"))
        assertEquals(AliceBridgeRouter.NAVIGATION_DISABLED, results.getValue("n1").getString("error"))
        coVerify { actionDispatcher.dispatch(ActionDef("自动空调", "Alice", "param"), any()) }
        // Upstream's raw command goes through the same param step, gates included.
        coVerify { actionDispatcher.dispatch(ActionDef("车门解锁", "Alice", "param"), any()) }
        // Percentages go to the closed-loop controller with a direct speed read.
        coVerify { aperture.positionWindow("window.driver.position", 40, any()) }
    }

    @Test fun `with navigation on routes reach the navigation engine and vehicle commands stay refused`() {
        permissions(vehicle = false, navigation = true)
        val results = runOnce()

        assertEquals(true, results.getValue("n1").getBoolean("success"))
        assertEquals("не получилось открыть Навигатор", results.getValue("n2").getString("error"))
        assertEquals(AliceBridgeRouter.VEHICLE_CONTROL_DISABLED, results.getValue("v1").getString("error"))
        coVerify { agentTools.navigateDirect("Рига", false, "") }
        coVerify(exactly = 0) { actionDispatcher.dispatch(any(), any()) }
    }

    // An agent question needs no permission, but its turn is held to them: the agent_query payload
    // carries both flags, and with them off ActionDispatcher hands the agent a denied tool set.
    @Test fun `an agent question carries the permissions in its agent_query payload`() {
        val question = JSONObject().put("commands", org.json.JSONArray()
            .put(command("q1", "agent.query").put("text", "какой заряд батареи"))).toString()
        val payloads = mutableListOf<String?>()
        coEvery { actionDispatcher.dispatch(any(), any()) } answers {
            payloads += firstArg<ActionDef>().takeIf { it.kind == "agent_query" }?.payload
            DispatchResult(true)
        }
        permissions(vehicle = false, navigation = false)
        assertEquals(true, runOnce(question).getValue("q1").getBoolean("success"))
        manager.stop()
        permissions(vehicle = true, navigation = false)
        acks.clear()
        assertEquals(true, runOnce(question.replace("q1", "q2")).getValue("q2").getBoolean("success"))

        val parsed = payloads.map { AgentQueryPermissions.from(JSONObject(it!!)) }
        assertEquals(listOf(AgentQueryPermissions(false, false), AgentQueryPermissions(true, false)), parsed)
        assertEquals("какой заряд батареи", JSONObject(payloads.first()!!).getString("prompt"))
    }

    @Test fun `upstream raw command without timestamps runs after an empty poll and is acked by id`() {
        permissions(vehicle = true, navigation = false)
        val results = runOnce("""{"commands":[]}""", """{"commands":[{"id":"r1","command":"自动空调"}]}""")

        assertEquals(true, results.getValue("r1").getBoolean("success"))
        coVerify { actionDispatcher.dispatch(ActionDef("自动空调", "Alice", "param"), any()) }
    }

    @Test fun `an unstamped command on the very first poll is of unknown age and expires`() {
        permissions(vehicle = true, navigation = true)
        val results = runOnce("""{"commands":[{"id":"r1","command":"车窗全开"}]}""")

        assertEquals(AliceCommandTtl.EXPIRED, results.getValue("r1").getString("error"))
        coVerify(exactly = 0) { actionDispatcher.dispatch(any(), any()) }
    }
}
