package com.bydmate.app.data.remote

import com.bydmate.app.agent.AgentTools
import com.bydmate.app.data.automation.ActionDispatcher
import com.bydmate.app.data.automation.DispatchResult
import com.bydmate.app.data.local.entity.ActionDef
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Runs Alice bridge commands once [AliceBridgeRouter] has let them through. Every vehicle write
 * is an ActionDispatcher "param" step, so the bridge gets the same allowlist, safety and speed
 * gates as an automation (speed-gated commands on a direct speed read, fail-closed); on top of
 * them the rear trunk opens only at a known standstill. Window and sunroof percentages go to
 * [AliceApertureController], which gates its opening moves on the same direct read; routes,
 * map search and points go to the agent's navigation engine directly.
 */
@Singleton
class AliceBridgeExecutor @Inject constructor(
    private val actionDispatcher: ActionDispatcher,
    private val apertureController: AliceApertureController,
    private val appDispatcher: AliceAppActionDispatcher,
    private val agentTools: dagger.Lazy<AgentTools>,
) : AliceBridgeActions {

    /** The latest poll of the car, fed by [AlicePollingManager]. */
    @Volatile var latestData: DiParsData? = null

    override suspend fun vehicle(command: AliceBridgeCommand): Result<Unit> {
        if (command.action.isEmpty()) return dispatchCommands(listOf(command.rawCommand))
        if (command.action == "vehicle.command") return vehicleText(command.text)
        aperture(command)?.let { return it }
        val vehicleCommand = AliceBridgeCommandTranslator.resolve(command.action, command.value)
            ?: return AliceBridgeRouter.failure(AliceBridgeRouter.UNSUPPORTED_ACTION)
        return dispatchCommands(listOf(vehicleCommand))
    }

    /** Route, map search, point: the agent's navigation engine called directly, no LLM. */
    override suspend fun navigation(command: AliceBridgeCommand): Result<Unit> {
        val request = AliceLocalCommandRouter.navigationRequest(command.action, command.text)
            ?: return AliceBridgeRouter.failure("missing_navigation_target")
        val tools = agentTools.get()
        val response = when (request.mode) {
            AliceNavigationRequest.Mode.ROUTE -> tools.navigateDirect(request.target, request.go, request.app)
            AliceNavigationRequest.Mode.SEARCH -> tools.searchMapDirect(request.target, request.app)
            AliceNavigationRequest.Mode.SHOW -> tools.showPointDirect(request.target, request.app)
        }
        val json = runCatching { JSONObject(response) }.getOrNull()
        return if (json?.optBoolean("ok", false) == true) Result.success(Unit)
        else AliceBridgeRouter.failure((json?.opt("error") as? String)?.takeIf(String::isNotBlank) ?: "navigation_failed")
    }

    override suspend fun app(command: AliceBridgeCommand): Result<Unit> = appDispatcher.app(command, latestData)

    override suspend fun media(command: AliceBridgeCommand): Result<Unit> = appDispatcher.media(command, latestData)

    /** Automotive questions only; the answer is spoken by the BYDMate agent like an automation's
     *  agent_query. */
    override suspend fun query(command: AliceBridgeCommand): Result<Unit> {
        val prompt = command.text
        if (prompt.isEmpty()) return AliceBridgeRouter.failure("missing_agent_query")
        if (!AliceLocalCommandRouter.isAutomotiveAgentQuery(prompt)) {
            return AliceBridgeRouter.failure("agent_query_outside_automotive_domain")
        }
        val payload = JSONObject().put("prompt", prompt).toString()
        return actionDispatcher.dispatch(ActionDef("", ALICE, "agent_query", payload), latestData)
            .asResult("agent_query_failed")
    }

    /** Window and sunroof percentages: the closed-loop controller, or null for other actions. */
    private suspend fun aperture(command: AliceBridgeCommand): Result<Unit>? {
        val speedNow: suspend () -> Int? = { actionDispatcher.readSpeedNow() }
        return when (command.action) {
            in WINDOW_POSITION_ACTIONS -> command.value
                ?.let { apertureController.positionWindow(command.action, it, speedNow) }
                ?: AliceBridgeRouter.failure("invalid_window_position")
            "sunroof.position" -> command.value
                ?.let { apertureController.positionSunroof(it, speedNow) }
                ?: AliceBridgeRouter.failure("sunroof_percent_not_supported")
            else -> null
        }
    }

    private suspend fun vehicleText(text: String): Result<Unit> =
        when (val plan = AliceLocalCommandRouter.planVehicleText(text, latestData?.acTemp)) {
            is AliceTextPlan.Commands -> dispatchCommands(plan.commands)
            is AliceTextPlan.Volume -> actionDispatcher.dispatch(
                ActionDef("media_volume", ALICE, "media_volume", plan.payload), latestData,
            ).asResult("volume_command_failed")
            is AliceTextPlan.OpenNavigator -> actionDispatcher.openNavigatorApp(plan.app).asResult("navigator_open_failed")
            is AliceTextPlan.Failed -> AliceBridgeRouter.failure(plan.reason)
        }

    private suspend fun dispatchCommands(commands: List<String>): Result<Unit> {
        for (vehicleCommand in commands) {
            rearTrunkBlock(vehicleCommand)?.let { return it }
            val result = actionDispatcher.dispatch(ActionDef(vehicleCommand, ALICE, "param"), latestData)
            if (!result.success) return result.asResult("vehicle_command_failed")
        }
        return Result.success(Unit)
    }

    /** Nobody stands next to the car when Alice opens the tailgate from afar: a known 0 km/h on a
     *  direct read, or no opening. */
    private suspend fun rearTrunkBlock(command: String): Result<Unit>? {
        if (!ActionDispatcher.isRearTrunkOpenCommand(command)) return null
        val speed = actionDispatcher.readSpeedNow()
            ?: return AliceBridgeRouter.failure("rear_trunk_speed_unknown")
        return if (speed != 0) AliceBridgeRouter.failure("rear_trunk_requires_standstill") else null
    }

    private fun DispatchResult.asResult(fallback: String): Result<Unit> =
        if (success) Result.success(Unit) else AliceBridgeRouter.failure(reason ?: fallback)

    private companion object {
        const val ALICE = "Alice"
        val WINDOW_POSITION_ACTIONS = setOf(
            "window.driver.position",
            "window.passenger.position",
            "window.rear_left.position",
            "window.rear_right.position",
        )
    }
}
