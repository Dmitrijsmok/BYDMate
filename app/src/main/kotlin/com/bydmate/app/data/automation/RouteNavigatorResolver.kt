package com.bydmate.app.data.automation

import android.content.Context

internal object RouteNavigatorResolver {
    fun resolve(
        context: Context,
        isPackageInstalled: (String) -> Boolean,
        log: (String) -> Unit,
    ): Pair<String, String?> {
        val prefs = context.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, Context.MODE_PRIVATE)
        val chosen = RouteNavigatorUris.normalize(
            prefs.getString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, null),
        )
        val manualPackage = prefs.getString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR_PACKAGE, null)
            ?.trim().orEmpty()
        log("navigate: navigator=$chosen" +
            if (manualPackage.isNotBlank()) " package_override=$manualPackage" else "")

        if (selectedPackage(context, chosen, isPackageInstalled) != null) {
            return chosen to null
        }

        if (chosen == RouteNavigatorUris.YANDEX) return chosen to null

        val (label, reason) = when (chosen) {
            RouteNavigatorUris.DGIS -> "2gis" to "2ГИС не установлен, открыт Яндекс Навигатор"
            RouteNavigatorUris.MAPS -> "yandex maps" to "Яндекс Карты не установлены, открыт Яндекс Навигатор"
            RouteNavigatorUris.WAZE -> "waze" to "Waze не установлен, открыт Яндекс Навигатор"
            RouteNavigatorUris.GOOGLE_MAPS -> "google maps" to
                "Google Maps не установлен, открыт Яндекс Навигатор"
            else -> "navigator" to "Навигатор не установлен, открыт Яндекс Навигатор"
        }
        log("navigate: $label not installed, falling back to yandex")
        return RouteNavigatorUris.YANDEX to reason
    }

    /**
     * Resolves the actual APK used for a navigator id. A manually entered package only overrides
     * the navigator currently selected in Settings; an explicit per-command navigator such as
     * "Google Maps" still resolves its own installed package and can never be redirected to Waze.
     */
    fun selectedPackage(
        context: Context,
        navigator: String,
        isPackageInstalled: (String) -> Boolean,
    ): String? {
        val id = RouteNavigatorUris.normalize(navigator)
        val prefs = context.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, Context.MODE_PRIVATE)
        val selected = RouteNavigatorUris.normalize(
            prefs.getString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, null),
        )
        val manualPackage = prefs.getString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR_PACKAGE, null)
            ?.trim().orEmpty()

        if (id == selected && manualPackage.isNotBlank() && isPackageInstalled(manualPackage)) {
            return manualPackage
        }
        return RouteNavigatorDiscovery.packagesFor(id, context.packageManager).firstOrNull()
    }
}
