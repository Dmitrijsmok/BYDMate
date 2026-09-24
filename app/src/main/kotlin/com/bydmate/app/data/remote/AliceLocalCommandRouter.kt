package com.bydmate.app.data.remote

import org.json.JSONObject

/**
 * Pure text/domain routing shared by the Alice bridge. It never executes vehicle writes and never
 * calls an LLM; execution remains in AlicePollingManager/ActionDispatcher where safety gates live.
 */
object AliceLocalCommandRouter {
    private val disabledNavigationActions = setOf(
        "navigation.route",
        "navigation.search",
        "navigation.show",
        "navigation.cluster_on",
        "navigation.cluster_off",
        "app.navigation.open",
        "app.waze.open",
        "app.yandex_navi.open",
        "app.yandex_maps.open",
        "app.google_maps.open",
        "app.dgis.open",
    )

    private val automotiveQueryMarkers = listOf(
        "автомоб", "машин", "byd", "atto", "seal", "dolphin", "leopard", "tang", "han",
        "song", "sealion", "электромоб", "батар", "заряд", "расход", "пробег", "запас хода",
        "шина", "давлен", "колес", "климат", "кондиц", "сиден", "стекл", "окн", "люк",
        "штор", "багаж", "капот", "двер", "замок", "фара", "мотор", "двигател", "инвертор",
        "прибор", "панел", "рекуперац", "зарядк", "холодильник",
        "аварийн", "аварийк", "дхо", "ходов", "frunk",
    )

    fun isNavigationAction(action: String): Boolean = action in disabledNavigationActions

    fun commandText(json: JSONObject): String =
        json.optString("text").trim().ifEmpty { json.optString("prompt").trim() }

    fun isAutomotiveAgentQuery(prompt: String): Boolean {
        val normalized = normalizeAliceText(prompt)
        return normalized.isNotEmpty() && automotiveQueryMarkers.any(normalized::contains)
    }

    fun directVehicleCommand(text: String): String? =
        AliceVehicleCommandMatcher.match(normalizeAliceText(text))
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
        if (aliceContainsAny(
                value,
                "нагрев",
                "нагре",
                "подогрев",
                "подогре",
                "греть",
                "тепл",
                "heat",
            )
        ) {
            return temperature?.coerceIn(35, 50)?.let { "冰箱制热${it}度" } ?: "冰箱制热"
        }
        if (aliceContainsAny(value, "охлаж", "охлад", "холод", "мороз", "cool") ||
            isEnable(value)
        ) {
            return temperature?.coerceIn(-6, 6)?.let { "冰箱制冷${it}度" } ?: "冰箱制冷"
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
        value,
        "включ",
        "открой",
        "открыть",
        "запусти",
        "запри",
        "заблокируй",
        "enable",
        "open",
        "lock",
    )

    private fun isDisable(value: String): Boolean = aliceContainsAny(
        value,
        "выключ",
        "закрой",
        "закрыть",
        "отключ",
        "отопри",
        "разблокируй",
        "disable",
        "close",
        "unlock",
        "off",
    )
}

private fun aliceContainsAny(value: String, vararg markers: String): Boolean =
    markers.any(value::contains)

private fun normalizeAliceText(value: String): String =
    value.trim().lowercase().replace('ё', 'е')
