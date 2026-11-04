package com.bydmate.app.data.automation

import android.content.Intent
import android.content.pm.PackageManager
import com.bydmate.app.navdata.NavPackages
import java.util.Locale

/**
 * Which of the [RouteNavigatorUris] map apps this head unit has, and under which package.
 *
 * "Installed" means the package exists (getApplicationInfo) or a launcher entry is a build of
 * that app. It deliberately does not mean getLaunchIntentForPackage() != null: on DiLink and
 * vendor builds a navigator can own its deep links without an ordinary launch intent, and that
 * check made field build 64023 report an installed Waze as missing.
 */
internal object RouteNavigatorDiscovery {

    /** One launcher entry: its package and its label as the launcher shows it. */
    data class LauncherApp(val packageName: String, val label: String)

    /** The store/variant packages of [navigator] this app knows by name, most preferred first. */
    fun knownPackages(navigator: String): List<String> = when (RouteNavigatorUris.normalize(navigator)) {
        RouteNavigatorUris.DGIS -> listOf(RouteNavigatorUris.DGIS_PACKAGE)
        RouteNavigatorUris.MAPS -> NavPackages.YANDEX_MAPS.toList()
        RouteNavigatorUris.WAZE -> listOf(RouteNavigatorUris.WAZE_PACKAGE)
        RouteNavigatorUris.GOOGLE_MAPS -> RouteNavigatorUris.GOOGLE_MAPS_PACKAGES
        else -> NavPackages.YANDEX_NAVI.toList()
    }

    /** Whether a launcher entry is a build of [navigator], by package token or label. Pure. */
    fun matches(navigator: String, packageName: String, label: String): Boolean {
        val pkg = packageName.lowercase(Locale.ROOT)
        val name = label.trim().lowercase(Locale.ROOT).replace('ё', 'е')
        return when (RouteNavigatorUris.normalize(navigator)) {
            RouteNavigatorUris.DGIS -> listOf("dublgis", "2gis").any { it in pkg } || listOf("2гис", "2gis").any { it in name }
            // "Яндекс Карты и Навигатор" is Maps, so the Navigator needs its own two words together.
            RouteNavigatorUris.MAPS -> "yandexmaps" in pkg || listOf("яндекс карты", "yandex maps").any { it in name }
            RouteNavigatorUris.WAZE -> "waze" in pkg || name == "waze"
            // The Russian launcher label of Google Maps is a bare "Карты", which says nothing:
            // only the package and the explicit names count.
            RouteNavigatorUris.GOOGLE_MAPS -> isGoogleMapsPackage(pkg) || name in GOOGLE_MAPS_LABELS
            else -> "yandexnavi" in pkg || listOf("яндекс навигатор", "yandex navigator").any { it in name }
        }
    }

    /** ReVanced/RVX and other MicroG builds keep "android.apps.maps" (or "maps" and their name) in the package. */
    private fun isGoogleMapsPackage(pkg: String): Boolean =
        pkg.endsWith(".android.apps.maps") || ("maps" in pkg && ("google" in pkg || "revanced" in pkg))

    private val GOOGLE_MAPS_LABELS = setOf("google maps", "карты google", "гугл карты", "google карты")

    /** The navigator id [packageName] is a build of, or null for any other app. Pure. */
    fun navigatorOf(packageName: String): String? =
        RouteNavigatorUris.ALL.firstOrNull { packageName in knownPackages(it) }
            ?: RouteNavigatorUris.ALL.firstOrNull { matches(it, packageName, "") }

    /**
     * The package [navigator] is installed under, or null: a known package that exists first,
     * then a launcher entry that is a build of it. The launcher is only scanned when no known
     * package is there, so the common case costs a few package lookups.
     */
    fun firstPackage(pm: PackageManager, navigator: String): String? =
        knownPackages(navigator).firstOrNull { packageExists(pm, it) }
            ?: launcherApps(pm).firstOrNull { matches(navigator, it.packageName, it.label) }?.packageName

    /** Every navigator with the packages it is installed under (empty when absent), in settings order. */
    fun discover(pm: PackageManager): Map<String, List<String>> {
        val launcher = launcherApps(pm)
        return RouteNavigatorUris.ALL.associateWith { id ->
            (knownPackages(id).filter { packageExists(pm, it) } +
                launcher.filter { matches(id, it.packageName, it.label) }.map { it.packageName }).distinct()
        }
    }

    fun packageExists(pm: PackageManager, packageName: String): Boolean =
        runCatching { pm.getApplicationInfo(packageName, 0); true }.getOrDefault(false)

    fun launcherApps(pm: PackageManager): List<LauncherApp> {
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        return runCatching {
            pm.queryIntentActivities(intent, 0).mapNotNull { info ->
                val pkg = info.activityInfo?.packageName ?: return@mapNotNull null
                LauncherApp(pkg, runCatching { info.loadLabel(pm).toString() }.getOrDefault(""))
            }
        }.getOrDefault(emptyList())
    }
}
