package com.bydmate.app.cluster

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SteeringWheelKeyDecisionVoiceTest {
    @Test fun triggers_on_configured_voice_key_down() {
        assertEquals(VoiceKeyDecision.TRIGGER, voiceDecision(320, isDown = true, voiceEnabled = true, voiceKeyCode = 320))
    }
    // The matching key's UP edge must be CONSUMEd, not IGNOREd — otherwise it falls through
    // to the native BYD assistant, which owns the same hardware keycode (320).
    @Test fun consumes_key_up_when_matched_and_enabled() {
        assertEquals(VoiceKeyDecision.CONSUME, voiceDecision(320, isDown = false, voiceEnabled = true, voiceKeyCode = 320))
    }
    @Test fun ignores_key_up_when_voice_disabled() {
        assertEquals(VoiceKeyDecision.IGNORE, voiceDecision(320, isDown = false, voiceEnabled = false, voiceKeyCode = 320))
    }
    @Test fun ignores_when_voice_disabled() {
        assertEquals(VoiceKeyDecision.IGNORE, voiceDecision(320, isDown = true, voiceEnabled = false, voiceKeyCode = 320))
    }
    @Test fun ignores_other_keys() {
        assertEquals(VoiceKeyDecision.IGNORE, voiceDecision(351, isDown = true, voiceEnabled = true, voiceKeyCode = 320))
    }
    @Test fun ignores_other_keys_key_up() {
        assertEquals(VoiceKeyDecision.IGNORE, voiceDecision(351, isDown = false, voiceEnabled = true, voiceKeyCode = 320))
    }

    // Atto 3 (DiLink 3.0): one press of the mic button sends 304 and 327, and the stock assistant
    // reacts to 327. The learned press keeps the first code as primary and the other as a companion.
    @Test fun primary_down_triggers_and_up_is_consumed_with_companions() {
        assertEquals(VoiceKeyDecision.TRIGGER, voiceDecision(304, isDown = true, voiceEnabled = true, voiceKeyCode = 304, companions = setOf(327)))
        assertEquals(VoiceKeyDecision.CONSUME, voiceDecision(304, isDown = false, voiceEnabled = true, voiceKeyCode = 304, companions = setOf(327)))
    }
    @Test fun companion_down_and_up_are_consumed_never_triggered() {
        assertEquals(VoiceKeyDecision.CONSUME, voiceDecision(327, isDown = true, voiceEnabled = true, voiceKeyCode = 304, companions = setOf(327)))
        assertEquals(VoiceKeyDecision.CONSUME, voiceDecision(327, isDown = false, voiceEnabled = true, voiceKeyCode = 304, companions = setOf(327)))
    }
    @Test fun reverse_roles_trigger_on_the_primary_only() {
        assertEquals(VoiceKeyDecision.TRIGGER, voiceDecision(327, isDown = true, voiceEnabled = true, voiceKeyCode = 327, companions = setOf(304)))
        assertEquals(VoiceKeyDecision.CONSUME, voiceDecision(327, isDown = false, voiceEnabled = true, voiceKeyCode = 327, companions = setOf(304)))
        assertEquals(VoiceKeyDecision.CONSUME, voiceDecision(304, isDown = true, voiceEnabled = true, voiceKeyCode = 327, companions = setOf(304)))
        assertEquals(VoiceKeyDecision.CONSUME, voiceDecision(304, isDown = false, voiceEnabled = true, voiceKeyCode = 327, companions = setOf(304)))
    }
    @Test fun voice_disabled_ignores_primary_and_companion() {
        for (code in listOf(304, 327)) for (down in listOf(true, false)) {
            assertEquals(VoiceKeyDecision.IGNORE, voiceDecision(code, isDown = down, voiceEnabled = false, voiceKeyCode = 304, companions = setOf(327)))
        }
    }
    @Test fun other_keys_are_ignored_with_companions() {
        assertEquals(VoiceKeyDecision.IGNORE, voiceDecision(351, isDown = true, voiceEnabled = true, voiceKeyCode = 304, companions = setOf(327)))
        assertEquals(VoiceKeyDecision.IGNORE, voiceDecision(351, isDown = false, voiceEnabled = true, voiceKeyCode = 304, companions = setOf(327)))
    }
    // Every car with a single-code button stores no companions: the results must stay the old ones.
    @Test fun empty_companions_keep_single_code_results() {
        val cases = listOf(
            Triple(320, true, true) to VoiceKeyDecision.TRIGGER,
            Triple(320, false, true) to VoiceKeyDecision.CONSUME,
            Triple(320, false, false) to VoiceKeyDecision.IGNORE,
            Triple(320, true, false) to VoiceKeyDecision.IGNORE,
            Triple(351, true, true) to VoiceKeyDecision.IGNORE,
            Triple(351, false, true) to VoiceKeyDecision.IGNORE,
        )
        for ((input, expected) in cases) {
            val (code, down, enabled) = input
            assertEquals(expected, voiceDecision(code, isDown = down, voiceEnabled = enabled, voiceKeyCode = 320, companions = emptySet()))
        }
    }

    @Test fun companions_csv_round_trip() {
        for (set in listOf(emptySet(), setOf(327), setOf(304, 327))) {
            assertEquals(set, voiceCompanionsFromCsv(voiceCompanionsToCsv(set)))
        }
        assertEquals("", voiceCompanionsToCsv(emptySet()))
        assertEquals("304,327", voiceCompanionsToCsv(setOf(327, 304)))
    }
    @Test fun companions_csv_garbage_reads_as_empty() {
        for (garbage in listOf(null, "", ",", "abc", "327,abc", "327,", "-5", "0")) {
            assertEquals("input=$garbage", emptySet<Int>(), voiceCompanionsFromCsv(garbage))
        }
    }

    @Test fun dilink3_304_triggers_selected_voice_provider_on_down() {
        assertEquals(VoiceKeyDecision.TRIGGER, diLink3VoiceDecision(304, isDown = true, voiceEnabled = true))
    }

    @Test fun dilink3_304_consumes_up_edge() {
        assertEquals(VoiceKeyDecision.CONSUME, diLink3VoiceDecision(304, isDown = false, voiceEnabled = true))
    }

    @Test fun dilink3_327_is_consumed_while_voice_enabled() {
        assertEquals(VoiceKeyDecision.CONSUME, diLink3VoiceDecision(327, isDown = true, voiceEnabled = true))
        assertEquals(VoiceKeyDecision.CONSUME, diLink3VoiceDecision(327, isDown = false, voiceEnabled = true))
    }

    @Test fun dilink3_special_codes_pass_through_when_voice_disabled() {
        assertEquals(VoiceKeyDecision.IGNORE, diLink3VoiceDecision(304, isDown = true, voiceEnabled = false))
        assertEquals(VoiceKeyDecision.IGNORE, diLink3VoiceDecision(327, isDown = true, voiceEnabled = false))
    }
    @Test fun local_voice_second_press_within_window_is_double_press() {
        assertTrue(isVoiceDoublePress(previousDownMs = 1_000L, nowMs = 1_400L))
    }

    @Test fun local_voice_press_after_window_is_normal_press() {
        assertFalse(isVoiceDoublePress(previousDownMs = 1_000L, nowMs = 1_401L))
    }

    /** Field 1.1.1: a relaxed double press is 300-400 ms apart; 250 ms took it for two singles. */
    @Test fun a_relaxed_double_press_still_reaches_alice() {
        assertEquals(400L, VOICE_DOUBLE_PRESS_WINDOW_MS)
        assertTrue(isVoiceDoublePress(previousDownMs = 1_000L, nowMs = 1_350L))
    }

    @Test fun local_starts_at_the_end_of_the_press_window_however_late_the_press_is_handled() {
        assertEquals(400L, localVoiceStartDelayMs(downMs = 1_000L, nowMs = 1_000L))
        assertEquals(100L, localVoiceStartDelayMs(downMs = 1_000L, nowMs = 1_300L))
        assertEquals(0L, localVoiceStartDelayMs(downMs = 1_000L, nowMs = 2_000L))
        // A clock that disagrees (a press time after "now") never waits more than the window.
        assertEquals(400L, localVoiceStartDelayMs(downMs = 2_000L, nowMs = 1_000L))
    }

    @Test fun first_local_voice_press_is_never_double_press() {
        assertFalse(isVoiceDoublePress(previousDownMs = 0L, nowMs = 100L))
    }

    @Test fun yandex_context_routes_single_press_to_alice() {
        assertEquals(
            VoicePressRoute.ALICE,
            voicePressRoute(
                repeatCount = 0,
                aliceContextActive = true,
                keyCode = 304,
                previous = VoicePressMemory(-1, 0L),
                nowMs = 10_000L,
            ),
        )
    }

    @Test fun outside_yandex_context_first_press_routes_to_local() {
        assertEquals(
            VoicePressRoute.LOCAL,
            voicePressRoute(
                repeatCount = 0,
                aliceContextActive = false,
                keyCode = 304,
                previous = VoicePressMemory(-1, 0L),
                nowMs = 10_000L,
            ),
        )
    }

    @Test fun yandex_browser_and_navigator_are_alice_contexts() {
        assertTrue(isAliceContextPackage("com.yandex.browser"))
        assertTrue(isAliceContextPackage("ru.yandex.yandexnavi"))
        assertFalse(isAliceContextPackage("com.bydmate.app"))
    }

}
