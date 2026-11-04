package com.bydmate.app.data.automation

import java.util.Locale

/**
 * App names that mean a navigation app, for every path that opens one by name: the agent's
 * launch_app, the offline «открой навигатор» and the Alice bridge. One table, so a name means
 * the same app whichever assistant heard it. Pure.
 *
 * «навигатор» / «навигация» is the app chosen in «Навигатор для маршрутов» ([DEFAULT]). The
 * name of an app is that app whatever is chosen: «открой Google Maps» with Waze chosen opens
 * Google Maps, «открой Waze» opens Waze. Resolve the result to packages with
 * [RouteNavigatorResolver.launchCandidates] (navigator = null for [DEFAULT]).
 */
object NavigatorAppNames {

    /** The app chosen in settings. */
    const val DEFAULT = "default"

    /** [DEFAULT], a [RouteNavigatorUris] id, or null when [name] is not a navigation app. */
    fun of(name: String): String? =
        NAMES[name.trim().lowercase(Locale.ROOT).replace('ё', 'е').replace(WHITESPACE, " ")]

    /** The names that mean [navigator] ([DEFAULT] or a [RouteNavigatorUris] id), for Settings. */
    fun namesOf(navigator: String): List<String> = NAMES.filterValues { it == navigator }.keys.toList()

    private val WHITESPACE = Regex("\\s+")

    private val NAMES: Map<String, String> = buildMap {
        fun names(navigator: String, vararg spoken: String) = spoken.forEach { put(it, navigator) }
        names(DEFAULT, "навигатор", "навигация", "навигацию", "navigator", "navigation")
        names(RouteNavigatorUris.YANDEX, "яндекс навигатор", "яндекс навигация", "yandex navigator", "yandex navi")
        // A bare «карты» stays Yandex Maps, as the launch_app alias always had it.
        names(RouteNavigatorUris.MAPS, "яндекс карты", "yandex maps", "карты")
        names(RouteNavigatorUris.DGIS, "2гис", "2gis", "два гис", "дубльгис")
        names(RouteNavigatorUris.WAZE, "waze", "вейз", "вэйз", "уэйз")
        names(
            RouteNavigatorUris.GOOGLE_MAPS,
            "google maps", "гугл карты", "гугл мапс", "карты google", "карты гугл", "google карты",
        )
    }
}
