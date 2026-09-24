package com.bydmate.app.data.remote

import com.bydmate.app.agent.AgentTools
import com.bydmate.app.data.automation.ActionDispatcher
import com.bydmate.app.data.local.entity.ActionDef
import com.bydmate.app.data.repository.SettingsRepository
import com.bydmate.app.data.vehicle.VehicleApi
import com.bydmate.app.voice.NluParser
import com.bydmate.app.voice.ParseResult
import com.bydmate.app.voice.VoiceLang
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AlicePollingManager @Inject constructor(
    private val settingsRepository: SettingsRepository,
    private val sharedAdaptiveLoop: com.bydmate.app.data.loop.SharedAdaptiveLoop,
    private val vehicleApi: VehicleApi,
    private val actionDispatcher: ActionDispatcher,
    private val appDispatcher: AliceAppActionDispatcher,
    private val apertureController: AliceApertureController,
) {
    companion object {
        private const val LONG_POLL_MS = 2000
        private const val IDLE_DELAY_MS = 100L
        private const val STATE_REPORT_EVERY = 10
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(3, TimeUnit.SECONDS)
        .readTimeout(4, TimeUnit.SECONDS)
        .writeTimeout(3, TimeUnit.SECONDS)
        .build()

    private var scope: CoroutineScope? = null
    private var pollingJob: Job? = null
    private var pollCount = 0

    @Volatile
    var latestData: DiParsData? = null
        private set

    fun start() {
        if (pollingJob?.isActive == true) return
        val owner = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        scope = owner
        owner.launch {
            sharedAdaptiveLoop.flow.collect {
                latestData = it
                apertureController.latestData = it
            }
        }
        pollingJob = owner.launch {
            while (true) {
                try {
                    poll()
                } catch (e: CancellationException) {
                    throw e
                } catch (_: Exception) {
                    delay(1000L)
                }
                delay(IDLE_DELAY_MS)
            }
        }
    }

    fun stop() {
        pollingJob?.cancel()
        pollingJob = null
        scope?.cancel()
        scope = null
    }

    val isRunning: Boolean
        get() = pollingJob?.isActive == true

    private suspend fun poll() {
        val endpoint = settingsRepository.getString(SettingsRepository.KEY_ALICE_ENDPOINT, "").trimEnd('/')
        val apiKey = settingsRepository.getString(SettingsRepository.KEY_ALICE_API_KEY, "")
        if (endpoint.isBlank() || apiKey.isBlank()) return

        val request = Request.Builder()
            .url("$endpoint/api/poll?wait_ms=$LONG_POLL_MS")
            .header("X-Api-Key", apiKey)
            .build()

        val commands = client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return
            val body = response.body?.string() ?: return
            JSONObject(body).optJSONArray("commands") ?: return
        }

        val results = mutableListOf<AckResult>()
        repeat(commands.length()) { index ->
            commands.optJSONObject(index)?.let { command ->
                processCommand(command)?.let(results::add)
            }
        }

        if (results.isNotEmpty()) ack(endpoint, apiKey, results)

        pollCount++
        if (pollCount >= STATE_REPORT_EVERY) {
            pollCount = 0
            reportState(endpoint, apiKey)
        }
    }

    private suspend fun processCommand(command: JSONObject): AckResult? {
        val id = command.optString("id").takeIf { it.isNotBlank() } ?: return null
        val action = command.optString("action").trim().lowercase()
        val result = execute(command, action)
        return AckResult(id, result.isSuccess, result.exceptionOrNull()?.message?.take(160))
    }

    private suspend fun execute(json: JSONObject, action: String): Result<Unit> {
        when {
            action == "vehicle.command" -> return executeVehicleText(json)
            AliceLocalCommandRouter.isNavigationAction(action) ->
                return Result.failure(UnsupportedOperationException("alice_navigation_disabled"))
            action == "agent.query" -> return executeAutomotiveAgentQuery(
                json = json,
                dispatcher = actionDispatcher,
                data = latestData,
            )
            action == "window.all.vent" -> {
                return executeSemanticVehicleCommand(
                    JSONObject().put("action", "window.all.vent"),
                    latestData,
                    vehicleApi,
                )
            }
            action in windowPositionActions -> {
                val target = json.valueInt()
                    ?: return Result.failure(IllegalArgumentException("invalid_window_position"))
                return apertureController.positionWindow(action, target, latestData?.speed)
            }
            action == "sunroof.position" -> {
                val target = json.valueInt()?.takeIf { it in setOf(0, 50, 100) }
                    ?: return Result.failure(IllegalArgumentException("sunroof_percent_not_supported"))
                return apertureController.positionSunroof(target, latestData)
            }
        }

        appDispatcher.dispatch(json, latestData)?.let { return it }
        return executeSemanticVehicleCommand(json, latestData, vehicleApi)
    }


    private suspend fun executeVehicleText(json: JSONObject): Result<Unit> {
        val text = AliceLocalCommandRouter.commandText(json)
        if (text.isEmpty()) return Result.failure(IllegalArgumentException("missing_vehicle_command"))

        AliceLocalCommandRouter.directVehicleCommand(text)?.let { command ->
            return dispatchAliceVehicleCommands(
                commands = listOf(command),
                dispatcher = actionDispatcher,
                data = latestData,
            )
        }

        val ru = NluParser.parse(text, VoiceLang.RU)
        val parsed = if (ru == ParseResult.Unrecognized) NluParser.parse(text, VoiceLang.EN) else ru
        return when (parsed) {
            is ParseResult.Command -> dispatchAliceVehicleCommands(
                commands = parsed.commands,
                dispatcher = actionDispatcher,
                data = latestData,
            )

            is ParseResult.RelativeTemp -> {
                val current = latestData?.acTemp
                    ?: return Result.failure(IllegalStateException("ac_temperature_unknown"))
                val target = (current + parsed.sign).coerceIn(16, 30)
                val result = actionDispatcher.dispatch(
                    ActionDef(command = "设置温度$target", displayName = "Alice", kind = "param"),
                    latestData,
                )
                if (result.success) Result.success(Unit)
                else Result.failure(IllegalStateException(result.reason ?: "temperature_command_failed"))
            }

            is ParseResult.Volume -> {
                val result = actionDispatcher.dispatch(
                    ActionDef(
                        command = "media_volume",
                        displayName = "Alice",
                        kind = "media_volume",
                        payload = parsed.payload,
                    ),
                    latestData,
                )
                if (result.success) Result.success(Unit)
                else Result.failure(IllegalStateException(result.reason ?: "volume_command_failed"))
            }

            ParseResult.Unrecognized ->
                Result.failure(IllegalArgumentException("unsupported_vehicle_command"))
        }
    }

    private fun reportState(endpoint: String, apiKey: String) {
        val data = latestData ?: return
        val body = JSONObject().apply {
            data.soc?.let { put("soc", it) }
            data.windowFL?.let { put("windowFL", it) }
            data.windowFR?.let { put("windowFR", it) }
            data.windowRL?.let { put("windowRL", it) }
            data.windowRR?.let { put("windowRR", it) }
            data.sunroof?.let { put("sunroof", it) }
            data.trunk?.let { put("trunk", it) }
            data.lockFL?.let { put("lockFL", it) }
            data.acStatus?.let { put("acStatus", it) }
            data.acTemp?.let { put("acTemp", it) }
            data.acCirc?.let { put("acCirc", it) }
            data.fanLevel?.let { put("fanLevel", it) }
            data.acWindMode?.let { put("acWindMode", it) }
            data.insideTemp?.let { put("insideTemp", it) }
            data.exteriorTemp?.let { put("exteriorTemp", it) }
        }

        val request = Request.Builder()
            .url("$endpoint/api/state")
            .header("X-Api-Key", apiKey)
            .post(body.toString().toRequestBody("application/json".toMediaType()))
            .build()
        runCatching { client.newCall(request).execute().close() }
    }

    private fun ack(endpoint: String, apiKey: String, results: List<AckResult>) {
        val body = JSONObject().apply {
            put("ids", JSONArray(results.map { it.id }))
            put("results", JSONArray().apply {
                results.forEach { result ->
                    put(JSONObject().apply {
                        put("id", result.id)
                        put("success", result.success)
                        result.error?.let { put("error", it) }
                    })
                }
            })
        }
        val request = Request.Builder()
            .url("$endpoint/api/ack")
            .header("X-Api-Key", apiKey)
            .post(body.toString().toRequestBody("application/json".toMediaType()))
            .build()
        runCatching { client.newCall(request).execute().close() }
    }

    private data class AckResult(val id: String, val success: Boolean, val error: String?)

    private val windowPositionActions = setOf(
        "window.driver.position",
        "window.passenger.position",
        "window.rear_left.position",
        "window.rear_right.position",
    )
}

