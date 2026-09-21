package com.bydmate.app.voice

/** Maps local voice window commands to the same closed-loop position controller Alice uses.
 *  This is intentionally separate from CommandTranslator: on DiLink 3 a raw percentage write can
 *  be accepted without landing at the requested aperture, while the closed-loop controller reads
 *  the pane and falls back to open/close + stop when needed. */
internal object VoiceWindowPositionRouter {
    data class Request(val action: String, val target: Int)

    private const val VENT_PERCENT = 10
    private const val HALF_PERCENT = 50

    private val all = listOf(
        "window.driver.position",
        "window.passenger.position",
        "window.rear_left.position",
        "window.rear_right.position",
    )
    private val front = all.take(2)
    private val rear = all.drop(2)

    fun resolve(command: String): List<Request>? {
        aggregate(command)?.let { return it }
        individualDetent(command)?.let { return listOf(it) }
        return explicitPercent(command)?.let(::listOf)
    }

    private fun aggregate(command: String): List<Request>? = when (command) {
        "车窗通风" -> requests(all, VENT_PERCENT)
        "车窗半开" -> requests(all, HALF_PERCENT)
        "前排车窗通风" -> requests(front, VENT_PERCENT)
        "前排车窗半开" -> requests(front, HALF_PERCENT)
        "后排车窗通风" -> requests(rear, VENT_PERCENT)
        "后排车窗半开" -> requests(rear, HALF_PERCENT)
        else -> null
    }

    private fun individualDetent(command: String): Request? {
        val target = when {
            command.endsWith("通风") -> VENT_PERCENT
            command.endsWith("半开") -> HALF_PERCENT
            else -> return null
        }
        val prefix = command.removeSuffix(if (target == VENT_PERCENT) "通风" else "半开")
        return actionForPrefix(prefix)?.let { Request(it, target) }
    }

    private fun explicitPercent(command: String): Request? {
        val match = PERCENT.matchEntire(command) ?: return null
        val target = match.groupValues[2].toIntOrNull()?.takeIf { it in 1..99 } ?: return null
        return actionForPrefix(match.groupValues[1])?.let { Request(it, target) }
    }

    private fun actionForPrefix(prefix: String): String? = when (prefix) {
        "主驾" -> "window.driver.position"
        "副驾" -> "window.passenger.position"
        "后左" -> "window.rear_left.position"
        "后右" -> "window.rear_right.position"
        else -> null
    }

    private fun requests(actions: List<String>, target: Int): List<Request> =
        actions.map { Request(it, target) }

    private val PERCENT = Regex("""(主驾|副驾|后左|后右)打开(\d{1,2})""")
}
