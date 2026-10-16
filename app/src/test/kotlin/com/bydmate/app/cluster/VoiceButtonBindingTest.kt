package com.bydmate.app.cluster

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertFalse
import org.junit.Test

class VoiceButtonBindingTest {
    @Test fun `assignments are independent and companions never trigger`() {
        val local = VoiceButtonBinding(304, setOf(327))
        val alice = VoiceButtonBinding(383, setOf(384))
        assertEquals(VoiceButtonTarget.LOCAL, assignedVoiceTarget(304, local, alice))
        assertEquals(VoiceButtonTarget.ALICE, assignedVoiceTarget(383, local, alice))
        assertEquals(VoiceButtonTarget.COMPANION, assignedVoiceTarget(327, local, alice))
        assertEquals(VoiceButtonTarget.COMPANION, assignedVoiceTarget(384, local, alice))
        assertEquals(VoiceButtonTarget.UNASSIGNED, assignedVoiceTarget(351, local, alice))
        assertEquals(VoiceButtonTarget.UNASSIGNED, assignedVoiceTarget(0, local, VoiceButtonBinding()))
        assertEquals(VoiceButtonTarget.UNASSIGNED, assignedVoiceTarget(384, local, VoiceButtonBinding(0, setOf(384))))
    }

    @Test fun `a companion may arrive after a long hold ends`() {
        val anchor = learnWindowAnchor(304, 304, 1_000, 5_000)
        assertTrue(isLearnCompanion(327, true, 304, anchor, 5_059))
        assertFalse(isLearnCompanion(327, true, 304, anchor, 5_301))
        assertFalse(isLearnCompanion(327, false, 304, anchor, 5_059))
        assertFalse(isLearnCompanion(304, true, 304, anchor, 5_059))
        assertFalse(isLearnCompanion(24, true, 304, anchor, 5_059))
        assertFalse(isLearnCompanion(327, true, 304, anchor, 4_999))
    }

    @Test fun `a new assignment rejects any overlapping primary or companion`() {
        val local = VoiceButtonBinding(304, setOf(327))
        assertFalse(VoiceButtonBinding(327).canAssign(local.codes))
        assertFalse(VoiceButtonBinding(383, setOf(304)).canAssign(local.codes))
        assertFalse(VoiceButtonBinding(383, setOf(351)).canAssign(setOf(351)))
        assertFalse(VoiceButtonBinding(383, setOf(85)).canAssign(emptySet()))
        assertFalse(VoiceButtonBinding(24).canAssign(emptySet()))
        assertTrue(VoiceButtonBinding(383).canAssign(local.codes))
    }

    @Test fun `serialization is deterministic and corrupt values cannot swallow keys`() {
        assertEquals("304,327", voiceCompanionsToCsv(setOf(327, 304)))
        assertEquals(setOf(304, 327), voiceCompanionsFromCsv("304,327"))
        listOf(null, "", "327,x", "327,-1", "327,24").forEach {
            assertEquals(emptySet<Int>(), voiceCompanionsFromCsv(it))
        }
    }

    @Test fun `legacy mic fallback stays Android 10 takeover only until the pair is learned`() {
        val unlearned = VoiceButtonBinding(320)
        assertTrue(useLegacyVoiceFallback(29, true, unlearned, VoiceButtonBinding()))
        assertFalse(useLegacyVoiceFallback(30, true, unlearned, VoiceButtonBinding()))
        assertFalse(useLegacyVoiceFallback(29, false, unlearned, VoiceButtonBinding()))
        assertFalse(useLegacyVoiceFallback(29, true, VoiceButtonBinding(304, setOf(327)), VoiceButtonBinding()))
        assertFalse(useLegacyVoiceFallback(29, true, unlearned, VoiceButtonBinding(304, setOf(327))))
    }

    @Test fun `press pairing ignores repeats duplicate downs and companions but permits double press`() {
        val presses = VoiceButtonPresses()
        assertTrue(presses.firstDown(304, 1, 100, 0))
        assertFalse(presses.firstDown(304, 1, 100, 0))
        assertFalse(presses.firstDown(304, 1, 100, 1))
        presses.release(304, 1)
        assertTrue(presses.firstDown(304, 1, 200, 0))
        presses.clear()
        assertTrue(presses.firstDown(304, 1, 300, 0))
    }

    @Test fun `single button routing and exact double press boundary remain unchanged`() {
        val previous = VoicePressMemory(304, 1_000)
        assertEquals(VoicePressRoute.ALICE, voicePressRoute(0, false, 304, previous, 1_250))
        assertEquals(VoicePressRoute.LOCAL, voicePressRoute(0, false, 304, previous, 1_251))
        assertEquals(VoicePressRoute.NONE, voicePressRoute(1, true, 304, previous, 1_100))
    }
}
