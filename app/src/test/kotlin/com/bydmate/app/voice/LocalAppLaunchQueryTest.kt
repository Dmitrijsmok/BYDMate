package com.bydmate.app.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class LocalAppLaunchQueryTest {
    @Test fun russian_google_maps_is_extracted() {
        assertEquals("google maps", LocalAppLaunchQuery.target("открой Google Maps", VoiceLang.RU))
        assertEquals("гугл карты", LocalAppLaunchQuery.target("запусти гугл карты", VoiceLang.RU))
    }

    @Test fun app_prefix_is_supported() {
        assertEquals("youtube", LocalAppLaunchQuery.target("открой приложение YouTube", VoiceLang.RU))
    }

    @Test fun non_launch_query_is_not_captured() {
        assertNull(LocalAppLaunchQuery.target("построй маршрут домой", VoiceLang.RU))
        assertNull(LocalAppLaunchQuery.target("температура в машине", VoiceLang.RU))
    }

    @Test fun english_launch_is_extracted() {
        assertEquals("google maps", LocalAppLaunchQuery.target("open Google Maps", VoiceLang.EN))
    }
}
