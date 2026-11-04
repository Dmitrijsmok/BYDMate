package com.bydmate.app.data.remote

import com.bydmate.app.agent.AgentTools
import com.bydmate.app.data.automation.ActionDispatcher
import com.bydmate.app.data.automation.DispatchResult
import com.bydmate.app.data.local.entity.ActionDef
import com.bydmate.app.data.loop.SharedAdaptiveLoop
import com.bydmate.app.data.repository.SettingsRepository
import io.mockk.coEvery
import io.mockk.coVerify
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
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit

/**
 * The fork's deployed worker, "BYDmate Alice Bridge 5.10" (reference/alice-worker/worker.mjs @
 * 656c137e), byte for byte in the shapes it answers: the poll answer has `{id, action, value?,
 * text?}` and no timestamp, `/api/debug` lists `created_at` (server ms), the ack is read from
 * `results` only, and every answer carries Cloudflare's `Date` header. The head unit clock here is
 * fourteen minutes off; neither command age may depend on it.
 */
class AlicePollingBridge510Test {

    private val server = MockWebServer()
    private val acks = LinkedBlockingQueue<JSONObject>()
    private val polls = ConcurrentLinkedQueue<RecordedRequest>()
    private val debugCalls = ConcurrentLinkedQueue<RecordedRequest>()
    private val settings = mockk<SettingsRepository>()
    private val actionDispatcher = mockk<ActionDispatcher>(relaxed = true)
    private val loop = mockk<SharedAdaptiveLoop>()
    private lateinit var manager: AlicePollingManager

    /** The worker's clock: the head unit's runs 845 s behind it. */
    private val serverNow = System.currentTimeMillis() + 845_000L
    private var pollBody = """{"commands":[]}"""

    private fun httpDate(ms: Long): String = SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss 'GMT'", Locale.US)
        .apply { timeZone = TimeZone.getTimeZone("GMT") }.format(Date(ms))

    private fun worker510(body: String) = MockResponse()
        .setHeader("Content-Type", "application/json; charset=utf-8")
        .setHeader("Cache-Control", "no-store")
        .setHeader("Date", httpDate(serverNow))
        .setBody(body)

    @Before fun setUp() {
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.getHeader("X-Api-Key") != "test-key") {
                    return worker510("""{"error":"unauthorized"}""").setResponseCode(401)
                }
                return when (request.requestUrl?.encodedPath) {
                    "/api/poll" -> {
                        polls += request
                        worker510(pollBody).also { pollBody = """{"commands":[]}""" }
                    }
                    "/api/debug" -> {
                        debugCalls += request
                        worker510(
                            """{"bridge":"5.10","allowed_actions":["light.interior_on"],"state":null,"commands":[""" +
                                """{"id":"fresh","action":"light.interior_on","value":null,"created_at":${serverNow - 4_000L},""" +
                                """"acked":0,"success":null,"error":null},""" +
                                """{"id":"stale","action":"climate.on","value":null,"created_at":${serverNow - 845_000L},""" +
                                """"acked":0,"success":null,"error":null}]}""",
                        )
                    }
                    "/api/ack" -> {
                        acks.put(JSONObject(request.body.readUtf8()))
                        worker510("""{"ok":true}""")
                    }
                    "/api/state" -> worker510("""{"ok":true}""")
                    else -> worker510("""{"error":"not_found"}""").setResponseCode(404)
                }
            }
        }
        server.start()
        coEvery { settings.getString(SettingsRepository.KEY_ALICE_ENDPOINT, any()) } returns server.url("/").toString()
        coEvery { settings.getString(SettingsRepository.KEY_ALICE_API_KEY, any()) } returns "test-key"
        coEvery { settings.getString(SettingsRepository.KEY_ALICE_VEHICLE_CONTROL, any()) } returns "true"
        coEvery { settings.getString(SettingsRepository.KEY_ALICE_NAVIGATION, any()) } returns "false"
        every { loop.flow } returns MutableSharedFlow()
        coEvery { actionDispatcher.dispatch(any(), any()) } returns DispatchResult(true)
    }

    @After fun tearDown() {
        if (::manager.isInitialized) manager.stop()
        server.shutdown()
    }

    private fun start() {
        manager = AlicePollingManager(OkHttpClient(), settings, loop, AliceBridgeExecutor(
            actionDispatcher, mockk(relaxed = true), mockk(relaxed = true), dagger.Lazy { mockk<AgentTools>(relaxed = true) },
        ))
        manager.start()
    }

    private fun results(ack: JSONObject): Map<String, JSONObject> {
        val array = ack.getJSONArray("results")
        return (0 until array.length()).associate { array.getJSONObject(it).let { r -> r.getString("id") to r } }
    }

    @Test fun `the first answer after start is aged from the worker record, not the unit clock`() {
        pollBody = """{"commands":[{"id":"fresh","action":"light.interior_on"},{"id":"stale","action":"climate.on"}]}"""
        start()

        val ack = acks.poll(10, TimeUnit.SECONDS)
        assertNotNull("the worker got no ack", ack)
        val results = results(ack!!)
        assertEquals(true, results.getValue("fresh").getBoolean("success"))
        assertEquals(false, results.getValue("stale").getBoolean("success"))
        assertEquals(AliceCommandTtl.EXPIRED, results.getValue("stale").getString("error"))
        coVerify(exactly = 1) { actionDispatcher.dispatch(ActionDef("打开车内灯", "Alice", "param"), any()) }
        coVerify(exactly = 0) { actionDispatcher.dispatch(ActionDef("自动空调", "Alice", "param"), any()) }
        assertEquals(1, debugCalls.size)
        assertEquals("test-key", debugCalls.single().getHeader("X-Api-Key"))
        assertEquals("debug_lookup", AliceBridgeDiagnostics.lastCommand?.ageSource)
        // The unit clock runs 845 s behind the worker's Date header (±1 s).
        val skew = AliceBridgeDiagnostics.clockSkewMs!!
        assertTrue("skew $skew", skew in -847_000L..-843_000L)
    }

    @Test fun `the poll is the long poll 5_10 holds, with its key`() {
        start()
        val deadline = System.currentTimeMillis() + 5_000L
        while (polls.isEmpty() && System.currentTimeMillis() < deadline) Thread.sleep(20)
        val poll = polls.peek()
        assertNotNull(poll)
        assertEquals("GET", poll!!.method)
        assertEquals("2000", poll.requestUrl?.queryParameter("wait_ms"))
        assertEquals("test-key", poll.getHeader("X-Api-Key"))
    }

    @Test fun `the ack 5_10 reads is the results array with id success and error`() {
        pollBody = """{"commands":[{"id":"fresh","action":"light.interior_on"}]}"""
        start()
        val ack = acks.poll(10, TimeUnit.SECONDS)!!
        val result = ack.getJSONArray("results").getJSONObject(0)
        assertEquals("fresh", result.getString("id"))
        assertEquals(true, result.getBoolean("success"))
    }
}
