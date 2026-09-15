package com.bydmate.app.data.remote

import org.json.JSONObject

/**
 * Narrow semantic command surface for the Alice/Yandex bridge.
 *
 * The cloud side never gets access to raw BYD dev/fid/value writes. It sends one of
 * the actions below; this object translates it to BYDMate's validated internal command
 * vocabulary, which is then resolved by CommandTranslator and WriteAllowlist.
 *
 * 5.0 exposes comfort controls plus the four side windows. Locks, trunks and sunroof
 * remain deliberately absent and therefore fail closed.
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

            // Yandex Smart Home models a window as devices.types.openable. A range/open
            // capability can request 0..100%, so keep the cloud contract semantic and
            // translate percentages to BYDMate's existing per-window vocabulary here.
            "window.driver.open" -> "主驾打开100"
            "window.driver.close" -> "主驾打开0"
            "window.driver.vent" -> "主驾通风"
            "window.driver.position" -> windowPosition("主驾", json) ?: return null

            "window.passenger.open" -> "副驾打开100"
            "window.passenger.close" -> "副驾打开0"
            "window.passenger.vent" -> "副驾通风"
            "window.passenger.position" -> windowPosition("副驾", json) ?: return null

            "window.rear_left.open" -> "后左打开100"
            "window.rear_left.close" -> "后左打开0"
            "window.rear_left.vent" -> "后左通风"
            "window.rear_left.position" -> windowPosition("后左", json) ?: return null

            "window.rear_right.open" -> "后右打开100"
            "window.rear_right.close" -> "后右打开0"
            "window.rear_right.vent" -> "后右通风"
            "window.rear_right.position" -> windowPosition("后右", json) ?: return null

            else -> return null
        }
        return Resolved(action, command)
    }

    private fun seatCommand(prefix: String, json: JSONObject): String? {
        val level = json.intValueOrNull() ?: return null
        if (level !in 0..5) return null
        return if (level == 0) "${prefix}关闭" else "${prefix}${level}档"
    }

    private fun windowPosition(prefix: String, json: JSONObject): String? {
        val percent = json.intValueOrNull() ?: return null
        if (percent !in 0..100) return null
        return "${prefix}打开${percent}"
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
        "window.driver.open",
        "window.driver.close",
        "window.driver.vent",
        "window.driver.position",
        "window.passenger.open",
        "window.passenger.close",
        "window.passenger.vent",
        "window.passenger.position",
        "window.rear_left.open",
        "window.rear_left.close",
        "window.rear_left.vent",
        "window.rear_left.position",
        "window.rear_right.open",
        "window.rear_right.close",
        "window.rear_right.vent",
        "window.rear_right.position",
    )
}
