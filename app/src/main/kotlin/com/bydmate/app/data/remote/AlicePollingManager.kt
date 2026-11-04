package com.bydmate.app.data.remote

import android.os.SystemClock
import android.util.Log
import com.bydmate.app.data.repository.SettingsRepository
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
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/**
 * The car side of the Alice bridge: polls the worker, runs its commands through
 * [AliceBridgeRouter] (the two permissions) and [AliceBridgeExecutor], acks every command with
 * its own result and reports the car state Alice answers from.
 *
 * Protocol: `GET /api/poll?wait_ms=…` long-polls the reference worker; upstream's worker answers
 * at once and gets polled at its old cadence instead. A command older than [AliceCommandTtl] is
 * acked "expired" without running, and a command answered before (its ack got lost) is acked
 * again with the same result instead of running twice. The age never comes from this unit's
 * clock: see [AliceCommandTtl] for the server clocks it is read against (the `Date` header of
 * the poll answer, and for the fork's 5.10 worker, which stamps nothing, its `/api/debug`).
 */
@Singleton
class AlicePollingManager @Inject constructor(
    httpClient: OkHttpClient,
    private val settingsRepository: SettingsRepository,
    private val sharedAdaptiveLoop: com.bydmate.app.data.loop.SharedAdaptiveLoop,
    private val executor: AliceBridgeExecutor,
) {
    companion object {
        private const val TAG = "AlicePolling"
        private const val LONG_POLL_MS = 2_000L
        /** Upstream's polling cadence, kept for a worker that does not hold the request. */
        private const val PLAIN_POLL_INTERVAL_MS = 2_500L
        private const val IDLE_DELAY_MS = 100L
        private const val ERROR_DELAY_MS = 1_000L
        private const val STATE_REPORT_INTERVAL_MS = 20_000L
        private const val ANSWERED_MEMORY = 128
    }

    // Short timeouts for polling (the shared client has 15 s); the read covers the long poll.
    private val client = httpClient.newBuilder()
        .connectTimeout(3, TimeUnit.SECONDS)
        .readTimeout(LONG_POLL_MS + 2_000L, TimeUnit.MILLISECONDS)
        .writeTimeout(3, TimeUnit.SECONDS)
        .build()

    private val ttl = AliceCommandTtl(monotonicMs = SystemClock::elapsedRealtime, wallMs = System::currentTimeMillis)
    private val answered = object : LinkedHashMap<String, AliceAckResult>() {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, AliceAckResult>?) =
            size > ANSWERED_MEMORY
    }

    private var scope: CoroutineScope? = null
    private var pollingJob: Job? = null
    private var lastStateReportAtMs = 0L

    // Set by TrackingService from the shared poll as well; the executor answers from it.
    @Volatile var latestData: DiParsData? = null
        set(value) {
            field = value
            executor.latestData = value
        }

    fun start() {
        if (pollingJob?.isActive == true) return
        val s = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        scope = s
        ttl.reset()
        // Alice's own subscription to the shared loop, so it does not depend on TrackingService
        // writing latestData on every tick.
        s.launch {
            sharedAdaptiveLoop.flow.collect { data -> latestData = data }
        }
        pollingJob = s.launch {
            Log.i(TAG, "Polling started")
            while (true) {
                val pause = try {
                    poll()
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    Log.e(TAG, "Poll error: ${e.javaClass.simpleName}")
                    AliceBridgeDiagnostics.poll(e.javaClass.simpleName)
                    ERROR_DELAY_MS
                }
                delay(pause)
            }
        }
    }

    fun stop() {
        pollingJob?.cancel()
        pollingJob = null
        scope?.cancel()
        scope = null
        ttl.reset()
        Log.i(TAG, "Polling stopped")
    }

    val isRunning: Boolean get() = pollingJob?.isActive == true

    /** One poll round; returns how long to wait before the next one. */
    private suspend fun poll(): Long {
        val endpoint = settingsRepository.getString(SettingsRepository.KEY_ALICE_ENDPOINT, "").trim().trimEnd('/')
        val apiKey = settingsRepository.getString(SettingsRepository.KEY_ALICE_API_KEY, "").trim()
        if (endpoint.isBlank() || apiKey.isBlank()) return PLAIN_POLL_INTERVAL_MS

        val request = Request.Builder()
            .url("$endpoint/api/poll?wait_ms=$LONG_POLL_MS")
            .header("X-Api-Key", apiKey)
            .build()
        val t0 = SystemClock.elapsedRealtime()
        var dateMs: Long? = null
        val body = client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                Log.w(TAG, "Poll HTTP ${response.code}")
                AliceBridgeDiagnostics.poll("http_${response.code}")
                return ERROR_DELAY_MS
            }
            dateMs = response.dateMs()
            response.body?.string()
        }
        val elapsed = SystemClock.elapsedRealtime() - t0
        val batch = body?.let(AliceBridgeProtocol::parsePoll) ?: run {
            AliceBridgeDiagnostics.poll("bad_response")
            return ERROR_DELAY_MS
        }
        AliceBridgeDiagnostics.poll(null)
        // Every answer, empty ones included: it bounds the age of the next unstamped command.
        val window = ttl.onResponse(batch.serverTimeMs, dateMs)
        window.clockSkewMs?.let(AliceBridgeDiagnostics::clockSkew)

        if (batch.commands.isNotEmpty()) {
            Log.i(TAG, "Received ${batch.commands.size} command(s) (${elapsed}ms)")
            if (batch.commands.any { it.id !in answered && window.needsLookup(it) }) {
                window.lookup = lookup(endpoint, apiKey)
            }
            val results = answer(batch.commands, window)
            ack(endpoint, apiKey, results)
        }
        maybeReportState(endpoint, apiKey)

        // An empty answer well before the long-poll window ran out: the worker does not hold the
        // request (upstream's), so poll it at its own cadence rather than ten times a second.
        return if (batch.commands.isEmpty() && elapsed < LONG_POLL_MS / 2) PLAIN_POLL_INTERVAL_MS - elapsed
        else IDLE_DELAY_MS
    }

    private suspend fun answer(commands: List<AliceBridgeCommand>, window: AliceCommandTtl.Batch): List<AliceAckResult> {
        val permissions = AliceBridgePermissions(
            vehicleControl = settingsRepository.getString(SettingsRepository.KEY_ALICE_VEHICLE_CONTROL, "false") == "true",
            navigation = settingsRepository.getString(SettingsRepository.KEY_ALICE_NAVIGATION, "false") == "true",
        )
        return commands.map { command ->
            answered[command.id] ?: run {
                val label = command.action.ifEmpty { command.rawCommand }
                val age = window.age(command)
                val result = if (window.isExpired(command)) {
                    Log.w(TAG, "Expired: '$label' (id=${command.id}, age=${age.ms ?: "unknown"}ms " +
                        "source=${age.source.label})")
                    AliceAckResult(command.id, false, AliceCommandTtl.EXPIRED)
                } else {
                    execute(command, permissions)
                }
                Log.i(TAG, "Result: '$label' -> ${result.error ?: "OK"} (age=${age.ms ?: "unknown"}ms " +
                    "source=${age.source.label})")
                AliceBridgeDiagnostics.command(label, result.error, age.source.label, age.ms)
                answered[command.id] = result
                result
            }
        }
    }

    /**
     * The worker's own record of when its commands were queued, for commands whose age nothing in
     * the poll answer bounds: the fork worker (5.10–5.12) sends no timestamp with a command but
     * lists `created_at` in `/api/debug`, read here against that answer's `Date` header (or its
     * `server_time` when it has one). Null when the worker has no such endpoint (upstream's) or
     * gives no server clock: the commands then stay of unknown age and expire.
     */
    private fun lookup(endpoint: String, apiKey: String): AliceCommandTtl.Lookup? = runCatching {
        val request = Request.Builder().url("$endpoint/api/debug").header("X-Api-Key", apiKey).build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return@use null
            val date = response.dateMs()
            val body = response.body?.string() ?: return@use null
            val created = AliceBridgeProtocol.parseDebugCreatedAt(body) ?: return@use null
            val serverNow = runCatching { JSONObject(body).optLong("server_time", 0L) }.getOrDefault(0L)
                .takeIf { it > 0L }
            when {
                serverNow != null -> AliceCommandTtl.Lookup(created, serverNow, SystemClock.elapsedRealtime())
                date != null -> ttl.lookupOf(created, date)
                else -> null
            }
        }
    }.onFailure { Log.w(TAG, "Command age lookup failed: ${it.javaClass.simpleName}") }.getOrNull()
        .also { Log.i(TAG, "Command age lookup: ${if (it == null) "unavailable" else "${it.createdAtMs.size} entries"}") }

    /** The response's HTTP `Date` in ms, or null when it has none. */
    private fun okhttp3.Response.dateMs(): Long? = headers.getDate("Date")?.time

    private suspend fun execute(command: AliceBridgeCommand, permissions: AliceBridgePermissions): AliceAckResult {
        // A throw is this command's failure, not the poll loop's: the rest of the batch still runs.
        val result = runCatching { AliceBridgeRouter.execute(command, permissions, executor) }
            .onFailure { if (it is CancellationException) throw it }
            .getOrElse {
                Log.e(TAG, "Command '${command.action}' threw ${it.javaClass.simpleName}")
                AliceBridgeRouter.failure(it.javaClass.simpleName)
            }
        val error = result.exceptionOrNull()?.let { it.message ?: it.javaClass.simpleName }
        return AliceAckResult(command.id, result.isSuccess, error)
    }

    private fun maybeReportState(endpoint: String, apiKey: String) {
        val now = SystemClock.elapsedRealtime()
        if (lastStateReportAtMs != 0L && now - lastStateReportAtMs < STATE_REPORT_INTERVAL_MS) return
        val data = latestData ?: return
        lastStateReportAtMs = now
        AliceBridgeDiagnostics.stateAttempt(data)
        runCatching {
            post(endpoint, apiKey, "state", AliceBridgeProtocol.stateBody(data)) { code ->
                AliceBridgeDiagnostics.stateResult(code, null)
            }
        }.onFailure {
            Log.e(TAG, "State report failed: ${it.javaClass.simpleName}")
            AliceBridgeDiagnostics.stateResult(null, it.javaClass.simpleName)
        }
    }

    private fun ack(endpoint: String, apiKey: String, results: List<AliceAckResult>) {
        runCatching { post(endpoint, apiKey, "ack", AliceBridgeProtocol.ackBody(results)) {} }
            .onSuccess { Log.i(TAG, "Acked ${results.size} command(s)") }
            .onFailure { Log.e(TAG, "Ack failed: ${it.javaClass.simpleName}") }
    }

    private fun post(endpoint: String, apiKey: String, path: String, body: JSONObject, onCode: (Int) -> Unit) {
        val request = Request.Builder()
            .url("$endpoint/api/$path")
            .header("X-Api-Key", apiKey)
            .post(body.toString().toRequestBody("application/json".toMediaType()))
            .build()
        client.newCall(request).execute().use { onCode(it.code) }
    }
}
