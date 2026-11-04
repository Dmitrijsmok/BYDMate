package com.bydmate.app.data.remote

/**
 * Age limit of Alice bridge commands. Alice answers «готово» as soon as the worker queued the
 * command, so a car that was offline would otherwise run it whenever it comes back — a window
 * opened hours after it was asked for. Anything older than [ttlMs] is not run; the poll loop acks
 * it with [EXPIRED].
 *
 * The age comes from the server when it says so: `age_ms` (its own clock, no skew), else
 * `created_at` against the response's `server_time`, else against this unit's clock. A command
 * without any timestamp (upstream's worker) was queued after the previous poll answer, so its age
 * is at most the time since that answer; with no answer since the polling (re)started it is
 * unknown and treated as expired. Pure: both clocks are injected.
 */
internal class AliceCommandTtl(
    private val ttlMs: Long = DEFAULT_TTL_MS,
    private val monotonicMs: () -> Long,
    private val wallMs: () -> Long,
) {
    @Volatile private var lastResponseAtMs: Long? = null

    /** Forget the previous answer: called when the polling starts or stops. */
    fun reset() {
        lastResponseAtMs = null
    }

    /** Opens one poll response; call exactly once per successful response, before its commands. */
    fun onResponse(serverTimeMs: Long?): Batch {
        val now = monotonicMs()
        val bound = lastResponseAtMs?.let { now - it }
        lastResponseAtMs = now
        return Batch(now, bound, serverTimeMs)
    }

    /** One response: [isExpired] also counts the time spent on earlier commands of the batch. */
    inner class Batch internal constructor(
        private val receivedAtMs: Long,
        private val unstampedBoundMs: Long?,
        private val serverTimeMs: Long?,
    ) {
        fun ageMs(command: AliceBridgeCommand): Long? {
            val atResponse = command.ageMs
                ?: command.createdAtMs?.let { (serverTimeMs ?: wallMs()) - it }
                ?: unstampedBoundMs
                ?: return null
            return atResponse.coerceAtLeast(0) + (monotonicMs() - receivedAtMs)
        }

        fun isExpired(command: AliceBridgeCommand): Boolean = ageMs(command)?.let { it > ttlMs } ?: true
    }

    companion object {
        /** Long enough for a slow mobile network, short enough that nobody expects it any more. */
        const val DEFAULT_TTL_MS = 30_000L
        const val EXPIRED = "expired"
    }
}
