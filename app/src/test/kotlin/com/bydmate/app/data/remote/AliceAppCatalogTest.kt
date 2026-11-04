package com.bydmate.app.data.remote

import com.bydmate.app.data.automation.RouteNavigatorDiscovery
import com.bydmate.app.data.automation.RouteNavigatorUris
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AliceAppCatalogTest {

    @Test fun `navigator app actions open the shared navigator table, the generic one the chosen app`() {
        assertEquals(AliceAppTarget.Navigator(null), AliceAppCatalog.forAction("app.navigation.open"))
        assertEquals(AliceAppTarget.Navigator(RouteNavigatorUris.WAZE), AliceAppCatalog.forAction("app.waze.open"))
        assertEquals(AliceAppTarget.Navigator(RouteNavigatorUris.GOOGLE_MAPS), AliceAppCatalog.forAction("app.google_maps.open"))
        assertEquals(AliceAppTarget.Navigator(RouteNavigatorUris.YANDEX), AliceAppCatalog.forAction("app.yandex_navi.open"))
        assertEquals(AliceAppTarget.Navigator(RouteNavigatorUris.MAPS), AliceAppCatalog.forAction("app.yandex_maps.open"))
        assertEquals(AliceAppTarget.Navigator(RouteNavigatorUris.DGIS), AliceAppCatalog.forAction("app.dgis.open"))
    }

    @Test fun `spoken navigator names mean the same app as for the local assistant`() {
        // «навигатор» is the app chosen in settings (fork 9ac7d503), a named app stays that app.
        assertEquals(AliceAppTarget.Navigator(null), AliceAppCatalog.forName("навигатор"))
        assertEquals(AliceAppTarget.Navigator(null), AliceAppCatalog.forName("Навигация"))
        assertEquals(AliceAppTarget.Navigator(RouteNavigatorUris.YANDEX), AliceAppCatalog.forName("яндекс навигатор"))
        assertEquals(AliceAppTarget.Navigator(RouteNavigatorUris.GOOGLE_MAPS), AliceAppCatalog.forName("гугл карты"))
        assertEquals(AliceAppTarget.Navigator(RouteNavigatorUris.WAZE), AliceAppCatalog.forName("вейз"))
    }

    @Test fun `alternative YouTube and TikTok builds are found by package token`() {
        val youtube = AliceAppCatalog.forName("ютуб") as AliceAppTarget.App
        assertTrue("app.revanced.android.youtube" in youtube.packages)
        assertTrue("app.rvx.android.youtube" in youtube.packages)
        assertTrue("youtube" in youtube.packageTokens)
        val tiktok = AliceAppCatalog.forName("Тик Ток") as AliceAppTarget.App
        assertTrue("com.zhiliaoapp.musically" in tiktok.packages)
        assertEquals(AliceAppTarget.Self, AliceAppCatalog.forName("BYDMate"))
    }

    @Test fun `an unknown name is looked up by launcher label and package token`() {
        assertEquals(
            AliceAppTarget.App(labels = setOf("telegram x"), packageTokens = setOf("telegramx")),
            AliceAppCatalog.forName(" Telegram  X "),
        )
        assertEquals(AliceAppTarget.App(labels = setOf("vk")), AliceAppCatalog.forName("VK"))
    }

    private fun app(label: String, pkg: String) = RouteNavigatorDiscovery.LauncherApp(pkg, label)

    @Test fun `a known package wins in the catalog's order, then the exact label, then a contained one`() {
        val youtube = AliceAppCatalog.forName("ютуб") as AliceAppTarget.App
        // Only the RVX build is installed: found by its package, not by a label search.
        assertEquals(listOf("app.rvx.android.youtube"),
            AliceAppCatalog.pick(youtube, listOf(app("YouTube RVX", "app.rvx.android.youtube"))).map { it.packageName })
        // A ReVanced build under a vendor package: its package token says YouTube.
        assertEquals(listOf("com.vendor.youtube.patched"),
            AliceAppCatalog.pick(youtube, listOf(app("Видео", "com.vendor.youtube.patched"))).map { it.packageName })
        // Stock YouTube beats an alternative build when both are there.
        assertEquals(listOf("com.google.android.youtube"), AliceAppCatalog.pick(youtube, listOf(
            app("YouTube ReVanced", "app.revanced.android.youtube"), app("YouTube", "com.google.android.youtube"),
        )).map { it.packageName })
    }

    @Test fun `a Cyrillic name finds the Latin launcher label`() {
        val tiktok = AliceAppCatalog.forName("тикток") as AliceAppTarget.App
        assertEquals(listOf("com.example.tiktok.lite"),
            AliceAppCatalog.pick(tiktok, listOf(app("TikTok Lite", "com.example.tiktok.lite"))).map { it.packageName })
        assertEquals(tiktok, AliceAppCatalog.forName("тик-ток"))
        assertTrue("com.zhiliaoapp.musically.go" in tiktok.packages)
    }

    @Test fun `an unknown name matches every app that contains it, one per package`() {
        val apps = listOf(app("Карты", "ru.example.maps"), app("Карточки", "com.example.cards"),
            app("Карточки", "com.example.cards"))
        assertEquals(listOf("ru.example.maps", "com.example.cards"),
            AliceAppCatalog.pick(AliceAppCatalog.byLabel("карт"), apps).map { it.packageName })
        assertEquals(listOf("ru.example.maps"),
            AliceAppCatalog.pick(AliceAppCatalog.byLabel("Карты"), apps).map { it.packageName })
        assertTrue(AliceAppCatalog.pick(AliceAppCatalog.byLabel("калькулятор"), apps).isEmpty())
    }

    @Test fun `settings screens are a closed set of sections`() {
        assertEquals(AliceAppTarget.Settings("car"), AliceAppCatalog.forName("настройки машины"))
        assertEquals(AliceAppTarget.Settings("wifi"), AliceAppCatalog.forName("настройки wi fi"))
        assertEquals(AliceAppTarget.Settings("android"), AliceAppCatalog.forName("Настройки"))
        assertEquals(AliceAppTarget.Settings("car"), AliceAppCatalog.forAction("app.car_settings.open"))
        assertEquals(null, AliceAppCatalog.settingsSection("настройки кофеварки"))
        listOf("car", "display", "android", "wifi", "bluetooth", "sound", "apps").forEach {
            assertTrue(it, it in AliceAppCatalog.SETTINGS_SECTIONS)
        }
    }

    @Test fun `the closed set holds known names only, the open set every name`() {
        assertEquals(AliceAppCatalog.forAction("app.camera.open"), AliceAppCatalog.known("камеру"))
        assertEquals(AliceAppCatalog.forAction("app.chrome.open"), AliceAppCatalog.known("хром"))
        assertEquals(null, AliceAppCatalog.known("калькулятор"))
        assertEquals(AliceAppCatalog.byLabel("калькулятор"), AliceAppCatalog.forName("калькулятор"))
    }

    @Test fun `Settings lists the spoken names of an action`() {
        assertTrue(AliceAppCatalog.spokenNames("app.tiktok.open").containsAll(listOf("тикток", "тик ток")))
        assertTrue("вейз" in AliceAppCatalog.spokenNames("app.waze.open"))
        assertTrue("навигатор" in AliceAppCatalog.spokenNames("app.navigation.open"))
        assertTrue("настройки машины" in AliceAppCatalog.spokenNames("app.car_settings.open"))
    }

    @Test fun `every diagnostic action resolves to a target`() {
        AliceAppCatalog.diagnosticActions.forEach { action ->
            assertTrue(action, AliceAppCatalog.forAction(action) != null)
        }
    }
}
