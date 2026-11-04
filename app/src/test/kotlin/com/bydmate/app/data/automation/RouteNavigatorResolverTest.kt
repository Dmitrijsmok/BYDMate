package com.bydmate.app.data.automation

import com.bydmate.app.data.automation.RouteNavigatorDiscovery.LauncherApp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Which app and package a navigate action and an «open the navigator» get, from the setting. */
class RouteNavigatorResolverTest {

    private fun choice(navigator: String, manual: String? = null) = NavigatorChoice(navigator, manual)

    private fun installed(vararg pairs: Pair<String, String>): (String) -> String? = pairs.toMap()::get

    @Test fun `the chosen app installed is pinned to the package it is installed under`() {
        assertEquals(
            NavigatorTarget(RouteNavigatorUris.WAZE, "com.waze"),
            RouteNavigatorResolver.resolve(choice(RouteNavigatorUris.WAZE), null,
                installed(RouteNavigatorUris.WAZE to "com.waze")),
        )
    }

    @Test fun `the chosen app missing falls back to yandex and says which`() {
        assertEquals(
            NavigatorTarget(RouteNavigatorUris.YANDEX, null, fellBackFrom = RouteNavigatorUris.WAZE),
            RouteNavigatorResolver.resolve(choice(RouteNavigatorUris.WAZE), null, installed()),
        )
    }

    /** Field build 64023: an "installed" check said a working Waze was missing. A package the
     *  driver typed in is used as given, with no check that could be wrong the same way. */
    @Test fun `a manual package is used as given, not probed`() {
        val target = RouteNavigatorResolver.resolve(choice(RouteNavigatorUris.WAZE, "com.vendor.waze"), null) {
            error("a manual package must not be probed")
        }
        assertEquals(NavigatorTarget(RouteNavigatorUris.WAZE, "com.vendor.waze"), target)
    }

    @Test fun `a manual package never takes a command that names another app`() {
        val target = RouteNavigatorResolver.resolve(
            choice(RouteNavigatorUris.WAZE, "com.vendor.waze"), RouteNavigatorUris.MAPS, installed())
        assertEquals(NavigatorTarget(RouteNavigatorUris.MAPS, null), target)
    }

    @Test fun `yandex is never probed and stays unpinned`() {
        val target = RouteNavigatorResolver.resolve(choice(RouteNavigatorUris.YANDEX), null) {
            error("Yandex Navigator links resolve by scheme")
        }
        assertEquals(NavigatorTarget(RouteNavigatorUris.YANDEX, null), target)
    }

    @Test fun `maps chosen and installed stays unpinned so any store variant takes it`() {
        assertEquals(
            NavigatorTarget(RouteNavigatorUris.MAPS, null),
            RouteNavigatorResolver.resolve(choice(RouteNavigatorUris.MAPS), null,
                installed(RouteNavigatorUris.MAPS to "ru.yandex.yandexmaps.rustore")),
        )
    }

    @Test fun `maps named by the command is not probed`() {
        val target = RouteNavigatorResolver.resolve(choice(RouteNavigatorUris.DGIS), RouteNavigatorUris.MAPS) {
            error("app=maps resolves by scheme")
        }
        assertEquals(NavigatorTarget(RouteNavigatorUris.MAPS, null), target)
    }

    @Test fun `launch candidates put the manual package first and fall back to yandex for the setting`() {
        val launcher = listOf(LauncherApp("com.vendor.navi", "Waze"))
        assertEquals(
            listOf("com.manual.waze", "com.waze", "com.vendor.navi") + RouteNavigatorDiscovery.knownPackages(
                RouteNavigatorUris.YANDEX),
            RouteNavigatorResolver.launchCandidates(choice(RouteNavigatorUris.WAZE, "com.manual.waze"), null, launcher),
        )
    }

    @Test fun `launch candidates of a named app keep to that app`() {
        val candidates = RouteNavigatorResolver.launchCandidates(
            choice(RouteNavigatorUris.WAZE, "com.manual.waze"), RouteNavigatorUris.YANDEX, emptyList())
        assertEquals(RouteNavigatorDiscovery.knownPackages(RouteNavigatorUris.YANDEX), candidates)
    }

