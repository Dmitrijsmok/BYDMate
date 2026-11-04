package com.bydmate.app.data.remote

/** The last car state sent to the worker: the temperatures Alice answers from, and how it went. */
data class AliceStateReportSnapshot(
    val attemptedAtMs: Long = 0L,
    val insideTemp: Int? = null,
    val acTemp: Int? = null,
    val exteriorTemp: Int? = null,
    val httpCode: Int? = null,
    val error: String? = null,
)

/**
 * The last command the bridge answered: its action (or raw command), the error (null = done), and
 * where its age came from (AliceCommandTtl.AgeSource label) with the age itself.
 */
data class AliceLastCommand(
    val atMs: Long,
    val action: String,
    val error: String?,
    val ageSource: String? = null,
    val ageMs: Long? = null,
)

/**
 * Field diagnostics of the Alice bridge for Settings and the diagnostic dump: what Alice was last
 * told about the cabin temperatures (a wrong «в салоне 85 градусов» starts here) and what the
 * last command came to. Process memory only.
 */
object AliceBridgeDiagnostics {
    @Volatile var stateReport: AliceStateReportSnapshot = AliceStateReportSnapshot()
        private set

    @Volatile var lastCommand: AliceLastCommand? = null
        private set

    @Volatile var lastPollAtMs: Long = 0L
        private set

    @Volatile var lastPollError: String? = null
        private set

    @Volatile var expiredCount: Int = 0
        private set

    /** This unit's clock minus the worker's, from the last poll answer's `Date` header (±1 s). */
    @Volatile var clockSkewMs: Long? = null
        private set

    fun stateAttempt(data: DiParsData, nowMs: Long = System.currentTimeMillis()) {
        stateReport = AliceStateReportSnapshot(
            attemptedAtMs = nowMs,
            insideTemp = data.insideTemp,
            acTemp = data.acTemp,
            exteriorTemp = data.exteriorTemp,
        )
    }

    fun stateResult(code: Int?, error: String?) {
        stateReport = stateReport.copy(httpCode = code, error = error)
    }

    fun poll(error: String?, nowMs: Long = System.currentTimeMillis()) {
        lastPollAtMs = nowMs
        lastPollError = error
    }

    fun clockSkew(skewMs: Long) {
        clockSkewMs = skewMs
    }

    fun command(
        action: String,
        error: String?,
        ageSource: String? = null,
        ageMs: Long? = null,
        nowMs: Long = System.currentTimeMillis(),
    ) {
        lastCommand = AliceLastCommand(nowMs, action, error, ageSource, ageMs)
        if (error == AliceCommandTtl.EXPIRED) expiredCount++
    }

    /** One line for the diagnostic dump. */
    fun dumpLine(nowMs: Long = System.currentTimeMillis()): String {
        fun age(at: Long) = if (at > 0L) "${(nowMs - at) / 1000L}s" else "-"
        val report = stateReport
        val last = lastCommand
        return "poll_age=${age(lastPollAtMs)} poll_error=${lastPollError ?: "-"} " +
            "state_age=${age(report.attemptedAtMs)} insideTemp=${report.insideTemp} acTemp=${report.acTemp} " +
            "exteriorTemp=${report.exteriorTemp} state_http=${report.httpCode ?: "-"} state_error=${report.error ?: "-"} " +
            "last_command=${last?.let { "${it.action}:${it.error ?: "ok"}@${age(it.atMs)}" } ?: "-"} " +
            "age_source=${last?.ageSource ?: "-"} command_age=${last?.ageMs?.let { "${it}ms" } ?: "-"} " +
            "clock_skew=${clockSkewMs?.let { "${it / 1000L}s" } ?: "-"} expired=$expiredCount"
    }
}
