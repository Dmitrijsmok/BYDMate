package com.bydmate.app.data.remote

import com.bydmate.app.data.automation.NavigatorAppNames
import com.bydmate.app.data.automation.RouteNavigatorDiscovery
import com.bydmate.app.data.automation.RouteNavigatorUris
import java.util.Locale

/** Where an Alice app action or app name leads. */
internal sealed interface AliceAppTarget {
    /**
     * A navigation app, opened without a route through the same name table and resolver as the
     * local assistant and the agent ([NavigatorAppNames], RouteNavigatorResolver): [navigator] is
     * a RouteNavigatorUris id, null = the app chosen in «Навигатор для маршрутов».
     */
    data class Navigator(val navigator: String?) : AliceAppTarget

    /** Another app: its known [packages] first, then a launcher entry whose label or package is
     *  exactly one of [labels] / [packageTokens], then one that contains them. */
    data class App(
        val packages: List<String> = emptyList(),
        val labels: Set<String> = emptySet(),
        val packageTokens: Set<String> = emptySet(),
    ) : AliceAppTarget

    /** BYDMate itself, whatever its package. */
    data object Self : AliceAppTarget

    /** A screen of the system settings, one of [AliceAppCatalog.SETTINGS_SECTIONS]; opened by the
     *  ActionDispatcher "system_settings" kind, never by a launcher search. */
    data class Settings(val section: String) : AliceAppTarget
}

/**
 * The one app-name table of BYDMate: the app actions the reference worker sends
 * (`app.youtube.open`, …), the names Alice's `app.launch` carries («открой тикток») and the names
 * the local assistant opens (the agent's launch_app, the offline «открой <приложение>»), so a name
 * means the same app whoever heard it. Alternative builds (ReVanced/RVX YouTube, TikTok variants)
 * are found by package token and launcher label ([pick]). Pure.
 */
internal object AliceAppCatalog {

    /** The settings screens open_settings / «открой настройки …» may open; nothing else. */
    val SETTINGS_SECTIONS = setOf("car", "display", "android", "wifi", "bluetooth", "sound", "apps")

    /** YouTube and its ReVanced/RVX builds, most preferred first (the youtube play/search kind too). */
    val YOUTUBE_PACKAGES = listOf(
        "anddea.youtube",
        "com.google.android.youtube",
        "app.revanced.android.youtube",
        "app.rvx.android.youtube",
    )

    private const val CAR_SETTINGS_PACKAGE = "com.byd.carsettings"
    private const val ANDROID_SETTINGS_PACKAGE = "com.android.settings"

    /** The package that shows [section] (a split screen pane or the diagnostics need one). */
    fun settingsPackage(section: String): String =
        if (section == "car") CAR_SETTINGS_PACKAGE else ANDROID_SETTINGS_PACKAGE

    /** The actions Settings shows the matched app for, in this order. */
    val diagnosticActions = listOf(
        "app.navigation.open", "app.waze.open", "app.yandex_navi.open", "app.yandex_maps.open",
        "app.google_maps.open", "app.dgis.open", "app.youtube.open", "app.music.open", "app.tiktok.open",
        "app.browser.open", "app.chrome.open", "app.abrp.open", "app.camera.open", "app.dashcam.open",
        "app.files.open", "app.drive_modes.open", "app.sentry.open", "app.media_center.open", "app.phone.open",
        "app.radio.open", "app.car_settings.open", "app.android_settings.open", "app.bydmate.open",
    )

    private val navigatorActions = mapOf(
        "app.waze.open" to RouteNavigatorUris.WAZE,
        "app.yandex_navi.open" to RouteNavigatorUris.YANDEX,
        "app.yandex_maps.open" to RouteNavigatorUris.MAPS,
        "app.google_maps.open" to RouteNavigatorUris.GOOGLE_MAPS,
        "app.dgis.open" to RouteNavigatorUris.DGIS,
    )

    fun forAction(action: String): AliceAppTarget? = when (action) {
        "app.navigation.open" -> AliceAppTarget.Navigator(null)
        "app.bydmate.open" -> AliceAppTarget.Self
        "app.car_settings.open" -> AliceAppTarget.Settings("car")
        "app.android_settings.open" -> AliceAppTarget.Settings("android")
        else -> navigatorActions[action]?.let { AliceAppTarget.Navigator(it) } ?: staticTargets[action]
    }

    /** Never null: a name nobody knows is looked up as a launcher label / package token. */
    fun forName(name: String): AliceAppTarget = known(name) ?: byLabel(name)

