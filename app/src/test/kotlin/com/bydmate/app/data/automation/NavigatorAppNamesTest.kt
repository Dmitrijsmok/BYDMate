package com.bydmate.app.data.automation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** One name table for every assistant: the generic word is the chosen app, a name is that app. */
class NavigatorAppNamesTest {

    @Test fun `the generic words mean the app chosen in settings`() {
        listOf("навигатор", "Навигация", "навигацию", " Navigator ").forEach {
            assertEquals(it, NavigatorAppNames.DEFAULT, NavigatorAppNames.of(it))
        }
    }

    /** Fork 64da6949: an explicit Waze or Google Maps stays explicit. */
    @Test fun `an app name is that app`() {
        assertEquals(RouteNavigatorUris.WAZE, NavigatorAppNames.of("Waze"))
        assertEquals(RouteNavigatorUris.WAZE, NavigatorAppNames.of("вейз"))
        assertEquals(RouteNavigatorUris.GOOGLE_MAPS, NavigatorAppNames.of("Google Maps"))
        assertEquals(RouteNavigatorUris.GOOGLE_MAPS, NavigatorAppNames.of("гугл  карты"))
        assertEquals(RouteNavigatorUris.GOOGLE_MAPS, NavigatorAppNames.of("карты Google"))
        assertEquals(RouteNavigatorUris.YANDEX, NavigatorAppNames.of("Яндекс Навигатор"))
        assertEquals(RouteNavigatorUris.MAPS, NavigatorAppNames.of("Яндекс Карты"))
        assertEquals(RouteNavigatorUris.DGIS, NavigatorAppNames.of("2ГИС"))
    }

    /** A bare «карты» keeps meaning Yandex Maps, as the upstream alias had it. */
    @Test fun `bare maps is yandex maps`() {
        assertEquals(RouteNavigatorUris.MAPS, NavigatorAppNames.of("карты"))
    }

    @Test fun `other apps and fragments are not navigation apps`() {
        assertNull(NavigatorAppNames.of("музыка"))
        assertNull(NavigatorAppNames.of("карт"))
        assertNull(NavigatorAppNames.of("навигатор на приборку"))
        assertNull(NavigatorAppNames.of(""))
    }
}
