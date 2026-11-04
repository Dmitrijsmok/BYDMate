package com.bydmate.app.data.remote

import com.bydmate.app.voice.NluParser
import com.bydmate.app.voice.ParseResult

/** What a free-text `vehicle.command` from Alice turns into, decided without an LLM. */
internal sealed interface AliceTextPlan {
    /** Vehicle command strings, run one after the other through ActionDispatcher. */
    data class Commands(val commands: List<String>) : AliceTextPlan

    /** A media_volume payload. */
    data class Volume(val payload: String) : AliceTextPlan

    /** Open a navigation app (a RouteNavigatorUris id; null = the app chosen in settings). */
    data class OpenNavigator(val app: String?) : AliceTextPlan

    data class Failed(val reason: String) : AliceTextPlan
}

/**
 * Pure text/domain routing of the Alice bridge. It never executes anything and never calls an
 * LLM; execution stays in [AliceBridgeExecutor] / ActionDispatcher, where the safety gates live.
 */
internal object AliceLocalCommandRouter {
    private const val TEMP_MIN = 16
    private const val TEMP_MAX = 33

    private val navigationTextActions = setOf(
        "navigation.route",
        "navigation.search",
        "navigation.show",
    )

    private val automotiveQueryMarkers = listOf(
        "автомоб", "машин", "byd", "atto", "seal", "dolphin", "leopard", "tang", "han",
        "song", "sealion", "электромоб", "батар", "заряд", "расход", "пробег", "запас хода",
        "шина", "давлен", "колес", "климат", "кондиц", "сиден", "стекл", "окн", "люк",
        "штор", "багаж", "капот", "двер", "замок", "фара", "мотор", "двигател", "инвертор",
        "прибор", "панел", "рекуперац", "маршрут", "навигац", "зарядк", "холодильник",
        "аварийн", "аварийк", "дхо", "ходов", "frunk",
    )

    fun isNavigationAction(action: String): Boolean = action in navigationTextActions

    /** The BYDMate agent answers questions about the car only; the rest stays with Alice. */
    fun isAutomotiveAgentQuery(prompt: String): Boolean {
        val normalized = normalizeAliceText(prompt)
        return normalized.isNotEmpty() && automotiveQueryMarkers.any(normalized::contains)
    }

    fun directVehicleCommand(text: String): String? =
        AliceVehicleCommandMatcher.match(normalizeAliceText(text))

    /**
     * [text] as Alice heard it: first the few phrases the offline dictionary does not carry
     * (frunk, hazard lights, DRL, rear defrost, fridge, doors), then the offline voice dictionary
     * itself, exactly as the local assistant parses it. [acTemp] is the current set temperature
     * for «теплее» / «холоднее».
     */
    fun planVehicleText(text: String, acTemp: Int?): AliceTextPlan {
        if (text.isBlank()) return AliceTextPlan.Failed("missing_vehicle_command")
        directVehicleCommand(text)?.let { return AliceTextPlan.Commands(listOf(it)) }
        return when (val parsed = NluParser.parse(text)) {
            is ParseResult.Command -> AliceTextPlan.Commands(parsed.commands)
            is ParseResult.RelativeTemp -> acTemp
                ?.let { AliceTextPlan.Commands(listOf("设置温度" + (it + parsed.sign).coerceIn(TEMP_MIN, TEMP_MAX))) }
                ?: AliceTextPlan.Failed("ac_temperature_unknown")
            is ParseResult.Volume -> AliceTextPlan.Volume(parsed.payload)
            is ParseResult.Navigator -> AliceTextPlan.OpenNavigator(parsed.app)
            is ParseResult.Ask, ParseResult.Music, ParseResult.Unrecognized ->
                AliceTextPlan.Failed("unsupported_vehicle_command")
        }
    }
}

private object AliceVehicleCommandMatcher {
    fun match(value: String): String? {
        if (value.isEmpty()) return null
        return frontTrunk(value)
            ?: hazard(value)
            ?: drl(value)
            ?: rearDefrost(value)
            ?: fridge(value)
            ?: doors(value)
    }

    private fun frontTrunk(value: String): String? {
        val matches = (value.contains("передн") && value.contains("багаж")) ||
            aliceContainsAny(value, "frunk", "front trunk")
        if (!matches) return null
        return when {
            isDisable(value) -> "前备箱关闭"
            isEnable(value) -> "前备箱打开"
            else -> null
        }
    }

    private fun hazard(value: String): String? {
        if (!aliceContainsAny(value, "аварийк", "аварийн", "hazard")) return null
        return when {
            isDisable(value) -> "双闪关闭"
            isEnable(value) -> "双闪打开"
            else -> null
        }
    }

    private fun drl(value: String): String? {
        if (!aliceContainsAny(value, "дхо", "дневн", "ходов", "daytime", "drl")) return null
        return when {
            isDisable(value) -> "关闭日行灯"
            isEnable(value) -> "打开日行灯"
            else -> null
        }
    }

    private fun rearDefrost(value: String): String? {
        val matches = (value.contains("задн") && value.contains("стекл") &&
            aliceContainsAny(value, "обогрев", "размороз")) || value.contains("rear defrost")
        if (!matches) return null
        return when {
            isDisable(value) -> "关闭后视镜加热"
            isEnable(value) -> "后视镜加热"
            else -> null
        }
    }

    private fun fridge(value: String): String? {
        if (!aliceContainsAny(value, "холодильник", "fridge")) return null
        if (isDisable(value)) return "冰箱关闭"

        val temperature = Regex("""-?\d{1,2}""").find(value)?.value?.toIntOrNull()
        if (aliceContainsAny(value, "нагрев", "нагре", "подогрев", "подогре", "греть", "тепл", "heat")) {
            return temperature?.coerceIn(FRIDGE_HEAT_MIN, FRIDGE_HEAT_MAX)?.let { "冰箱制热${it}度" } ?: "冰箱制热"
        }
        if (aliceContainsAny(value, "охлаж", "охлад", "холод", "мороз", "cool") || isEnable(value)) {
            return temperature?.coerceIn(FRIDGE_COOL_MIN, FRIDGE_COOL_MAX)?.let { "冰箱制冷${it}度" } ?: "冰箱制冷"
        }
        return null
    }

    private fun doors(value: String): String? {
        if (!aliceContainsAny(value, "двер", "замок", "doors", "lock")) return null
        return when {
            aliceContainsAny(value, "отопри", "разблок", "открой", "unlock") -> "车门解锁"
            aliceContainsAny(value, "запри", "заблок", "закрой", "lock") -> "车门上锁"
            else -> null
        }
    }

    private fun isEnable(value: String): Boolean = aliceContainsAny(
        value, "включ", "открой", "открыть", "запусти", "запри", "заблокируй", "enable", "open", "lock",
    )

    private fun isDisable(value: String): Boolean = aliceContainsAny(
        value, "выключ", "закрой", "закрыть", "отключ", "отопри", "разблокируй", "disable", "close", "unlock", "off",
    )

    private const val FRIDGE_HEAT_MIN = 35
    private const val FRIDGE_HEAT_MAX = 50
    private const val FRIDGE_COOL_MIN = -6
    private const val FRIDGE_COOL_MAX = 6
}

private fun aliceContainsAny(value: String, vararg markers: String): Boolean =
    markers.any(value::contains)

private fun normalizeAliceText(value: String): String =
    value.trim().lowercase().replace('ё', 'е')
