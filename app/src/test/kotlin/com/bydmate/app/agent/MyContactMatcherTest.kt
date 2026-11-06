package com.bydmate.app.agent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MyContactMatcherTest {
    private val wife = MyContact("Жена", "+1", listOf("Ивета", "амис"))
    private val mom = MyContact("Мама", "+2")
    private val temp = MyContact("Темп", "+3")
    private val all = listOf(wife, mom, temp)

    @Test fun exact_alias_and_case_forms_find_the_contact() {
        assertEquals(listOf(wife), MyContactMatcher.find("Жена", all))
        assertEquals(listOf(wife), MyContactMatcher.find("жене", all))
        assertEquals(listOf(wife), MyContactMatcher.find("ивете", all))
        assertEquals(listOf(wife), MyContactMatcher.find("Амис", all))
        assertEquals(listOf(mom), MyContactMatcher.find("маме", all))
    }

    @Test fun a_one_letter_mishearing_finds_the_contact() {
        assertEquals(listOf(temp), MyContactMatcher.find("тэмп", all))
    }

    @Test fun an_exact_name_beats_a_near_miss() {
        val masha = MyContact("Маша", "+4")
        assertEquals(listOf(mom), MyContactMatcher.find("мама", all + masha))
    }

    @Test fun unknown_and_empty_names_find_nothing() {
        assertTrue(MyContactMatcher.find("Никто", all).isEmpty())
        assertTrue(MyContactMatcher.find("  ", all).isEmpty())
    }

    @Test fun dictated_numbers_are_recognised_and_words_are_not() {
        assertEquals("+37128397625", MyContactMatcher.dialableNumber("+371 2839-7625"))
        assertEquals("28397625", MyContactMatcher.dialableNumber("28397625"))
        assertNull(MyContactMatcher.dialableNumber("1234"))
        assertNull(MyContactMatcher.dialableNumber("мама"))
    }
}
