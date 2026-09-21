package com.bydmate.app.data.remote

import android.content.Context
import android.content.Intent
import com.bydmate.app.data.automation.RouteNavigatorDiscovery
import com.bydmate.app.data.automation.RouteNavigatorUris
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Resolves Alice app actions/text to an installed launcher package. Alternative builds are found
 * by launcher label/package token, so ReVanced/RVX and vendor-specific packages remain supported.
 */
data class VoiceAppMatch(
    val name: String,
    val action: String,
    val appLabel: String?,
    val packageName: String?,
)

@Singleton
class AliceAppResolver @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    fun resolveAction(action: String): Result<String>? {
        val target = targetForAction(action) ?: return null
        return resolveTarget(target)
    }

    fun resolveText(query: String): Result<String> {
        val normalized = query.trim().lowercase()
        val known = textActionAliases[normalized]?.let(::targetForAction)
        val target = known ?: AppTarget(
            labels = setOf(normalized),
            packageTokens = normalized
                .replace(Regex("[^\\p{L}\\p{Nd}]+"), "")
                .takeIf { it.length >= 3 }
                ?.let(::setOf)
                ?: emptySet(),
        )
        return resolveTarget(target)
    }

    /** User-visible diagnostic mapping for Settings: shows what a voice app action will actually
     *  launch on this head unit. Null package/label means the supported target is not installed. */
    fun diagnosticMatches(): List<VoiceAppMatch> {
        val pm = context.packageManager
        return diagnosticActions.map { (name, action) ->
            val pkg = resolveAction(action)?.getOrNull()
            val label = pkg?.let {
                runCatching {
                    pm.getApplicationLabel(pm.getApplicationInfo(it, 0)).toString()
                }.getOrNull()
            }
            VoiceAppMatch(name, action, label, pkg)
        }
    }

    private fun targetForAction(action: String): AppTarget? =
        dynamicTarget(action) ?: staticTargets[action]

    private fun dynamicTarget(action: String): AppTarget? = when (action) {
        "app.navigation.open" -> AppTarget(packages = selectedNavigationPackages())
        "app.waze.open" -> AppTarget(
            packages = RouteNavigatorDiscovery.packagesFor(
                RouteNavigatorUris.WAZE,
                context.packageManager,
            ),
            labels = setOf("waze"),
            packageTokens = setOf("waze"),
        )
        "app.yandex_navi.open" -> AppTarget(
            packages = RouteNavigatorDiscovery.packagesFor(
                RouteNavigatorUris.YANDEX,
                context.packageManager,
            ),
            labels = setOf("яндекс навигатор", "yandex navigator", "навигатор"),
            packageTokens = setOf("yandexnavi"),
        )
        "app.yandex_maps.open" -> AppTarget(
            packages = RouteNavigatorDiscovery.packagesFor(
                RouteNavigatorUris.MAPS,
                context.packageManager,
            ),
            labels = setOf("яндекс карты", "yandex maps"),
            packageTokens = setOf("yandexmaps"),
        )
        "app.google_maps.open" -> AppTarget(
            packages = RouteNavigatorDiscovery.packagesFor(
                RouteNavigatorUris.GOOGLE_MAPS,
                context.packageManager,
            ),
            labels = setOf("google maps", "карты google", "гугл карты"),
            packageTokens = setOf("google.android.apps.maps"),
        )
        "app.dgis.open" -> AppTarget(
            packages = RouteNavigatorDiscovery.packagesFor(
                RouteNavigatorUris.DGIS,
                context.packageManager,
            ),
            labels = setOf("2gis", "2гис"),
            packageTokens = setOf("dublgis", "2gis"),
        )
        "app.bydmate.open" -> AppTarget(
            packages = listOf(context.packageName),
            labels = setOf("bydmate"),
            packageTokens = setOf("bydmate"),
        )
        else -> null
    }

    private fun resolveTarget(target: AppTarget): Result<String> {
        val pm = context.packageManager
        target.packages.firstOrNull {
            runCatching { pm.getLaunchIntentForPackage(it) != null }.getOrDefault(false)
        }?.let { return Result.success(it) }

        val launcherIntent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val apps = runCatching { pm.queryIntentActivities(launcherIntent, 0) }.getOrDefault(emptyList())

        val exact = apps.firstNotNullOfOrNull { info ->
            val label = runCatching { info.loadLabel(pm)?.toString().orEmpty() }
                .getOrDefault("")
                .trim()
                .lowercase()
            val packageName = info.activityInfo?.packageName.orEmpty()
            val packageLower = packageName.lowercase()
            packageName.takeIf {
                target.labels.any { token -> label == token } ||
                    target.packageTokens.any { token -> packageLower == token }
            }
        }
        if (exact != null) return Result.success(exact)

        val fuzzy = apps.firstNotNullOfOrNull { info ->
            val label = runCatching { info.loadLabel(pm)?.toString().orEmpty() }
                .getOrDefault("")
                .trim()
                .lowercase()
            val packageName = info.activityInfo?.packageName.orEmpty()
            val packageLower = packageName.lowercase()
            packageName.takeIf {
                target.labels.any(label::contains) ||
                    target.packageTokens.any(packageLower::contains)
            }
        }
        return fuzzy?.let(Result.Companion::success)
            ?: Result.failure(IllegalStateException("app_not_installed"))
    }

    private fun selectedNavigationPackages(): List<String> {
        val prefs = context.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, Context.MODE_PRIVATE)
        val selected = RouteNavigatorUris.normalize(
            prefs.getString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, null),
        )
        val installed = RouteNavigatorDiscovery.installedIds(context.packageManager)
        return (listOf(selected) + installed)
            .distinct()
            .flatMap { RouteNavigatorDiscovery.packagesFor(it, context.packageManager) }
            .distinct()
    }

    private data class AppTarget(
        val packages: List<String> = emptyList(),
        val labels: Set<String> = emptySet(),
        val packageTokens: Set<String> = emptySet(),
    )

    companion object {
        private val diagnosticActions = listOf(
            "YouTube" to "app.youtube.open",
            "Яндекс Музыка" to "app.music.open",
            "Waze" to "app.waze.open",
            "Яндекс Навигатор" to "app.yandex_navi.open",
            "Яндекс Карты" to "app.yandex_maps.open",
            "Google Maps" to "app.google_maps.open",
            "2GIS" to "app.dgis.open",
            "Браузер" to "app.browser.open",
            "ABRP" to "app.abrp.open",
            "TikTok" to "app.tiktok.open",
            "Камера" to "app.camera.open",
            "Видеорегистратор" to "app.dashcam.open",
            "Файлы" to "app.files.open",
            "Медиацентр" to "app.media_center.open",
            "Телефон" to "app.phone.open",
            "BYDMate" to "app.bydmate.open",
        )

        private val staticTargets = mapOf(
            "app.music.open" to AppTarget(
                packages = listOf("ru.yandex.music"),
                labels = setOf("яндекс музыка", "yandex music"),
                packageTokens = setOf("yandex.music"),
            ),
            "app.youtube.open" to AppTarget(
                packages = listOf(
                    "anddea.youtube",
                    "com.google.android.youtube",
                    "app.revanced.android.youtube",
                    "app.rvx.android.youtube",
                ),
                labels = setOf("youtube", "youtube revanced", "revanced youtube", "youtube rvx"),
                packageTokens = setOf("youtube"),
            ),
            "app.browser.open" to AppTarget(
                packages = listOf("com.yandex.browser", "com.android.chrome"),
                labels = setOf("яндекс браузер", "yandex browser", "chrome", "браузер"),
                packageTokens = setOf("yandex.browser", "chrome"),
            ),
            "app.car_settings.open" to AppTarget(
                packages = listOf("com.byd.carsettings"),
                labels = setOf("настройки автомобиля", "настройки машины", "car settings"),
                packageTokens = setOf("carsettings"),
            ),
            "app.android_settings.open" to AppTarget(
                packages = listOf("com.android.settings"),
                labels = setOf("settings", "настройки"),
                packageTokens = setOf("android.settings"),
            ),
            "app.camera.open" to AppTarget(
                packages = listOf("com.byd.avc"),
                labels = setOf("камера", "камеры", "camera", "360"),
                packageTokens = setOf("byd.avc"),
            ),
            "app.dashcam.open" to AppTarget(
                packages = listOf("com.byd.cdr"),
                labels = setOf("регистратор", "видеорегистратор", "dashcam"),
                packageTokens = setOf("byd.cdr", "dashcam"),
            ),
            "app.files.open" to AppTarget(
                packages = listOf("com.byd.filemanager"),
                labels = setOf("файлы", "файловый менеджер", "files"),
                packageTokens = setOf("filemanager"),
            ),
            "app.drive_modes.open" to AppTarget(
                packages = listOf("com.byd.drivemode"),
                labels = setOf("режимы вождения", "режим вождения", "drive mode", "drive modes"),
                packageTokens = setOf("drivemode"),
            ),
            "app.sentry.open" to AppTarget(
                packages = listOf("com.byd.sentrymode"),
                labels = setOf("часовой", "охрана", "охранный режим", "sentry"),
                packageTokens = setOf("sentry"),
            ),
            "app.abrp.open" to AppTarget(
                packages = listOf("com.iternio.abrpapp"),
                labels = setOf("abrp", "a better routeplanner"),
                packageTokens = setOf("abrp"),
            ),
            "app.media_center.open" to AppTarget(
                packages = listOf("com.byd.mediacenter"),
                labels = setOf("медиацентр", "медиа центр", "media center"),
                packageTokens = setOf("mediacenter"),
            ),
            "app.phone.open" to AppTarget(
                packages = listOf("com.byd.bluetoothcall"),
                labels = setOf("телефон", "звонки", "phone"),
                packageTokens = setOf("bluetoothcall"),
            ),
            "app.radio.open" to AppTarget(
                labels = setOf("радио", "radio"),
                packageTokens = setOf("radio"),
            ),
            "app.tiktok.open" to AppTarget(
                packages = listOf(
                    "com.zhiliaoapp.musically",
                    "com.ss.android.ugc.trill",
                    "com.ss.android.ugc.aweme",
                ),
                labels = setOf("tiktok", "tik tok", "тикток", "тик ток"),
                packageTokens = setOf("tiktok", "musically", "ugc.trill", "ugc.aweme"),
            ),
        )

        private val textActionAliases = mapOf(
            "youtube" to "app.youtube.open",
            "ютуб" to "app.youtube.open",
            "youtube revanced" to "app.youtube.open",
            "revanced" to "app.youtube.open",
            "rvx" to "app.youtube.open",
            "яндекс музыка" to "app.music.open",
            "yandex music" to "app.music.open",
            "музыка" to "app.music.open",
            "яндекс навигатор" to "app.yandex_navi.open",
            "yandex navigator" to "app.yandex_navi.open",
            "навигатор" to "app.yandex_navi.open",
            "яндекс карты" to "app.yandex_maps.open",
            "yandex maps" to "app.yandex_maps.open",
            "waze" to "app.waze.open",
            "вейз" to "app.waze.open",
            "вэйз" to "app.waze.open",
            "google maps" to "app.google_maps.open",
            "карты google" to "app.google_maps.open",
            "гугл карты" to "app.google_maps.open",
            "2gis" to "app.dgis.open",
            "2гис" to "app.dgis.open",
            "браузер" to "app.browser.open",
            "browser" to "app.browser.open",
            "chrome" to "app.browser.open",
            "хром" to "app.browser.open",
            "настройки машины" to "app.car_settings.open",
            "настройки автомобиля" to "app.car_settings.open",
            "car settings" to "app.car_settings.open",
            "android settings" to "app.android_settings.open",
            "настройки android" to "app.android_settings.open",
            "камера" to "app.camera.open",
            "камеры" to "app.camera.open",
            "camera" to "app.camera.open",
            "360" to "app.camera.open",
            "регистратор" to "app.dashcam.open",
            "видеорегистратор" to "app.dashcam.open",
            "dashcam" to "app.dashcam.open",
            "файлы" to "app.files.open",
            "файловый менеджер" to "app.files.open",
            "files" to "app.files.open",
            "режимы вождения" to "app.drive_modes.open",
            "режим вождения" to "app.drive_modes.open",
            "drive modes" to "app.drive_modes.open",
            "сэнтри" to "app.sentry.open",
            "sentry" to "app.sentry.open",
            "охрана" to "app.sentry.open",
            "охранный режим" to "app.sentry.open",
            "abrp" to "app.abrp.open",
            "a better routeplanner" to "app.abrp.open",
            "медиацентр" to "app.media_center.open",
            "медиа центр" to "app.media_center.open",
            "media center" to "app.media_center.open",
            "телефон" to "app.phone.open",
            "phone" to "app.phone.open",
            "радио" to "app.radio.open",
            "radio" to "app.radio.open",
            "bydmate" to "app.bydmate.open",
            "tiktok" to "app.tiktok.open",
            "tik tok" to "app.tiktok.open",
            "тикток" to "app.tiktok.open",
            "тик ток" to "app.tiktok.open",
        )
    }
}
