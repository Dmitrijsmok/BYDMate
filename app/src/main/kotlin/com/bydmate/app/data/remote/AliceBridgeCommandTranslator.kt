package com.bydmate.app.data.remote

/**
 * Semantic Alice actions (`climate.on`, `seat.driver.heat` + value, …) to the app's own vehicle
 * command strings, which then run through ActionDispatcher like any automation step: same
 * translator, allowlist and safety/speed gates. Only the actions the reference worker advertises
 * are known; anything else, raw fids included, resolves to null. Pure.
 */
internal object AliceBridgeCommandTranslator {

    private const val SEAT_MAX_LEVEL = 2
    private const val FAN_MIN = 1
    private const val FAN_MAX = 7
    private const val TEMP_MIN = 16
    private const val TEMP_MAX = 33

    private val fixedCommands = mapOf(
        "climate.on" to "自动空调",
        "climate.off" to "关闭空调",
        "climate.auto_on" to "空调自动",
        "climate.auto_off" to "空调手动",
        "climate.recirculation_inner" to "内循环",
        "climate.recirculation_outer" to "外循环",
        "climate.rear_defrost_on" to "后视镜加热",
        "climate.rear_defrost_off" to "关闭后视镜加热",
        "climate.front_defrost_on" to "吹前挡",
        "climate.front_defrost_off" to "关闭吹前挡",
        "climate.flow_only_on" to "打开空调通风",
        "climate.flow_only_off" to "关闭空调通风",
        "climate.airflow_face" to "吹面",
        "climate.airflow_face_feet" to "吹面吹脚",
        "climate.airflow_feet" to "吹脚",
        "climate.airflow_feet_windshield" to "吹脚除霜",
        "climate.airflow_windshield" to "除霜",
        "climate.airflow_face_feet_windshield" to "吹面吹脚除霜",
        "climate.airflow_face_windshield" to "吹面除霜",
        "light.interior_on" to "打开车内灯",
        "light.interior_off" to "关闭车内灯",
        "light.ambient_on" to "氛围灯打开",
        "light.ambient_off" to "氛围灯关闭",
        "window.driver.open" to "主驾打开100",
        "window.driver.close" to "主驾打开0",
        "window.passenger.open" to "副驾打开100",
        "window.passenger.close" to "副驾打开0",
        "window.rear_left.open" to "后左打开100",
        "window.rear_left.close" to "后左打开0",
        "window.rear_right.open" to "后右打开100",
        "window.rear_right.close" to "后右打开0",
        "window.all.open" to "车窗全开",
        "window.all.close" to "车窗关闭",
        "window.all.half" to "车窗半开",
        "window.all.vent" to "车窗通风",
        "trunk.rear.open" to "开后备箱",
        "trunk.rear.close" to "关后备箱",
        "sunroof.open" to "天窗打开100",
        "sunroof.close" to "天窗打开0",
        // 天窗打开50 is the half-open slide, not a tilt (upstream, live 2026-07-30). The worker's
        // "Люк наполовину" card sends it as sunroof.tilt (worker <= 5.12), hence both names.
        "sunroof.half" to "天窗打开50",
        "sunroof.tilt" to "天窗打开50",
        // The actual tilt-up for airing is 天窗通风.
        "sunroof.vent" to "天窗通风",
        "sunroof.comfort" to "天窗舒适打开",
        "sunroof.stop" to "天窗停止",
        "sunshade.open" to "遮阳帘打开",
        "sunshade.close" to "遮阳帘关闭",
    )

    private val seatPrefixes = mapOf(
        "seat.driver.heat" to "主驾座椅加热",
        "seat.passenger.heat" to "副驾座椅加热",
        "seat.driver.vent" to "主驾座椅通风",
        "seat.passenger.vent" to "副驾座椅通风",
    )

    private val windowPrefixes = mapOf(
        "window.driver.position" to "主驾",
        "window.passenger.position" to "副驾",
        "window.rear_left.position" to "后左",
        "window.rear_right.position" to "后右",
    )

    /** The vehicle command for [action] with [value], or null when the action is not known or
     *  the value is out of its range. */
    fun resolve(action: String, value: Int?): String? {
        fixedCommands[action]?.let { return it }
        seatPrefixes[action]?.let { prefix -> return seat(prefix, value) }
        windowPrefixes[action]?.let { prefix ->
            return value?.takeIf { it in 0..100 }?.let { prefix + "打开" + it }
        }
        return when (action) {
            // The same 16..33 window the translator clamps to (16 = Leopard 3 minimum, 33 = Seagull maximum).
            "climate.temperature" -> value?.coerceIn(TEMP_MIN, TEMP_MAX)?.let { "设置温度$it" }
            "climate.fan_level" -> value?.takeIf { it in FAN_MIN..FAN_MAX }?.let { "风量$it" }
            else -> null
        }
    }

    /** Yandex knows off / min / max only: 0, 1 and 2. */
    private fun seat(prefix: String, value: Int?): String? = when (value) {
        0 -> prefix + "关闭"
        in 1..SEAT_MAX_LEVEL -> prefix + value + "档"
        else -> null
    }
}
