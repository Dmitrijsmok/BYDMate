package com.bydmate.app.voice

/**
 * Tiny deterministic parser for explicit app-launch requests.
 *
 * It only extracts the app name. Resolution stays in AliceAppResolver so the local assistant
 * and Alice share the same package/label/token discovery, including alternative APK variants.
 * Unknown names deliberately fall through to the normal agent path.
 */
internal object LocalAppLaunchQuery {
    fun target(text: String, lang: VoiceLang): String? {
        val q = text.trim().lowercase().replace('ё', 'е')
        val prefixes = when (lang) {
            VoiceLang.RU -> RU_PREFIXES
            VoiceLang.EN -> EN_PREFIXES
            else -> emptyList()
        }
        val prefix = prefixes.firstOrNull(q::startsWith) ?: return null
        return q.removePrefix(prefix)
            .trim()
            .trim('"', '\'', '«', '»')
            .takeIf { it.isNotBlank() }
    }

    private val RU_PREFIXES = listOf(
        "открой приложение ",
        "запусти приложение ",
        "открыть приложение ",
        "запустить приложение ",
        "открой ",
        "запусти ",
        "открыть ",
        "запустить ",
    )

    private val EN_PREFIXES = listOf(
        "open app ",
        "launch app ",
        "start app ",
        "open ",
        "launch ",
        "start ",
    )
}
