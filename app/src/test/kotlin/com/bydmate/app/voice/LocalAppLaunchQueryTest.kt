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

    private fun closeTarget(text: String) = LocalAppLaunchQuery.matchClose(text)?.target

    @Test fun apps_of_the_table_are_closed_by_name() {
        val tiktok = AliceAppCatalog.forAction("app.tiktok.open")
        assertEquals(tiktok, closeTarget("закрой тик ток"))
        assertEquals(tiktok, closeTarget("выключи тикток"))
        assertEquals(tiktok, closeTarget("закрой приложение тикток"))
        assertEquals(AliceAppCatalog.forAction("app.youtube.open"), closeTarget("закрой пожалуйста ютуб"))
        assertEquals("тик ток", LocalAppLaunchQuery.matchClose("Закрой тик ток")?.name)
        assertEquals(AliceAppTarget.Navigator(null), closeTarget("закрой навигатор"))
    }

    @Test fun close_takes_only_exact_app_names() {
        assertNull(closeTarget("закрой окна"))
        assertNull(closeTarget("закрой окно водителя"))
        assertNull(closeTarget("закрой люк"))
        assertNull(closeTarget("закрой багажник"))
        assertNull(closeTarget("выключи свет"))
        assertNull(closeTarget("закрой калькулятор"))
        assertNull(closeTarget("закрой тикток и ютуб"))
        assertNull(closeTarget("открой тикток"))
        assertNull(closeTarget("закрой"))
    }

    @Test fun settings_bydmate_and_sentry_are_never_closed() {
        assertNull(closeTarget("закрой настройки"))
        assertNull(closeTarget("закрой bydmate"))
        assertNull(closeTarget("выключи охрану"))
        assertNull(closeTarget("выключи часовой"))
    }

    @Test fun open_never_matches_a_close_phrase() {
        assertNull(target("закрой тикток"))
        assertNull(target("выключи ютуб"))
    }
}
