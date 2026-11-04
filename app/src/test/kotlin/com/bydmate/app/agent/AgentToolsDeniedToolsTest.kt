package com.bydmate.app.agent

import android.content.Context
import com.bydmate.app.cluster.ClusterVoiceControl
import com.bydmate.app.data.automation.ActionDispatcher
import com.bydmate.app.data.automation.AutomationEngine
import com.bydmate.app.data.local.dao.ChargeDao
import com.bydmate.app.data.local.dao.RuleDao
import com.bydmate.app.data.local.dao.TripDao
import com.bydmate.app.data.remote.InsightsManager
import com.bydmate.app.data.remote.OpenRouterClient
import com.bydmate.app.data.repository.PlaceRepository
import com.bydmate.app.data.repository.SettingsRepository
import com.bydmate.app.domain.battery.BatteryStateRepository
import com.bydmate.app.domain.calculator.RangeCalculator
import com.bydmate.app.voice.VoiceGate
import io.mockk.confirmVerified
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * A restricted detached turn (an Alice question with «may control the car» / «may navigate» off)
 * neither sees nor runs the tools of the switched-off class, and every tool is classified, so a new
 * one cannot slip past the Alice permissions unnoticed.
 */
class AgentToolsDeniedToolsTest {

    private val actionDispatcher = mockk<ActionDispatcher>()

    private fun makeTools() = AgentTools(
        mockk<VoiceGate>(),
        mockk<BatteryStateRepository>(),
        mockk<RangeCalculator>(),
        mockk<TripDao>(),
        mockk<ChargeDao>(),
        actionDispatcher,
        mockk<RuleDao>(relaxed = true),
        mockk<AutomationEngine>(),
        mockk<PlaceRepository>(),
        mockk<WeatherClient>(),
        mockk<ExaSearchClient>(),
        mockk<OpenRouterClient>(),
        mockk<SettingsRepository>(relaxed = true),
        mockk<ContactLookup>(),
        mockk<Context>(relaxed = true),
        mockk<ClusterVoiceControl>(relaxed = true),
        mockk<ChargerSearchClient>(relaxed = true),
        mockk<InsightsManager>(relaxed = true),
        mockk<ZaiSearchClient>(relaxed = true),
        mockk<LlmConnectionResolver>(relaxed = true),
    )

    private fun toolNames(schemas: JSONArray): Set<String> =
        (0 until schemas.length()).map {
            schemas.getJSONObject(it).getJSONObject("function").getString("name")
        }.toSet()

    private val classified = AgentTools.CAR_CONTROL_TOOLS + AgentTools.NAVIGATION_TOOLS + AgentTools.ALWAYS_ALLOWED_TOOLS

    @Test
    fun `every tool is in exactly one class`() = runTest {
        val all = toolNames(makeTools().schemas())
        assertEquals("unclassified tools", emptySet<String>(), all - classified)
        assertEquals("classified names that are no tool", emptySet<String>(), classified - all)
        assertTrue(AgentTools.CAR_CONTROL_TOOLS.intersect(AgentTools.NAVIGATION_TOOLS).isEmpty())
        assertTrue(AgentTools.CAR_CONTROL_TOOLS.intersect(AgentTools.ALWAYS_ALLOWED_TOOLS).isEmpty())
        assertTrue(AgentTools.NAVIGATION_TOOLS.intersect(AgentTools.ALWAYS_ALLOWED_TOOLS).isEmpty())
    }

    @Test
    fun `both permissions off deny both classes, each permission lifts its own`() {
        val union = AgentTools.CAR_CONTROL_TOOLS + AgentTools.NAVIGATION_TOOLS
        assertEquals(union, AgentTools.deniedTools(vehicleControl = false, navigation = false))
        assertEquals(AgentTools.NAVIGATION_TOOLS, AgentTools.deniedTools(vehicleControl = true, navigation = false))
        assertEquals(AgentTools.CAR_CONTROL_TOOLS, AgentTools.deniedTools(vehicleControl = false, navigation = true))
        assertEquals(emptySet<String>(), AgentTools.deniedTools(vehicleControl = true, navigation = true))
    }

    @Test
    fun `the car and navigation classes hold the tools that act`() {
        assertTrue(AgentTools.CAR_CONTROL_TOOLS.containsAll(listOf(
            "vehicle_control", "set_sentry", "set_hotspot", "set_screen", "split_screen",
            "run_automation", "set_automation_enabled", "call_contact")))
        assertEquals(setOf("navigate_to", "search_on_map", "show_point_on_map", "go_home"), AgentTools.NAVIGATION_TOOLS)
    }

    @Test
    fun `schemas leave out exactly the denied tools`() = runTest {
        val tools = makeTools()
        val denied = AgentTools.deniedTools(vehicleControl = false, navigation = false)
        val full = toolNames(tools.schemas(includeAutomationTools = false))
        val restricted = toolNames(tools.schemas(includeAutomationTools = false, deniedTools = denied))
        assertTrue(restricted.intersect(denied).isEmpty())
        assertEquals(full - denied, restricted)
        assertTrue(restricted.containsAll(listOf("get_vehicle_state", "launch_app", "get_weather", "find_chargers")))
    }

    @Test
    fun `an empty denied set keeps the schemas as they are`() = runTest {
        val tools = makeTools()
        assertEquals(
            tools.schemas(includeAutomationTools = false).toString(),
            tools.schemas(includeAutomationTools = false, deniedTools = emptySet()).toString(),
        )
    }

    @Test
    fun `execute refuses a denied tool even when the model calls it`() = runTest {
        val tools = makeTools()
        val denied = AgentTools.deniedTools(vehicleControl = false, navigation = false)
        for (name in denied) {
            val res = tools.execute(AgentToolCall(id = "1", name = name, arguments = """{"command":"window_open_all"}"""),
                allowAutomationTools = false, deniedTools = denied)
            assertTrue("$name must be refused by the denied set: $res",
                JSONObject(res).getString("error").contains("запрещён для этого запроса"))
        }
        // Refused before running: the strict ActionDispatcher mock saw no call at all.
        confirmVerified(actionDispatcher)
    }

    @Test
    fun `execute still runs the allowed tools of a restricted turn`() = runTest {
        val denied = AgentTools.deniedTools(vehicleControl = false, navigation = false)
        val res = makeTools().execute(AgentToolCall(id = "1", name = "end_conversation", arguments = "{}"),
            allowAutomationTools = false, deniedTools = denied)
        assertEquals("""{"ok":true}""", res)
        val auto = makeTools().execute(AgentToolCall(id = "1", name = "remember_fact", arguments = "{}"),
            allowAutomationTools = false, deniedTools = denied)
        // The automation fence still stands behind the denied set.
        assertTrue(auto.contains("недоступен в сессии, запущенной автоматизацией"))
        assertFalse(auto.contains("запрещён"))
    }
}
