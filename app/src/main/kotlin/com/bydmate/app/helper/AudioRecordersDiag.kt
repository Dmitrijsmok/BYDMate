package com.bydmate.app.helper

/**
 * Who records from the microphone right now, out of `dumpsys audio` (read by the daemon, which
 * runs as shell): the RecordActivityMonitor section lists every active recording client with its
 * uid / package, its audio source and whether Android silences it. Pure, so it is tested without
 * a device. Field 1.1.x: another app (Overdrive's assistant) held the mic and BYDMate heard only
 * digital silence; this names the holder instead of guessing.
 */
object AudioRecordersDiag {
    private const val MAX_LINES = 20
    private const val MAX_LINE = 220
    private val HEADER = Regex("RecordActivityMonitor", RegexOption.IGNORE_CASE)
    private val CLIENT_HINT = Regex("(session|uid|pack|silenced|source)", RegexOption.IGNORE_CASE)

    fun parse(dump: String): List<String> {
        val lines = dump.lines()
        val start = lines.indexOfFirst { HEADER.containsMatchIn(it) }
        val section = if (start >= 0) {
            lines.drop(start + 1)
                .takeWhile { it.isBlank() || it.first().isWhitespace() }
                .filter { it.isNotBlank() && CLIENT_HINT.containsMatchIn(it) }
        } else {
            lines.filter { it.contains("silenced", ignoreCase = true) }
        }
        return section.map { it.trim().take(MAX_LINE) }.take(MAX_LINES)
    }

    private val PACKAGE = Regex("""pack(?:age)?\s*[:=]\s*([A-Za-z][\w.]*)""")
    private val ACTIVE = Regex("""silenced\s*[:=]\s*false""", RegexOption.IGNORE_CASE)

    /** Other apps' packages in [lines] ([parse] output), the ones Android lets record first:
     *  a client that is not silenced is the one holding the mic. Our own package is skipped. */
    fun holderPackages(lines: List<String>, ownPackage: String): List<String> =
        lines.sortedByDescending { ACTIVE.containsMatchIn(it) }
            .mapNotNull { PACKAGE.find(it)?.groupValues?.get(1) }
            .filter { it != ownPackage }
            .distinct()
}
