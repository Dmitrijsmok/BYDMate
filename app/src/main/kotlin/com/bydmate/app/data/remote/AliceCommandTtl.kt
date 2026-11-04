package com.bydmate.app.data.remote

/**
 * Age limit of Alice bridge commands. Alice answers «готово» as soon as the worker queued the
 * command, so a car that was offline would otherwise run it whenever it comes back — a window
 * opened hours after it was asked for. Anything older than [ttlMs] is not run; the poll loop acks
 * it with [EXPIRED].
 *
 * The age is never read off this unit's own clock (head unit clocks drift by minutes). In order:
 * - `age_ms` of the command (reference worker 5.13+): the server's own subtraction;
 * - `created_at` against the response's `server_time` (5.13+), else against the response's HTTP
 *   `Date` header (any worker behind Cloudflare or nginx; whole seconds, so up to 1 s too old);
 * - no timestamp at all (the fork's deployed worker 5.10–5.12, upstream's worker): the command was
 *   queued after the previous poll answer, so it is at most the time since that answer
 *   ([AgeSource.POLL_BOUND]), as long as that bound is inside the limit;
 * - otherwise (the first answer after the polling started, or a long outage before this answer)
 *   the worker's own record: [Lookup], the `created_at` of `/api/debug` read against that
 *   answer's `Date` header;
 * - nothing of that: unknown, and treated as expired.
 *
 * Pure: both clocks are injected; [wallMs] only measures the skew for the diagnostics.
 */
internal class AliceCommandTtl(
    private val ttlMs: Long = DEFAULT_TTL_MS,
    private val monotonicMs: () -> Long,
    private val wallMs: () -> Long,
) {
    /** Where an age came from, as the diagnostic dump prints it. */
    enum class AgeSource(val label: String) {
        AGE_MS("age_ms"),
        SERVER_TIME("server_time"),
        DATE_HEADER("date_header"),
        POLL_BOUND("poll_bound"),
        LOOKUP("debug_lookup"),
        UNKNOWN("unknown"),
    }

    /** One command's age in ms (null = unknown) and its source. */
    data class Age(val ms: Long?, val source: AgeSource)

    /**
     * The worker's own record of when commands were queued: [createdAtMs] by command id and the
     * server clock of that answer ([serverNowMs], from its `Date` header), received at
     * [receivedAtMonoMs] on [monotonicMs].
     */
    class Lookup(val createdAtMs: Map<String, Long>, val serverNowMs: Long, val receivedAtMonoMs: Long)

    @Volatile private var lastResponseAtMs: Long? = null

    /** Forget the previous answer: called when the polling starts or stops. */
    fun reset() {
        lastResponseAtMs = null
    }

    /**
     * Opens one poll response; call exactly once per successful response, before its commands.
     * [serverTimeMs] is the response's `server_time`, [dateMs] its HTTP `Date` header.
     */
    fun onResponse(serverTimeMs: Long?, dateMs: Long? = null): Batch {
        val now = monotonicMs()
        val bound = lastResponseAtMs?.let { now - it }
        lastResponseAtMs = now
        return Batch(now, bound, serverTimeMs, dateMs, dateMs?.let { wallMs() - it })
    }

    /** The server clock a `Date` header stands for: the header has whole seconds, so the upper end. */
    fun lookupOf(createdAtMs: Map<String, Long>, dateMs: Long): Lookup =
        Lookup(createdAtMs, dateMs + DATE_RESOLUTION_MS, monotonicMs())

    /** One response: [isExpired] also counts the time spent on earlier commands of the batch. */
    inner class Batch internal constructor(
        private val receivedAtMs: Long,
        private val unstampedBoundMs: Long?,
        private val serverTimeMs: Long?,
        private val dateMs: Long?,
        /** This unit's clock minus the server's at this answer (from `Date`, ±1 s), or null. */
        val clockSkewMs: Long?,
    ) {
        /** Set by the poll loop when [needsLookup] said so and the worker answered. */
        @Volatile var lookup: Lookup? = null

        fun age(command: AliceBridgeCommand): Age {
            val since = monotonicMs() - receivedAtMs
            command.ageMs?.let { return Age(it.coerceAtLeast(0) + since, AgeSource.AGE_MS) }
            command.createdAtMs?.let { created ->
                serverTimeMs?.let { return Age((it - created).coerceAtLeast(0) + since, AgeSource.SERVER_TIME) }
                dateMs?.let {
                    return Age((it + DATE_RESOLUTION_MS - created).coerceAtLeast(0) + since, AgeSource.DATE_HEADER)
                }
            }
            val bound = unstampedBoundMs?.let { it + since }
            if (bound != null && bound <= ttlMs) return Age(bound, AgeSource.POLL_BOUND)
            lookup?.let { l ->
                l.createdAtMs[command.id]?.let { created ->
                    val age = (l.serverNowMs - created).coerceAtLeast(0) + (monotonicMs() - l.receivedAtMonoMs)
                    return Age(age, AgeSource.LOOKUP)
                }
            }
            return if (bound != null) Age(bound, AgeSource.POLL_BOUND) else Age(null, AgeSource.UNKNOWN)
        }

        fun ageMs(command: AliceBridgeCommand): Long? = age(command).ms

        fun isExpired(command: AliceBridgeCommand): Boolean = ageMs(command)?.let { it > ttlMs } ?: true

        /** True when nothing in this answer can show [command] is young enough: the worker's
         *  own record is the last chance before it expires. */
        fun needsLookup(command: AliceBridgeCommand): Boolean {
            val age = age(command)
            return age.source == AgeSource.UNKNOWN || (age.source == AgeSource.POLL_BOUND && isExpired(command))
        }
    }

    companion object {
        /** Long enough for a slow mobile network, short enough that nobody expects it any more. */
        const val DEFAULT_TTL_MS = 30_000L
        const val EXPIRED = "expired"
        /** An HTTP `Date` has whole seconds. */
        const val DATE_RESOLUTION_MS = 999L
    }
}
