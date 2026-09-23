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
        log(
            "navigate: navigator=$chosen" +
                if (manualPackage.isNotBlank()) " package_override=$manualPackage" else ""
        )

        // A manual package is authoritative. Do not second-guess it with
        // getLaunchIntentForPackage(): that exact check caused false "not installed" verdicts
        // on DiLink/vendor APKs. The real startActivity result is the source of truth.
        if (manualPackage.isNotBlank()) return chosen to null

        if (chosen == RouteNavigatorUris.YANDEX) return chosen to null
        if (RouteNavigatorDiscovery.packagesFor(chosen, context.packageManager).isNotEmpty()) {
            return chosen to null
        }

        val reason = when (chosen) {
            RouteNavigatorUris.DGIS -> "2ГИС не установлен, открыт Яндекс Навигатор"
            RouteNavigatorUris.MAPS -> "Яндекс Карты не установлены, открыт Яндекс Навигатор"
            RouteNavigatorUris.WAZE -> "Waze не установлен, открыт Яндекс Навигатор"
            RouteNavigatorUris.GOOGLE_MAPS -> "Google Maps не установлен, открыт Яндекс Навигатор"
            else -> "Навигатор не установлен, открыт Яндекс Навигатор"
        }
        log("navigate: $chosen not detected, falling back to yandex")
        return RouteNavigatorUris.YANDEX to reason
    }

    /**
     * Returns the actual APK package for the requested navigator when one is known.
     * The manual override applies ONLY to the currently selected default navigator.
     * Explicit per-command requests such as Google Maps must resolve their own package and
     * must never be redirected into a manual/default Waze package.
     */
    fun selectedPackage(context: Context, navigator: String): String? {
        val id = RouteNavigatorUris.normalize(navigator)
        val prefs = context.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, Context.MODE_PRIVATE)
        val selected = RouteNavigatorUris.normalize(
            prefs.getString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, null),
        )
        val manualPackage = prefs.getString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR_PACKAGE, null)
            ?.trim().orEmpty()

        if (id == selected && manualPackage.isNotBlank()) return manualPackage
        return RouteNavigatorDiscovery.packagesFor(id, context.packageManager).firstOrNull()
    }
}
