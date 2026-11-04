package com.bydmate.app.data.remote

import com.bydmate.app.data.automation.NavigatorAppNames
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
}

/**
 * The app actions the reference worker sends (`app.youtube.open`, …) and the names `app.launch`
 * carries («открой тикток»). Alternative builds (ReVanced/RVX YouTube, TikTok variants) are found
 * by package token and launcher label. Pure.
 */
internal object AliceAppCatalog {

    /** The actions Settings shows the matched app for, in this order. */
    val diagnosticActions = listOf(
        "app.navigation.open", "app.waze.open", "app.yandex_navi.open", "app.yandex_maps.open",
        "app.google_maps.open", "app.dgis.open", "app.youtube.open", "app.music.open", "app.tiktok.open",
        "app.browser.open", "app.abrp.open", "app.camera.open", "app.dashcam.open", "app.files.open",
        "app.media_center.open", "app.phone.open", "app.bydmate.open",
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
        else -> navigatorActions[action]?.let { AliceAppTarget.Navigator(it) } ?: staticTargets[action]
    }

    /** Never null: a name nobody knows is looked up as a launcher label / package token. */
    fun forName(name: String): AliceAppTarget {
        NavigatorAppNames.of(name)?.let { return AliceAppTarget.Navigator(it.takeUnless { id -> id == NavigatorAppNames.DEFAULT }) }
        val normalized = name.trim().lowercase(Locale.ROOT).replace('ё', 'е').replace(WHITESPACE, " ")
        textAliases[normalized]?.let(::forAction)?.let { return it }
        val token = normalized.replace(NON_ALNUM, "").takeIf { it.length >= MIN_TOKEN_CHARS }
        return AliceAppTarget.App(labels = setOf(normalized), packageTokens = setOfNotNull(token))
    }

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
            packages = listOf(
                "anddea.youtube",
                "com.google.android.youtube",
                "app.revanced.android.youtube",
                "app.rvx.android.youtube",
            ),
            labels = setOf("youtube", "youtube revanced", "revanced youtube", "youtube rvx"),
            packageTokens = setOf("youtube"),
        ),
        "app.browser.open" to AliceAppTarget.App(
            packages = listOf("com.yandex.browser", "com.android.chrome"),
            labels = setOf("яндекс браузер", "yandex browser", "chrome", "браузер"),
            packageTokens = setOf("yandex.browser", "chrome"),
        ),
        "app.car_settings.open" to AliceAppTarget.App(
            packages = listOf("com.byd.carsettings"),
            labels = setOf("настройки автомобиля", "настройки машины", "car settings"),
            packageTokens = setOf("carsettings"),
        ),
        "app.android_settings.open" to AliceAppTarget.App(
            packages = listOf("com.android.settings"),
            labels = setOf("settings", "настройки"),
            packageTokens = setOf("android.settings"),
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
                "com.ss.android.ugc.aweme",
            ),
            labels = setOf("tiktok", "tik tok", "тикток", "тик ток"),
            packageTokens = setOf("tiktok", "musically", "ugc.trill", "ugc.aweme"),
        ),
    )

    // Names of navigation apps are not here: NavigatorAppNames owns them for every assistant.
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
        "yandex music" to "app.music.open",
        "музыка" to "app.music.open",
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
