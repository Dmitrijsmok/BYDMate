package com.bydmate.app.data.remote

import org.json.JSONObject

/**
 * Narrow semantic command surface for the Alice/Yandex bridge.
 *
 * The cloud side never gets access to raw BYD dev/fid/value writes.  It sends one of
 * the actions below; this object translates it to BYDMate's already validated internal
 * command vocabulary, which is then resolved by CommandTranslator and WriteAllowlist.
 *
 * 5.0 intentionally exposes comfort-only controls.  Windows, locks, trunks and sunroof
 * are deliberately absent from this table and therefore fail closed.
 */
object AliceBridgeCommandTranslator {
    data class Resolved(
        val action: String,
        val vehicleCommand: String,
    )

    fun resolve(json: JSONObject): Resolved? {
        val action = json.optString("action").trim().lowercase()
        if (action.isBlank()) return null

        val command = when (action) {
            "climate.on" -> "自动空调"
            "climate.off" -> "关闭空调"
            "climate.auto_on" -> "空调自动"
            "climate.auto_off" -> "空调手动"
            "climate.recirculation_inner" -> "内循环"
            "climate.recirculation_outer" -> "外循环"
            "climate.rear_defrost_on" -> "后视镜加热"
            "climate.rear_defrost_off" -> "关闭后视镜加热"

            "climate.temperature" -> {
                val value = json.intValueOrNull() ?: return null
                if (value !in 16..30) return null
                "设置温度${value}"
            }

            "seat.driver.heat" -> seatCommand("主驾座椅加热", json) ?: return null
            "seat.passenger.heat" -> seatCommand("副驾座椅加热", json) ?: return null
            "seat.driver.vent" -> seatCommand("主驾座椅通风", json) ?: return null
            "seat.passenger.vent" -> seatCommand("副驾座椅通风", json) ?: return null

            "light.interior_on" -> "打开车内灯"
            "light.interior_off" -> "关闭车内灯"
            "light.ambient_on" -> "氛围灯打开"
            "light.ambient_off" -> "氛围灯关闭"

            else -> return null
        }
        return Resolved(action, command)
    }

    private fun seatCommand(prefix: String, json: JSONObject): String? {
        val level = json.intValueOrNull() ?: return null
        if (level !in 0..5) return null
        return if (level == 0) "${prefix}关闭" else "${prefix}${level}档"
    }

    private fun JSONObject.intValueOrNull(): Int? {
        if (!has("value") || isNull("value")) return null
        return when (val raw = opt("value")) {
            is Number -> raw.toInt()
            is String -> raw.toIntOrNull()
            else -> null
        }
    }

    val supportedActions: Set<String> = setOf(
        "climate.on",
        "climate.off",
        "climate.auto_on",
        "climate.auto_off",
        "climate.recirculation_inner",
        "climate.recirculation_outer",
        "climate.rear_defrost_on",
        "climate.rear_defrost_off",
        "climate.temperature",
        "seat.driver.heat",
        "seat.passenger.heat",
        "seat.driver.vent",
        "seat.passenger.vent",
        "light.interior_on",
        "light.interior_off",
        "light.ambient_on",
        "light.ambient_off",
    )
}
