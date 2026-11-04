package com.bydmate.app.data.automation

import android.net.Uri

/**
 * Deep links of the map apps the `navigate` action can open (#190, #200, #305): Yandex Navigator
 * (default), 2GIS, Yandex Maps, Waze or Google Maps, chosen by the user in settings.
 *
 * The two schemes disagree on everything except the intent action: Yandex takes named `lat`/`lon`
 * parameters, 2GIS takes a path segment with the LONGITUDE first. Keeping both shapes here means
 * the dispatcher branches once on the app and never on the coordinate order.
 */
object RouteNavigatorUris {

    /** SharedPreferences file the voice/agent settings already live in. */
    const val PREFS_NAME = "voice"
    const val KEY_ROUTE_NAVIGATOR = "route_navigator"

    /**
     * Optional exact package of a non-standard build of the chosen app (vendor, ReVanced, other
     * store). When set it is used as given for that app; blank means the installed package is
     * found by [RouteNavigatorDiscovery].
     */
    const val KEY_ROUTE_NAVIGATOR_PACKAGE = "route_navigator_package"

    const val YANDEX = "yandex"
    const val DGIS = "dgis"

    /**
     * Third settings value (#200): the same yandexmaps:// dialect that `app="maps"` reaches
     * per-command (see below) is now also a persisted "Навигатор для маршрутов" choice, so
     * routes/search/points without an explicit `app` land here too.
     */
    const val MAPS = "maps"

    /** Fourth settings value (#305): Waze, `waze://` with the latitude first. */
    const val WAZE = "waze"

    /** Fifth settings value: Google Maps, its documented `api=1` Maps URLs pinned to the app. */
    const val GOOGLE_MAPS = "google_maps"

    const val YANDEX_PACKAGE = "ru.yandex.yandexnavi"
    const val DGIS_PACKAGE = "ru.dublgis.dgismobile"
    const val WAZE_PACKAGE = "com.waze"
    const val GOOGLE_MAPS_PACKAGE = "com.google.android.apps.maps"

    /** ReVanced Google Maps: the build that runs on MicroG, which head units without Google services need. */
    const val GOOGLE_MAPS_REVANCED_PACKAGE = "app.revanced.android.apps.maps"

    /** Google Maps builds by preference: the MicroG one works on a head unit, the stock one may not. */
    val GOOGLE_MAPS_PACKAGES: List<String> = listOf(GOOGLE_MAPS_REVANCED_PACKAGE, GOOGLE_MAPS_PACKAGE)

    /** Every settings value, in the order the settings screen lists them. */
    val ALL: List<String> = listOf(YANDEX, DGIS, MAPS, WAZE, GOOGLE_MAPS)

    /** Log/diagnostic names of the three deep links. */
    const val MODE_SEARCH = "search"
    const val MODE_SHOW = "show"
    const val MODE_ROUTE = "route"

    /** Stored value normalised: anything unset or unknown is the Yandex Navigator default. */
    fun normalize(value: String?): String = when (value) {
        DGIS -> DGIS
        MAPS -> MAPS
        WAZE -> WAZE
        GOOGLE_MAPS -> GOOGLE_MAPS
        else -> YANDEX
    }

    fun packageOf(navigator: String): String = when (normalize(navigator)) {
        DGIS -> DGIS_PACKAGE
        WAZE -> WAZE_PACKAGE
        GOOGLE_MAPS -> GOOGLE_MAPS_PACKAGE
        else -> YANDEX_PACKAGE
    }

    /** Free-text search on the map ("найди кафе"). */
    fun search(navigator: String, query: String): String = when (normalize(navigator)) {
        DGIS -> "dgis://2gis.ru/search/${Uri.encode(query)}"
        WAZE -> "waze://?q=${Uri.encode(query)}"
        GOOGLE_MAPS -> "https://www.google.com/maps/search/?api=1&query=${Uri.encode(query)}"
        else -> "yandexnavi://map_search?text=${Uri.encode(query)}"
    }

    /**
     * Pin without a route. [label] is the pin caption — Yandex as a parameter, Google Maps in
     * brackets after the coordinates; the 2GIS and Waze links take none.
     */
    fun showPoint(navigator: String, lat: Double, lon: Double, label: String?): String = when (normalize(navigator)) {
        DGIS -> "dgis://2gis.ru/geo/$lon,$lat"
        WAZE -> "waze://?ll=$lat,$lon"
        GOOGLE_MAPS -> buildString {
            append("https://www.google.com/maps/search/?api=1&query=$lat%2C$lon")
            if (label != null) append("%20(${Uri.encode(label)})")
        }
        else -> buildString {
            append("yandexnavi://show_point_on_map?lat=$lat&lon=$lon&zoom=14")
            if (label != null) append("&desc=${Uri.encode(label)}")
        }
    }

    /** Car route to the point. */
    fun route(navigator: String, lat: Double, lon: Double): String = when (normalize(navigator)) {
        DGIS -> "dgis://2gis.ru/routeSearch/rsType/car/to/$lon,$lat"
        WAZE -> "waze://?ll=$lat,$lon&navigate=yes"
        GOOGLE_MAPS ->
            "https://www.google.com/maps/dir/?api=1&destination=$lat%2C$lon&travelmode=driving&dir_action=navigate"
        else -> "yandexnavi://build_route_on_map?lat_to=$lat&lon_to=$lon"
    }

    /** Waze's saved Home or Work ([shortcut] "home"/"work"), navigation started like its routes. */
    fun wazeFavorite(shortcut: String): String = "waze://?favorite=$shortcut&navigate=yes"

    /**
     * Yandex Maps' own dialect (#200), reached either per command with `app="maps"` or, since
     * the setting grew a third value, when [MAPS] is the chosen navigator — Maps is a separate
     * app from the Navigator and speaks `yandexmaps://`. The route form leaves the start point
     * empty (`rtext=~to`, "from me"); that form is absent from Yandex' public docs but is what
     * current Maps builds honour.
     */
    fun mapsSearch(query: String): String = "yandexmaps://maps.yandex.ru/?text=${Uri.encode(query)}"

    /** Pin without a route. The `pt` dialect carries no caption, so the label stays in the log. */
    fun mapsShowPoint(lat: Double, lon: Double): String = "yandexmaps://maps.yandex.ru/?pt=$lat,$lon&z=14"

    fun mapsRoute(lat: Double, lon: Double): String = "yandexmaps://maps.yandex.ru/?rtext=~$lat,$lon&rtt=auto"
}
