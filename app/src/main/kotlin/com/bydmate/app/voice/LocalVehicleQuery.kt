package com.bydmate.app.voice

import com.bydmate.app.data.remote.DiParsData

/**
 * Latency-critical read-only questions that can be answered from the live vehicle snapshot.
 *
 * Build 64014 proved the direct Local path (GigaAM -> local resolver -> car) feels immediate.
 * These narrow queries use the same principle instead of paying an OpenRouter round-trip for
 * data BYDMate already has. Anything ambiguous stays on the normal agent path.
 */
internal object LocalVehicleQuery {

    data class Reply(val kind: String, val text: String)

    fun answer(text: String, lang: VoiceLang, data: DiParsData?): Reply? {
        if (lang != VoiceLang.RU) return null
        val q = text.lowercase().replace('ё', 'е').trim()

        return when {
            isOutsideTemperature(q) -> Reply(
                "outside_temp",
                data?.exteriorTemp?.let { "Снаружи $it градусов." }
                    ?: "Температура снаружи недоступна.",
            )
            isInsideTemperature(q) -> Reply(
                "inside_temp",
                data?.insideTemp?.let { "В салоне $it градусов." }
                    ?: "Температура в салоне недоступна.",
            )
            isClimateSetpoint(q) -> Reply(
                "climate_setpoint",
                data?.acTemp?.let { "Климат установлен на $it градусов." }
                    ?: "Температура климата недоступна.",
            )
            isBatteryCharge(q) -> Reply(
                "soc",
                data?.soc?.let { "Заряд $it%." }
                    ?: "Заряд батареи сейчас недоступен.",
            )
            else -> null
        }
    }

    private fun isOutsideTemperature(q: String): Boolean =
        mentionsTemperature(q) && OUTSIDE_MARKERS.any(q::contains)

    private fun isInsideTemperature(q: String): Boolean =
        mentionsTemperature(q) && INSIDE_MARKERS.any(q::contains)

    private fun isClimateSetpoint(q: String): Boolean =
        mentionsTemperature(q) && CLIMATE_MARKERS.any(q::contains) && looksLikeRead(q)

    private fun isBatteryCharge(q: String): Boolean {
        val mentionsCharge = "заряд" in q || ("батаре" in q && "процент" in q)
        return mentionsCharge && looksLikeRead(q)
    }

    private fun mentionsTemperature(q: String): Boolean =
        "температур" in q || "градус" in q

    private fun looksLikeRead(q: String): Boolean =
        q == "заряд" || READ_PREFIXES.any(q::startsWith) || "уровень заряда" in q

    private val OUTSIDE_MARKERS = listOf("на улице", "снаруж", "за борт")
    private val INSIDE_MARKERS = listOf("в салон", "внутри салон", "внутри машин")
    private val CLIMATE_MARKERS = listOf("климат", "кондиционер")
    private val READ_PREFIXES = listOf(
        "заряд ",
        "температура",
        "сколько",
        "какой",
        "какая",
        "покажи",
        "скажи",
    )
}
