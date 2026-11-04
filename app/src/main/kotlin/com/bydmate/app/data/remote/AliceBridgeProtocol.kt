package com.bydmate.app.data.remote

import org.json.JSONArray
import org.json.JSONObject

/**
 * One command the Alice worker handed out. The reference worker (reference/alice-worker) speaks
 * the semantic protocol: [action] plus an optional [value] and free [text] (a phrase, an app name
 * or a JSON navigation payload). Upstream's own worker sends a raw vehicle command string instead
 * ([rawCommand], the `command` field); it stays supported as a fallback.
 *
 * [ageMs] / [createdAtMs] are the server's own view of how old the command is, when it says so.
 */
data class AliceBridgeCommand(
    val id: String,
    val action: String = "",
    val value: Int? = null,
    val text: String = "",
    val rawCommand: String = "",
    val ageMs: Long? = null,
    val createdAtMs: Long? = null,
)

/** One poll response: its commands and the server clock when the response says it. */
internal data class AlicePollBatch(val commands: List<AliceBridgeCommand>, val serverTimeMs: Long?)

/** What the worker is told about one command; [error] null on success. */
internal data class AliceAckResult(val id: String, val success: Boolean, val error: String? = null)

/** Wire format of the bridge: poll body in, ack and state bodies out. Pure. */
internal object AliceBridgeProtocol {

    /** Longest error text sent back to the worker. */
    private const val MAX_ERROR_CHARS = 160

    /** Null when [body] is not a poll response at all; commands without an id are skipped. */
    fun parsePoll(body: String): AlicePollBatch? {
        val json = runCatching { JSONObject(body) }.getOrNull() ?: return null
        val array = json.optJSONArray("commands") ?: return null
        val commands = (0 until array.length()).mapNotNull { array.optJSONObject(it)?.let(::parseCommand) }
        return AlicePollBatch(commands, json.longOrNull("server_time"))
    }

    /**
     * `created_at` by command id from the worker's `/api/debug` answer (fork worker 5.10–5.13:
     * `{"bridge":"5.10",…,"commands":[{"id","action","value","created_at","acked",…}]}`, server
     * milliseconds), or null when [body] is no such answer.
     */
    fun parseDebugCreatedAt(body: String): Map<String, Long>? {
        val json = runCatching { JSONObject(body) }.getOrNull() ?: return null
        val array = json.optJSONArray("commands") ?: return null
        return (0 until array.length()).mapNotNull { i ->
            val entry = array.optJSONObject(i) ?: return@mapNotNull null
            val id = (entry.opt("id") as? String)?.trim()?.takeIf(String::isNotEmpty)
                ?: (entry.opt("id") as? Number)?.toString()
                ?: return@mapNotNull null
            entry.longOrNull("created_at")?.let { id to it }
        }.toMap()
    }

    fun parseCommand(json: JSONObject): AliceBridgeCommand? {
        val id = when (val v = json.opt("id")) {
            is String -> v.trim()
            is Number -> v.toString()
            else -> ""
        }.takeIf(String::isNotEmpty) ?: return null
        return AliceBridgeCommand(
            id = id,
            action = json.stringOrEmpty("action").lowercase(),
            value = json.intOrNull("value"),
            text = json.stringOrEmpty("text").ifEmpty { json.stringOrEmpty("prompt") },
            rawCommand = json.stringOrEmpty("command"),
            ageMs = json.longOrNull("age_ms"),
            createdAtMs = json.longOrNull("created_at"),
        )
    }

    /** Both shapes at once: `ids` for upstream's worker (ack = done), `results` for the reference
     *  worker, which keeps the failure reason for its debug view. */
    fun ackBody(results: List<AliceAckResult>): JSONObject = JSONObject()
        .put("ids", JSONArray(results.map { it.id }))
        .put("results", JSONArray().apply {
            results.forEach { result ->
                put(JSONObject().put("id", result.id).put("success", result.success).apply {
                    result.error?.let { put("error", it.take(MAX_ERROR_CHARS)) }
                })
            }
        })

    /** The car state the worker answers Smart Home queries from. Absent readings are left out. */
    fun stateBody(data: DiParsData): JSONObject = JSONObject().apply {
        listOf(
            "soc" to data.soc,
            "windowFL" to data.windowFL,
            "windowFR" to data.windowFR,
            "windowRL" to data.windowRL,
            "windowRR" to data.windowRR,
            "sunroof" to data.sunroof,
            "trunk" to data.trunk,
            "lockFL" to data.lockFL,
            "acStatus" to data.acStatus,
            "acTemp" to data.acTemp,
            "acCirc" to data.acCirc,
            "fanLevel" to data.fanLevel,
            "acWindMode" to data.acWindMode,
            "insideTemp" to data.insideTemp,
            "exteriorTemp" to data.exteriorTemp,
            // The fork worker (5.10+) answers its auto climate, front defrost, hood, DRL and
            // hazard cards from these.
            "acCtrlMode" to data.acCtrlMode,
            "acDefrostFront" to data.acDefrostFront,
            "hood" to data.hood,
            "drl" to data.drl,
            "turnSignal" to data.turnSignal,
        ).forEach { (key, value) -> value?.let { put(key, it) } }
    }

    /** A JSON null reads as "null" through optString on Android, so only real strings count. */
    private fun JSONObject.stringOrEmpty(key: String): String = (opt(key) as? String)?.trim().orEmpty()

    private fun JSONObject.intOrNull(key: String): Int? = when (val v = opt(key)) {
        is Number -> v.toDouble().takeIf { it.isFinite() }?.toInt()
        is String -> v.trim().toDoubleOrNull()?.takeIf { it.isFinite() }?.toInt()
        else -> null
    }

    private fun JSONObject.longOrNull(key: String): Long? = when (val v = opt(key)) {
        is Number -> v.toLong()
        is String -> v.trim().toLongOrNull()
        else -> null
    }
}
