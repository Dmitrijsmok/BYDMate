package com.bydmate.app.data.automation

import android.content.Intent
import android.content.pm.PackageManager
import com.bydmate.app.navdata.NavPackages
import java.util.Locale

/**
 * Discovers installed navigation apps without equating "installed" with
 * PackageManager.getLaunchIntentForPackage(). On DiLink/vendor builds those are not equivalent:
 * a package can own navigation deep links while exposing no ordinary launcher intent.
 */
internal object RouteNavigatorDiscovery {
    private val ORDER = listOf(
        RouteNavigatorUris.YANDEX,
        RouteNavigatorUris.DGIS,
        RouteNavigatorUris.MAPS,
        RouteNavigatorUris.WAZE,
        RouteNavigatorUris.GOOGLE_MAPS,
    )

    fun installedIds(pm: PackageManager): List<String> =
        ORDER.filter { packagesFor(it, pm).isNotEmpty() }

    fun packagesFor(navigator: String, pm: PackageManager): List<String> {
        val id = RouteNavigatorUris.normalize(navigator)
        val packages = LinkedHashSet<String>()

        canonicalPackages(id).filterTo(packages) { packageExists(pm, it) }

        launcherApps(pm).forEach { app ->
            if (matches(id, app.packageName, app.label)) packages += app.packageName
        }

        return packages.toList()
    }

    internal fun packageExists(pm: PackageManager, packageName: String): Boolean =
        runCatching { pm.getApplicationInfo(packageName, 0); true }.getOrDefault(false)

    private fun canonicalPackages(id: String): List<String> = when (id) {
        RouteNavigatorUris.YANDEX -> NavPackages.YANDEX_NAVI.toList()
        RouteNavigatorUris.DGIS -> listOf(RouteNavigatorUris.DGIS_PACKAGE)
        RouteNavigatorUris.MAPS -> NavPackages.YANDEX_MAPS.toList()
        RouteNavigatorUris.WAZE -> listOf(RouteNavigatorUris.WAZE_PACKAGE)
        RouteNavigatorUris.GOOGLE_MAPS -> RouteNavigatorUris.GOOGLE_MAPS_PACKAGES
        else -> emptyList()
    }

    private fun launcherApps(pm: PackageManager): List<LauncherApp> {
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        return runCatching {
            pm.queryIntentActivities(intent, 0).mapNotNull { info ->
                val pkg = info.activityInfo?.packageName ?: return@mapNotNull null
                val label = runCatching { info.loadLabel(pm)?.toString().orEmpty() }.getOrDefault("")
                LauncherApp(pkg, label)
            }
        }.getOrDefault(emptyList())
    }

    @Suppress("CyclomaticComplexMethod")
    private fun matches(id: String, packageName: String, rawLabel: String): Boolean {
        val pkg = packageName.lowercase(Locale.ROOT)
        val label = rawLabel.trim().lowercase(Locale.ROOT)
        return when (id) {
            RouteNavigatorUris.YANDEX ->
                "yandexnavi" in pkg ||
                    label.contains("яндекс навигатор") ||
                    label.contains("yandex navigator")
            RouteNavigatorUris.DGIS ->
                "dublgis" in pkg || "2gis" in pkg || "2гис" in label || "2gis" in label
            RouteNavigatorUris.MAPS ->
                "yandexmaps" in pkg ||
                    label.contains("яндекс карты") ||
                    label.contains("yandex maps")
            RouteNavigatorUris.WAZE ->
                "waze" in pkg || label == "waze"
            RouteNavigatorUris.GOOGLE_MAPS ->
                pkg in RouteNavigatorUris.GOOGLE_MAPS_PACKAGES ||
                    (pkg.contains("maps") && (pkg.contains("google") || pkg.contains("revanced"))) ||
                    pkg.endsWith(".android.apps.maps") ||
                    label == "google maps" ||
                    label == "карты google" ||
                    label == "гугл карты"
            else -> false
        }
    }

    private data class LauncherApp(val packageName: String, val label: String)
}
