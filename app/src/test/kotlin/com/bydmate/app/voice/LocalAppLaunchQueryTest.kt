package com.bydmate.app.voice

import com.bydmate.app.data.remote.AliceAppCatalog
import com.bydmate.app.data.remote.AliceAppTarget
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Fork df875e49, adapted: the offline «открой <приложение>» takes closed-set names only. */
class LocalAppLaunchQueryTest {

    private fun target(text: String) = LocalAppLaunchQuery.match(text)?.target

    @Test fun known_apps_are_extracted_with_the_shared_table() {
        assertEquals(AliceAppCatalog.forAction("app.tiktok.open"), target("открой тикток"))
        assertEquals(AliceAppCatalog.forAction("app.tiktok.open"), target("запусти тик ток"))
        assertEquals(AliceAppCatalog.forAction("app.youtube.open"), target("открой приложение YouTube"))
        assertEquals(AliceAppCatalog.forAction("app.youtube.open"), target("открой пожалуйста ютуб"))
        assertEquals(AliceAppCatalog.forAction("app.camera.open"), target("открой камеру"))
        assertEquals("ютуб", LocalAppLaunchQuery.match("Открой ютуб")?.name)
    }

    @Test fun settings_screens_are_extracted() {
        assertEquals(AliceAppTarget.Settings("wifi"), target("открой настройки wi-fi"))
        assertEquals(AliceAppTarget.Settings("car"), target("открой настройки машины"))
        assertEquals(AliceAppTarget.Settings("bluetooth"), target("запусти настройки блютус"))
    }

    @Test fun navigation_apps_stay_with_the_dictionary_navigator() {
        assertNull(target("открой навигатор"))
        assertNull(target("открой гугл карты"))
        assertNull(target("запусти приложение вейз"))
    }

    @Test fun anything_else_goes_to_the_agent() {
        assertNull(target("открой калькулятор"))
        assertNull(target("открой ютуб и включи музыку"))
        assertNull(target("открой окно"))
        assertNull(target("построй маршрут домой"))
        assertNull(target("температура в машине"))
        assertNull(target("тикток"))
        assertNull(target("открой"))
        assertNull(target("включи тикток"))
    }
}