    /**
     * The target of a name this table knows (a navigation app, a settings screen, an alias), or
     * null: the closed set the offline «открой <приложение>» opens without the agent.
     */
    fun known(name: String): AliceAppTarget? {
        NavigatorAppNames.of(name)?.let { return AliceAppTarget.Navigator(it.takeUnless { id -> id == NavigatorAppNames.DEFAULT }) }
        val normalized = normalize(name)
        settingsNames[normalized]?.let { return AliceAppTarget.Settings(it) }
        return textAliases[normalized]?.let(::forAction)
    }

    /** A name looked up only by launcher label and package token. */
    fun byLabel(name: String): AliceAppTarget.App {
        val normalized = normalize(name)
        val token = normalized.replace(NON_ALNUM, "").takeIf { it.length >= MIN_TOKEN_CHARS }
        return AliceAppTarget.App(labels = setOf(normalized), packageTokens = setOfNotNull(token))
    }

    /** The settings screen [name] means, or null. */
    fun settingsSection(name: String): String? = settingsNames[normalize(name)]

    /**
     * The launcher entries [target] can open, in one tier: a package it knows, in its own order
     * (only the first one present); else the entries whose label or package is exactly one of its
     * labels / tokens; else those that contain one. Several entries of one tier are several apps
     * (one per package); callers that cannot ask back take the first.
     */
    fun pick(target: AliceAppTarget.App, apps: List<RouteNavigatorDiscovery.LauncherApp>): List<RouteNavigatorDiscovery.LauncherApp> {
        target.packages.firstNotNullOfOrNull { pkg -> apps.firstOrNull { it.packageName == pkg } }?.let { return listOf(it) }
        fun label(app: RouteNavigatorDiscovery.LauncherApp) = normalize(app.label)
        fun pkg(app: RouteNavigatorDiscovery.LauncherApp) = app.packageName.lowercase(Locale.ROOT)
        val exact = apps.filter { label(it) in target.labels || pkg(it) in target.packageTokens }
        val tier = exact.ifEmpty {
            apps.filter { app ->
                target.labels.any { it.isNotEmpty() && label(app).contains(it) } ||
                    target.packageTokens.any { pkg(app).contains(it) }
            }
        }
        return tier.distinctBy { it.packageName }
    }

    /** The names (aliases, navigator and settings names) that lead to [action], for Settings. */
    fun spokenNames(action: String): List<String> {
        val navigator = when (action) {
            "app.navigation.open" -> NavigatorAppNames.DEFAULT
            else -> navigatorActions[action]
        }
        val target = forAction(action)
        return (navigator?.let(NavigatorAppNames::namesOf).orEmpty() +
            textAliases.filterValues { it == action }.keys +
            (target as? AliceAppTarget.Settings)?.let { s -> settingsNames.filterValues { it == s.section }.keys }.orEmpty())
            .distinct()
    }

    private fun normalize(name: String): String =
        name.trim().lowercase(Locale.ROOT).replace('ё', 'е').replace(WHITESPACE, " ")

    private val WHITESPACE = Regex("\\s+")
    private val NON_ALNUM = Regex("[^\\p{L}\\p{Nd}]+")
    private const val MIN_TOKEN_CHARS = 3

    private val staticTargets = mapOf(
        "app.music.open" to AliceAppTarget.App(
            packages = listOf("ru.yandex.music"),
            labels = setOf("яндекс музыка", "yandex music"),
            packageTokens = setOf("yandex.music"),
        ),
        "app.youtube.open" to AliceAppTarget.App(
            packages = YOUTUBE_PACKAGES,
            labels = setOf("youtube", "youtube revanced", "revanced youtube", "youtube rvx"),
            packageTokens = setOf("youtube"),
        ),
        "app.browser.open" to AliceAppTarget.App(
            packages = listOf("com.yandex.browser", "com.android.chrome"),
            labels = setOf("яндекс браузер", "yandex browser", "chrome", "браузер"),
            packageTokens = setOf("yandex.browser", "chrome"),
        ),
        "app.chrome.open" to AliceAppTarget.App(
            packages = listOf("com.android.chrome"),
            labels = setOf("chrome", "google chrome"),
            packageTokens = setOf("chrome"),
        ),
        "app.camera.open" to AliceAppTarget.App(
            packages = listOf("com.byd.avc"),
            labels = setOf("камера", "камеры", "camera", "360"),
            packageTokens = setOf("byd.avc"),
        ),
        "app.dashcam.open" to AliceAppTarget.App(
            packages = listOf("com.byd.cdr"),
            labels = setOf("регистратор", "видеорегистратор", "dashcam"),
            packageTokens = setOf("byd.cdr", "dashcam"),
        ),
        "app.files.open" to AliceAppTarget.App(
            packages = listOf("com.byd.filemanager"),
            labels = setOf("файлы", "файловый менеджер", "files"),
            packageTokens = setOf("filemanager"),
        ),
        "app.drive_modes.open" to AliceAppTarget.App(
            packages = listOf("com.byd.drivemode"),
            labels = setOf("режимы вождения", "режим вождения", "drive mode", "drive modes"),
            packageTokens = setOf("drivemode"),
        ),
        "app.sentry.open" to AliceAppTarget.App(
            packages = listOf("com.byd.sentrymode"),
            labels = setOf("часовой", "охрана", "охранный режим", "sentry"),
            packageTokens = setOf("sentry"),
        ),
        "app.abrp.open" to AliceAppTarget.App(
            packages = listOf("com.iternio.abrpapp"),
            labels = setOf("abrp", "a better routeplanner"),
            packageTokens = setOf("abrp"),
        ),
        "app.media_center.open" to AliceAppTarget.App(
            packages = listOf("com.byd.mediacenter"),
            labels = setOf("медиацентр", "медиа центр", "media center"),
            packageTokens = setOf("mediacenter"),
        ),
        "app.phone.open" to AliceAppTarget.App(
            packages = listOf("com.byd.bluetoothcall"),
            labels = setOf("телефон", "звонки", "phone"),
            packageTokens = setOf("bluetoothcall"),
        ),
        "app.radio.open" to AliceAppTarget.App(
            labels = setOf("радио", "radio"),
            packageTokens = setOf("radio"),
        ),
        "app.tiktok.open" to AliceAppTarget.App(
            packages = listOf(
                "com.zhiliaoapp.musically",
                "com.ss.android.ugc.trill",
                "com.zhiliaoapp.musically.go",
                "com.ss.android.ugc.aweme",
            ),
            labels = setOf("tiktok", "tik tok", "тикток", "тик ток"),
            packageTokens = setOf("tiktok", "musically", "ugc.trill", "ugc.aweme"),
        ),
    )

