package com.bydmate.app.data.remote

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

    @Test fun `every diagnostic action resolves to a target`() {
        AliceAppCatalog.diagnosticActions.forEach { action ->
            assertTrue(action, AliceAppCatalog.forAction(action) != null)
        }
    }
}