private suspend fun dispatchAliceVehicleCommands(
    commands: List<String>,
    dispatcher: ActionDispatcher,
    data: DiParsData?,
): Result<Unit> {
    for (command in commands) {
        val result = dispatcher.dispatch(
            ActionDef(command = command, displayName = "Alice", kind = "param"),
            data,
        )
        if (!result.success) {
            return Result.failure(
                IllegalStateException(result.reason ?: "vehicle_command_failed")
            )
        }
    }
    return Result.success(Unit)
}

private suspend fun executeAutomotiveAgentQuery(
    json: JSONObject,
    dispatcher: ActionDispatcher,
    data: DiParsData?,
): Result<Unit> {
    val prompt = AliceLocalCommandRouter.commandText(json)
    if (prompt.isEmpty()) return Result.failure(IllegalArgumentException("missing_agent_query"))
    if (!AliceLocalCommandRouter.isAutomotiveAgentQuery(prompt)) {
        return Result.failure(IllegalArgumentException("agent_query_outside_automotive_domain"))
    }

    val payload = JSONObject().put("prompt", prompt).toString()
    val result = dispatcher.dispatch(ActionDef("", "Alice", "agent_query", payload), data)
    return if (result.success) Result.success(Unit)
    else Result.failure(IllegalStateException(result.reason ?: "agent_query_failed"))
}

private suspend fun executeSemanticVehicleCommand(
    json: JSONObject,
    data: DiParsData?,
    vehicleApi: VehicleApi,
): Result<Unit> {
    val resolved = AliceBridgeCommandTranslator.resolve(json)
        ?: return Result.failure(IllegalArgumentException("unsupported_action"))

    aliceRearTrunkBlock(resolved.vehicleCommand, data)?.let { return it }
    val blocked = ActionDispatcher.safetyBlockReason(resolved.vehicleCommand, data)
        ?: ActionDispatcher.speedGateBlockReason(resolved.vehicleCommand, data?.speed)
    if (blocked != null) return Result.failure(IllegalStateException(blocked.javaClass.simpleName))

    return vehicleApi.dispatch(resolved.vehicleCommand)
}

private fun aliceRearTrunkBlock(command: String, data: DiParsData?): Result<Unit>? {
    if (!ActionDispatcher.isRearTrunkOpenCommand(command)) return null
    val speed = data?.speed
        ?: return Result.failure(IllegalStateException("rear_trunk_speed_unknown"))
    if (speed != 0) return Result.failure(IllegalStateException("rear_trunk_requires_standstill"))
    return null
}

private fun JSONObject.valueInt(): Int? = when (val value = opt("value")) {
    is Number -> value.toInt()
    is String -> value.toIntOrNull()
    else -> null
}

