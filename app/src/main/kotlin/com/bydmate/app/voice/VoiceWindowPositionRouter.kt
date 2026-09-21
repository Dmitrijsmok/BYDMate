package com.bydmate.app.voice

/** Maps individual local voice window-position commands to the same closed-loop controller Alice
 *  uses. Aggregate detents (all/front/rear half or vent) deliberately stay OUT of this router:
 *  VehicleApi's composite path fans those panes out as one burst with its Song L-safe stagger and
 *  shared verification, so "all windows" starts every pane together instead of waiting for each
 *  closed-loop move to finish before starting the next one. */
internal object VoiceWindowPositionRouter {
    data class Request(val action: String, val target: Int)

    private const val VENT_PERCENT = 10
    private const val HALF_PERCENT = 50

    private val aggregateDetents = setOf(
        "车窗通风",
        "车窗半开",
        "前排车窗通风",
        "前排车窗半开",
        "后排车窗通风",
        "后排车窗半开",
    )

    fun resolve(command: String): List<Request>? {
        if (command in aggregateDetents) return null
        individualDetent(command)?.let { return listOf(it) }
        return explicitPercent(command)?.let(::listOf)
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

    private val PERCENT = Regex("""(主驾|副驾|后左|后右)打开(\d{1,2})""")
}
