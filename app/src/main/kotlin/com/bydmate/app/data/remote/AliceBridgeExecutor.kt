package com.bydmate.app.data.remote

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
 * them the rear trunk opens only at a known standstill.
 */
@Singleton
class AliceBridgeExecutor @Inject constructor(
    private val actionDispatcher: ActionDispatcher,
) : AliceBridgeActions {

    /** The latest poll of the car, fed by [AlicePollingManager]. */
    @Volatile var latestData: DiParsData? = null

    override suspend fun vehicle(command: AliceBridgeCommand): Result<Unit> {
        if (command.action.isEmpty()) return dispatchCommands(listOf(command.rawCommand))
        if (command.action == "vehicle.command") return vehicleText(command.text)
        val vehicleCommand = AliceBridgeCommandTranslator.resolve(command.action, command.value)
            ?: return AliceBridgeRouter.failure(AliceBridgeRouter.UNSUPPORTED_ACTION)
        return dispatchCommands(listOf(vehicleCommand))
    }

    override suspend fun navigation(command: AliceBridgeCommand): Result<Unit> =
        AliceBridgeRouter.failure(AliceBridgeRouter.UNSUPPORTED_ACTION)

    override suspend fun app(command: AliceBridgeCommand): Result<Unit> =
        AliceBridgeRouter.failure(AliceBridgeRouter.UNSUPPORTED_ACTION)

    override suspend fun media(command: AliceBridgeCommand): Result<Unit> =
        AliceBridgeRouter.failure(AliceBridgeRouter.UNSUPPORTED_ACTION)

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
    }
}