    // Settings screens by name, in the closed set of [SETTINGS_SECTIONS] (fork a6918f26).
    private val settingsNames = mapOf(
        "настройки машины" to "car", "настройки автомобиля" to "car", "car settings" to "car",
        "настройки экрана" to "display", "display settings" to "display",
        "настройки" to "android", "системные настройки" to "android", "настройки android" to "android",
        "настройки андроид" to "android", "android settings" to "android",
        "настройки wifi" to "wifi", "настройки wi fi" to "wifi", "настройки вайфай" to "wifi",
        "настройки вай фай" to "wifi", "wifi settings" to "wifi",
        "настройки bluetooth" to "bluetooth", "настройки блютус" to "bluetooth", "настройки блютуз" to "bluetooth",
        "bluetooth settings" to "bluetooth",
        "настройки звука" to "sound", "sound settings" to "sound",
        "настройки приложений" to "apps", "apps settings" to "apps",
    )

    // Names of navigation apps are not here: NavigatorAppNames owns them for every assistant.
    // Accusative forms («открой камеру») are listed where they differ: the offline «открой …»
    // matches the name as said.
    private val textAliases = mapOf(
        "youtube" to "app.youtube.open",
        "ютуб" to "app.youtube.open",
        "youtube premium" to "app.youtube.open",
        "ютуб premium" to "app.youtube.open",
        "ютуб премиум" to "app.youtube.open",
        "youtube byd" to "app.youtube.open",
        "ютуб byd" to "app.youtube.open",
        "youtube revanced" to "app.youtube.open",
        "revanced" to "app.youtube.open",
        "rvx" to "app.youtube.open",
        "яндекс музыка" to "app.music.open",
        "яндекс музыку" to "app.music.open",
        "yandex music" to "app.music.open",
        "музыка" to "app.music.open",
        "музыку" to "app.music.open",
        "браузер" to "app.browser.open",
        "browser" to "app.browser.open",
        "chrome" to "app.chrome.open",
        "хром" to "app.chrome.open",
        "камера" to "app.camera.open",
        "камеру" to "app.camera.open",
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
        "часовой" to "app.sentry.open",
        "охрана" to "app.sentry.open",
        "охрану" to "app.sentry.open",
        "охранный режим" to "app.sentry.open",
        "abrp" to "app.abrp.open",
        "абрп" to "app.abrp.open",
        "маршрутный планировщик" to "app.abrp.open",
        "a better routeplanner" to "app.abrp.open",
        "медиацентр" to "app.media_center.open",
        "медиа центр" to "app.media_center.open",
        "media center" to "app.media_center.open",
        "плеер" to "app.media_center.open",
        "телефон" to "app.phone.open",
        "звонки" to "app.phone.open",
        "phone" to "app.phone.open",
        "радио" to "app.radio.open",
        "radio" to "app.radio.open",
        "bydmate" to "app.bydmate.open",
        "tiktok" to "app.tiktok.open",
        "tik tok" to "app.tiktok.open",
        "тикток" to "app.tiktok.open",
        "тик ток" to "app.tiktok.open",
        "тик-ток" to "app.tiktok.open",
    )
}
