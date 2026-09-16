package com.bydmate.app.data.remote

import org.json.JSONObject

/**
 * Semantic command surface for the Alice/Yandex bridge.
 *
 * Cloud callers never receive raw dev/fid/value access. Every public action below
 * maps to BYDMate's internal command vocabulary, which then goes through
 * CommandTranslator, WriteAllowlist and ActionDispatcher safety gates.
 *
 * 5.2 is rebased on upstream BYDMate v3.15.5 and deliberately reuses upstream
 * vehicle command mappings wherever they exist (fan level and airflow included).
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
            // Climate
            "climate.on" -> "自动空调"
            "climate.off" -> "关闭空调"
            "climate.auto_on" -> "空调自动"
            "climate.auto_off" -> "空调手动"
            "climate.recirculation_inner" -> "内循环"
            "climate.recirculation_outer" -> "外循环"
            "climate.rear_defrost_on" -> "后视镜加热"
            "climate.rear_defrost_off" -> "关闭后视镜加热"
            "climate.front_defrost_on" -> "吹前挡"
            "climate.front_defrost_off" -> "关闭吹前挡"
            "climate.flow_only_on" -> "打开空调通风"
            "climate.flow_only_off" -> "关闭空调通风"

            "climate.temperature" -> {
                val value = json.intValueOrNull() ?: return null
                if (value !in 16..30) return null
                "设置温度${value}"
            }

            // Upstream v3.15.5 officially exposes fan levels 1..7 (#201).
            "climate.fan_level" -> {
                val value = json.intValueOrNull() ?: return null
                if (value !in 1..7) return null
                "风量${value}"
            }

            // Upstream v3.15.5 airflow-direction vocabulary (#201).
            "climate.airflow_face" -> "吹面"
            "climate.airflow_face_feet" -> "吹面吹脚"
            "climate.airflow_feet" -> "吹脚"
            "climate.airflow_feet_windshield" -> "吹脚除霜"
            "climate.airflow_windshield" -> "除霜"

            // Seats
            "seat.driver.heat" -> seatCommand("主驾座椅加热", json) ?: return null
            "seat.passenger.heat" -> seatCommand("副驾座椅加热", json) ?: return null
            "seat.driver.vent" -> seatCommand("主驾座椅通风", json) ?: return null
            "seat.passenger.vent" -> seatCommand("副驾座椅通风", json) ?: return null

            // Lights
            "light.interior_on" -> "打开车内灯"
            "light.interior_off" -> "关闭车内灯"
            "light.ambient_on" -> "氛围灯打开"
            "light.ambient_off" -> "氛围灯关闭"
            "light.drl_on" -> "打开日行灯"
            "light.drl_off" -> "关闭日行灯"
            "light.hazard_on" -> "双闪打开"
            "light.hazard_off" -> "双闪关闭"

            // Individual windows
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

            // Aggregate windows
            "window.all.open" -> "车窗全开"
            "window.all.close" -> "车窗关闭"
            "window.all.half" -> "车窗半开"
            "window.all.vent" -> "车窗通风"

            // Locks / trunks
            "doors.lock" -> "车门上锁"
            "doors.unlock" -> "车门解锁"
            "trunk.rear.open" -> "开后备箱"
            "trunk.rear.close" -> "关后备箱"
            "trunk.front.open" -> "前备箱打开"
            "trunk.front.close" -> "前备箱关闭"

            // Roof / shade
            "sunroof.open" -> "天窗打开100"
            "sunroof.close" -> "天窗打开0"
            "sunroof.tilt" -> "天窗打开50"
            "sunroof.vent" -> "天窗通风"
            "sunroof.comfort" -> "天窗舒适打开"
            "sunroof.stop" -> "天窗停止"
            "sunshade.open" -> "遮阳帘打开"
            "sunshade.close" -> "遮阳帘关闭"

            // Fridge
            "fridge.cool" -> "冰箱制冷"
            "fridge.heat" -> "冰箱制热"
            "fridge.off" -> "冰箱关闭"
            "fridge.cool_temperature" -> {
                val value = json.intValueOrNull() ?: return null
                if (value !in -6..6) return null
                "冰箱制冷${value}度"
            }
            "fridge.heat_temperature" -> {
                val value = json.intValueOrNull() ?: return null
                if (value !in 35..50) return null
                "冰箱制热${value}度"
            }

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
        "climate.front_defrost_on",
        "climate.front_defrost_off",
        "climate.flow_only_on",
        "climate.flow_only_off",
        "climate.temperature",
        "climate.fan_level",
        "climate.airflow_face",
        "climate.airflow_face_feet",
        "climate.airflow_feet",
        "climate.airflow_feet_windshield",
        "climate.airflow_windshield",

        "seat.driver.heat",
        "seat.passenger.heat",
        "seat.driver.vent",
        "seat.passenger.vent",

        "light.interior_on",
        "light.interior_off",
        "light.ambient_on",
        "light.ambient_off",
        "light.drl_on",
        "light.drl_off",
        "light.hazard_on",
        "light.hazard_off",

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
        "window.all.open",
        "window.all.close",
        "window.all.half",
        "window.all.vent",

        "doors.lock",
        "doors.unlock",
        "trunk.rear.open",
        "trunk.rear.close",
        "trunk.front.open",
        "trunk.front.close",

        "sunroof.open",
        "sunroof.close",
        "sunroof.tilt",
        "sunroof.vent",
        "sunroof.comfort",
        "sunroof.stop",
        "sunshade.open",
        "sunshade.close",

        "fridge.cool",
        "fridge.heat",
        "fridge.off",
        "fridge.cool_temperature",
        "fridge.heat_temperature",
    )
}
