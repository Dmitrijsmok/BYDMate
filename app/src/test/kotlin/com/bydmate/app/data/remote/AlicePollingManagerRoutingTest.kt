package com.bydmate.app.data.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AlicePollingManagerRoutingTest {

    @Test
    fun `agent fallback is automotive only`() {
        assertTrue(AliceLocalCommandRouter.isAutomotiveAgentQuery("Почему зимой у BYD выше расход?"))
        assertTrue(AliceLocalCommandRouter.isAutomotiveAgentQuery("Какой сейчас заряд батареи машины?"))
        assertTrue(AliceLocalCommandRouter.isAutomotiveAgentQuery("Как работает холодильник в BYD?"))
        assertTrue(AliceLocalCommandRouter.isAutomotiveAgentQuery("Почему не включаются ДХО?"))
        assertTrue(AliceLocalCommandRouter.isAutomotiveAgentQuery("Что такое frunk?"))
        assertFalse(AliceLocalCommandRouter.isAutomotiveAgentQuery("Расскажи, почему зимой день короче"))
        assertFalse(AliceLocalCommandRouter.isAutomotiveAgentQuery("Какая сегодня погода в Риге?"))
    }

    @Test
    fun `all historical Alice navigation actions are disabled`() {
        listOf(
            "navigation.route",
            "navigation.search",
            "navigation.show",
            "navigation.cluster_on",
            "navigation.cluster_off",
            "app.navigation.open",
            "app.waze.open",
            "app.yandex_navi.open",
            "app.yandex_maps.open",
            "app.google_maps.open",
            "app.dgis.open",
        ).forEach { action ->
            assertTrue("must reject stale Alice navigation action: $action",
                AliceLocalCommandRouter.isNavigationAction(action))
        }
        assertFalse(AliceLocalCommandRouter.isNavigationAction("app.youtube.open"))
    }

    @Test
    fun `navigation prompts are rejected before automotive agent fallback`() {
        assertTrue(AliceLocalCommandRouter.isNavigationText("построй маршрут до аэропорта"))
        assertTrue(AliceLocalCommandRouter.isNavigationText("открой Google Maps"))
        assertTrue(AliceLocalCommandRouter.isNavigationText("запусти Яндекс Навигатор"))
        assertFalse(AliceLocalCommandRouter.isNavigationText("какой сейчас заряд батареи"))
    }

    @Test
    fun `delegated vehicle commands stay deterministic`() {
        assertEquals("前备箱打开", AliceLocalCommandRouter.directVehicleCommand("открой передний багажник"))
        assertEquals("前备箱关闭", AliceLocalCommandRouter.directVehicleCommand("закрой frunk"))
        assertEquals("双闪打开", AliceLocalCommandRouter.directVehicleCommand("включи аварийку"))
        assertEquals("双闪关闭", AliceLocalCommandRouter.directVehicleCommand("выключи аварийные огни"))
        assertEquals("车门解锁", AliceLocalCommandRouter.directVehicleCommand("открой двери"))
        assertEquals("车门上锁", AliceLocalCommandRouter.directVehicleCommand("запри двери"))
    }

    @Test
    fun `fridge and rear defrost do not need agent`() {
        assertEquals("冰箱制冷-3度", AliceLocalCommandRouter.directVehicleCommand("охлади холодильник до -3 градусов"))
        assertEquals("冰箱制热40度", AliceLocalCommandRouter.directVehicleCommand("подогрей холодильник до 40 градусов"))
        assertEquals("冰箱关闭", AliceLocalCommandRouter.directVehicleCommand("выключи холодильник"))
        assertEquals("后视镜加热", AliceLocalCommandRouter.directVehicleCommand("включи обогрев заднего стекла"))
        assertNull(AliceLocalCommandRouter.directVehicleCommand("расскажи про батарею"))
    }
}
