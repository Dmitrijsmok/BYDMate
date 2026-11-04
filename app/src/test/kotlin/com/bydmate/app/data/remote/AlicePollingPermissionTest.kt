package com.bydmate.app.data.remote

import com.bydmate.app.data.automation.ActionDispatcher
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
import java.util.concurrent.atomic.AtomicBoolean

/**
 * End to end through the real poll loop, router and executor against a fake worker: with the two
 * Alice permissions off nothing reaches ActionDispatcher and the worker is told why per command.
 */
class AlicePollingPermissionTest {

    private val server = MockWebServer()
    private val acks = LinkedBlockingQueue<JSONObject>()
    private val served = AtomicBoolean(false)
    private val settings = mockk<SettingsRepository>()
    private val actionDispatcher = mockk<ActionDispatcher>(relaxed = true)
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
                "/api/poll" -> MockResponse().setBody(if (served.compareAndSet(false, true)) pollBody else """{"commands":[]}""")
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
    }

    @After fun tearDown() {
        if (::manager.isInitialized) manager.stop()
        server.shutdown()
    }

    private fun permissions(vehicle: Boolean, navigation: Boolean) {
        coEvery { settings.getString(SettingsRepository.KEY_ALICE_VEHICLE_CONTROL, any()) } returns vehicle.toString()
        coEvery { settings.getString(SettingsRepository.KEY_ALICE_NAVIGATION, any()) } returns navigation.toString()
    }

    private fun runOnce(): Map<String, JSONObject> {
        manager = AlicePollingManager(OkHttpClient(), settings, loop, AliceBridgeExecutor(actionDispatcher))
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
        confirmVerified(actionDispatcher)
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
    }
}
