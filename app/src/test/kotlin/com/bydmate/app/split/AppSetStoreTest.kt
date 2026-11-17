package com.bydmate.app.split

import com.bydmate.app.split.AppSetStore.Check
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AppSetStoreTest {

    private val tiktokMusic = AppSet("set1", "Открой комплект 1", "com.zhiliaoapp.musically", "ru.yandex.music")

    private fun store(backing: MutableMap<String, Any?> = mutableMapOf()) = AppSetStore(fakeSplitSharedPrefs(backing))

    @Test fun `a saved set survives a new process`() {
        val backing = mutableMapOf<String, Any?>()
        store(backing).upsert(tiktokMusic)
        assertEquals(listOf(tiktokMusic), store(backing).sets.value)
    }

    @Test fun `a set without a right app and with autostart round-trips`() {
        val backing = mutableMapOf<String, Any?>()
        val solo = AppSet("set2", "Видео", "com.zhiliaoapp.musically", null, autostart = true)
        store(backing).upsert(solo)
        assertEquals(solo, store(backing).get("set2"))
    }

    @Test fun `unreadable stored sets start empty instead of crashing`() {
        val s = store(mutableMapOf(AppSetStore.KEY to "{not json"))
        assertTrue(s.sets.value.isEmpty())
    }

    @Test fun `the name is the voice phrase and only the whole utterance matches`() {
        val s = store().apply { upsert(tiktokMusic) }
        assertEquals(tiktokMusic, s.match("открой комплект 1"))
        assertEquals(tiktokMusic, s.match("эй, открой комплект 1, пожалуйста"))
        assertNull(s.match("открой комплект 1 и включи музыку"))
        assertNull(s.match("открой комплект 2"))
    }

    @Test fun `only one set starts with the service`() {
        val s = store()
        s.upsert(tiktokMusic.copy(autostart = true))
        s.upsert(AppSet("set2", "Второй", "org.telegram.messenger", null, autostart = true))
        assertEquals(listOf(false, true), s.sets.value.map { it.autostart })
        assertEquals("set2", s.autostartSet()?.id)
    }

    @Test fun `saving an existing set keeps its place`() {
        val s = store()
        s.upsert(tiktokMusic)
        s.upsert(AppSet("set2", "Второй", "org.telegram.messenger"))
        s.upsert(tiktokMusic.copy(name = "Первый"))
        assertEquals(listOf("Первый", "Второй"), s.sets.value.map { it.name })
    }

    @Test fun `removing a set forgets it`() {
        val backing = mutableMapOf<String, Any?>()
        store(backing).apply { upsert(tiktokMusic); remove("set1") }
        assertTrue(store(backing).sets.value.isEmpty())
    }

    @Test fun `new ids do not repeat after a removal`() {
        val s = store()
        s.upsert(tiktokMusic)
        s.upsert(AppSet(s.newId(), "Второй", "org.telegram.messenger"))
        s.remove("set1")
        assertEquals("set3", s.newId())
    }

    @Test fun `check accepts a good set and names what is wrong with a bad one`() {
        val s = store().apply { upsert(tiktokMusic) }
        assertEquals(Check.Ok, s.check(tiktokMusic))
        assertEquals(Check.NoName, s.check(tiktokMusic.copy(name = "  ")))
        assertEquals(Check.NameTooLong, s.check(tiktokMusic.copy(name = "а".repeat(AppSetStore.MAX_NAME_CHARS + 1))))
        assertEquals(Check.NoLeftApp, s.check(tiktokMusic.copy(leftPkg = "")))
        assertEquals(Check.SameApp, s.check(tiktokMusic.copy(rightPkg = tiktokMusic.leftPkg)))
    }

    @Test fun `a name that is another sets phrase is refused, however it is written`() {
        val s = store().apply { upsert(tiktokMusic) }
        val other = AppSet("set2", "открой  КОМПЛЕКТ 1!", "org.telegram.messenger")
        assertEquals(Check.NameInUse("Открой комплект 1"), s.check(other))
        assertFalse(s.check(other) == Check.Ok)
    }

    @Test fun `the number of sets is limited`() {
        val s = store()
        repeat(AppSetStore.MAX_SETS) { s.upsert(AppSet("set${it + 1}", "Комплект ${it + 1}", "pkg.a$it")) }
        assertEquals(Check.TooMany, s.check(AppSet("set99", "Лишний", "pkg.extra")))
        assertEquals(Check.Ok, s.check(s.sets.value.first()))
    }
}
