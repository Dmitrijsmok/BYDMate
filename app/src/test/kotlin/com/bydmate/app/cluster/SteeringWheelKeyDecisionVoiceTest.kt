package com.bydmate.app.cluster

import org.junit.Assert.assertEquals
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

    @Test fun dilink3_304_down_triggers_local_voice() {
        assertEquals(
            VoiceKeyDecision.TRIGGER,
            diLink3VoiceDecision(304, isDown = true, voiceEnabled = true),
        )
    }

    @Test fun dilink3_304_up_is_consumed() {
        assertEquals(
            VoiceKeyDecision.CONSUME,
            diLink3VoiceDecision(304, isDown = false, voiceEnabled = true),
        )
    }

    @Test fun dilink3_327_is_consumed_on_both_edges() {
        assertEquals(
            VoiceKeyDecision.CONSUME,
            diLink3VoiceDecision(327, isDown = true, voiceEnabled = true),
        )
        assertEquals(
            VoiceKeyDecision.CONSUME,
            diLink3VoiceDecision(327, isDown = false, voiceEnabled = true),
        )
    }

    @Test fun dilink3_aliases_pass_through_when_voice_is_disabled() {
        assertEquals(
            VoiceKeyDecision.IGNORE,
            diLink3VoiceDecision(304, isDown = true, voiceEnabled = false),
        )
        assertEquals(
            VoiceKeyDecision.IGNORE,
            diLink3VoiceDecision(327, isDown = true, voiceEnabled = false),
        )
    }

    @Test fun dilink3_alias_gate_does_not_capture_unrelated_keys() {
        assertEquals(
            VoiceKeyDecision.IGNORE,
            diLink3VoiceDecision(320, isDown = true, voiceEnabled = true),
        )
        assertEquals(
            VoiceKeyDecision.IGNORE,
            diLink3VoiceDecision(351, isDown = true, voiceEnabled = true),
        )
    }

}
