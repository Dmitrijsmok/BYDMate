package com.bydmate.app.helper

/**
 * Where DiLink keeps the voice-zone / driver-only setting of the stock assistant (field 1.1.8:
 * com.byd.vrassistant is disabled, the owner wants its driver-voice setting without it). The
 * daemon prints `settings list` of the three tables, `getprop` and the assistant's package dump;
 * this keeps only the lines whose key looks voice related, so two dumps (setting on / off) show
 * which key moves. Read-only. Pure, so it is tested without a device.
 */
object VoiceZoneProbe {
    const val SCRIPT =
        "echo '## system'; settings list system; echo '## global'; settings list global; " +
            "echo '## secure'; settings list secure; echo '## props'; getprop; " +
            "echo '## vrassistant'; dumpsys package com.byd.vrassistant"

    private const val MAX_LINES = 120
    private const val MAX_LINE = 200
    private val SECTION = Regex("""^## (\w+)$""")
    private val KEY = Regex(
        """(^|[._\-\[])(vr|voice|zone|mic|wake|wakeup|driver|aec|denoise|noise|asr|speech|soundsource|""" +
            """sound_source|beam|vad|hotword|iflytek|xunfei|cerence|nuance|seat_?pos)""",
        RegexOption.IGNORE_CASE,
    )
    private val PACKAGE_LINE = Regex(
        """(versionName|enabled=|disabledComponents|enabledComponents|^com\.byd\.vrassistant\.\S+$)""",
    )

    fun filter(output: String): List<String> {
        var section = ""
        val out = mutableListOf<String>()
        for (raw in output.lines()) {
            val header = SECTION.find(raw.trim())
            if (header != null) {
                section = header.groupValues[1]
                continue
            }
            val line = raw.trim()
            if (line.isNotEmpty() && keeps(section, line)) out += "$section: $line".take(MAX_LINE)
        }
        return out.take(MAX_LINES)
    }

    private fun keeps(section: String, line: String): Boolean = when (section) {
        "vrassistant" -> PACKAGE_LINE.containsMatchIn(line)
        "props" -> KEY.containsMatchIn(line.substringBefore("]:"))
        "" -> false
        else -> KEY.containsMatchIn(line.substringBefore('='))
    }
}
