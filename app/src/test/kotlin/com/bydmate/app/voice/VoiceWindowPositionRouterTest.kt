package com.bydmate.app.voice

import org.junit.Assert.assertEquals
import org.junit.Test

class VoiceWindowPositionRouterTest {
    @Test fun aggregate_detents_fan_out_through_closed_loop_controller() {
        assertEquals(
            listOf(
                VoiceWindowPositionRouter.Request("window.driver.position", 10),
                VoiceWindowPositionRouter.Request("window.passenger.position", 10),
                VoiceWindowPositionRouter.Request("window.rear_left.position", 10),
                VoiceWindowPositionRouter.Request("window.rear_right.position", 10),
            ),
            VoiceWindowPositionRouter.resolve("车窗通风"),
        )
        assertEquals(
            listOf(
                VoiceWindowPositionRouter.Request("window.driver.position", 50),
                VoiceWindowPositionRouter.Request("window.passenger.position", 50),
                VoiceWindowPositionRouter.Request("window.rear_left.position", 50),
                VoiceWindowPositionRouter.Request("window.rear_right.position", 50),
            ),
            VoiceWindowPositionRouter.resolve("车窗半开"),
        )
    }

    @Test fun front_and_rear_detents_target_only_requested_axle() {
        assertEquals(
            listOf(
                VoiceWindowPositionRouter.Request("window.driver.position", 10),
                VoiceWindowPositionRouter.Request("window.passenger.position", 10),
            ),
            VoiceWindowPositionRouter.resolve("前排车窗通风"),
        )
        assertEquals(
            listOf(
                VoiceWindowPositionRouter.Request("window.rear_left.position", 50),
                VoiceWindowPositionRouter.Request("window.rear_right.position", 50),
            ),
            VoiceWindowPositionRouter.resolve("后排车窗半开"),
        )
    }

    @Test fun individual_detents_keep_closed_loop_positioning() {
        assertEquals(
            listOf(VoiceWindowPositionRouter.Request("window.driver.position", 10)),
            VoiceWindowPositionRouter.resolve("主驾通风"),
        )
        assertEquals(
            listOf(VoiceWindowPositionRouter.Request("window.passenger.position", 50)),
            VoiceWindowPositionRouter.resolve("副驾半开"),
        )
    }

    @Test fun explicit_individual_percentage_keeps_closed_loop_positioning() {
        assertEquals(
            listOf(VoiceWindowPositionRouter.Request("window.rear_right.position", 37)),
            VoiceWindowPositionRouter.resolve("后右打开37"),
        )
    }
}
