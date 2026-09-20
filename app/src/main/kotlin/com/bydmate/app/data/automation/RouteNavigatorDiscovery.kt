package com.bydmate.app.data.automation

import android.content.Intent
import android.content.pm.PackageManager
import com.bydmate.app.navdata.NavPackages
import java.util.Locale

/**
 * Discovers installed navigation apps by their launcher activities instead of relying only on
 * one hard-coded package name. BYD head units often ship store/vendor variants whose package
 * differs from the Play Store build.
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

        when (id) {
            RouteNavigatorUris.YANDEX -> packages.addAll(NavPackages.YANDEX_NAVI)
            RouteNavigatorUris.DGIS -> packages += RouteNavigatorUris.DGIS_PACKAGE
            RouteNavigatorUris.MAPS -> packages.addAll(NavPackages.YANDEX_MAPS)
            RouteNavigatorUris.WAZE -> packages += RouteNavigatorUris.WAZE_PACKAGE
            RouteNavigatorUris.GOOGLE_MAPS -> packages += RouteNavigatorUris.GOOGLE_MAPS_PACKAGE
        }

        launcherApps(pm).forEach { app ->
            if (matches(id, app.packageName, app.label)) packages += app.packageName
        }

        return packages.filter { pkg ->
            runCatching { pm.getLaunchIntentForPackage(pkg) != null }.getOrDefault(false)
        }
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
                (pkg.contains("google") && pkg.contains("maps")) ||
                    label == "google maps" ||
                    label == "карты google"
            else -> false
        }
    }

    private data class LauncherApp(val packageName: String, val label: String)
}