    @Test fun `a package is told apart by its app`() {
        assertEquals(RouteNavigatorUris.WAZE, RouteNavigatorDiscovery.navigatorOf("com.waze"))
        assertEquals(RouteNavigatorUris.DGIS, RouteNavigatorDiscovery.navigatorOf("ru.dublgis.dgismobile"))
        assertEquals(RouteNavigatorUris.MAPS, RouteNavigatorDiscovery.navigatorOf("ru.yandex.yandexmaps.rustore"))
        assertEquals(RouteNavigatorUris.YANDEX, RouteNavigatorDiscovery.navigatorOf("ru.yandex.yandexnavi.inhouse"))
        assertNull(RouteNavigatorDiscovery.navigatorOf("com.example.player"))
    }

    /** ReVanced, RVX and other MicroG builds of Google Maps are Google Maps (fork da8209b1). */
    @Test fun `google maps builds are told by their package`() {
        assertEquals(RouteNavigatorUris.GOOGLE_MAPS, RouteNavigatorDiscovery.navigatorOf("app.revanced.android.apps.maps"))
        assertEquals(RouteNavigatorUris.GOOGLE_MAPS, RouteNavigatorDiscovery.navigatorOf("app.rvx.android.apps.maps"))
        assertEquals(RouteNavigatorUris.GOOGLE_MAPS, RouteNavigatorDiscovery.navigatorOf("com.google.android.apps.maps"))
        // MicroG itself is not a map app.
        assertNull(RouteNavigatorDiscovery.navigatorOf("app.revanced.android.gms"))
    }

    /** Google Maps is labelled a bare «Карты» in Russian: that must not make it Yandex Maps, and
     *  Yandex Maps must not pass for Google Maps. */
    @Test fun `the russian google maps label does not collide with yandex maps`() {
        assertEquals(false, RouteNavigatorDiscovery.matches(RouteNavigatorUris.MAPS, "com.google.android.apps.maps", "Карты"))
        assertEquals(true, RouteNavigatorDiscovery.matches(RouteNavigatorUris.GOOGLE_MAPS, "com.google.android.apps.maps", "Карты"))
        assertEquals(false, RouteNavigatorDiscovery.matches(RouteNavigatorUris.GOOGLE_MAPS, "ru.yandex.yandexmaps", "Яндекс Карты"))
        assertEquals(false, RouteNavigatorDiscovery.matches(RouteNavigatorUris.GOOGLE_MAPS, "com.vendor.maps", "Карты"))
    }

    @Test fun `google maps missing falls back to yandex and says which`() {
        assertEquals(
            NavigatorTarget(RouteNavigatorUris.YANDEX, null, fellBackFrom = RouteNavigatorUris.GOOGLE_MAPS),
            RouteNavigatorResolver.resolve(choice(RouteNavigatorUris.GOOGLE_MAPS), null, installed()),
        )
    }

    /** "Яндекс Карты и Навигатор" is the Maps app; the Navigator is not told by one shared word. */
    @Test fun `labels tell maps from the navigator`() {
        assertEquals(true, RouteNavigatorDiscovery.matches(RouteNavigatorUris.MAPS, "x.y", "Яндекс Карты и Навигатор"))
        assertEquals(false, RouteNavigatorDiscovery.matches(RouteNavigatorUris.YANDEX, "x.y", "Яндекс Карты и Навигатор"))
        assertEquals(true, RouteNavigatorDiscovery.matches(RouteNavigatorUris.DGIS, "x.y", "2ГИС"))
        assertEquals(true, RouteNavigatorDiscovery.matches(RouteNavigatorUris.WAZE, "x.y", "Waze"))
        assertEquals(false, RouteNavigatorDiscovery.matches(RouteNavigatorUris.WAZE, "x.y", "Waze Carpool helper"))
    }
}
