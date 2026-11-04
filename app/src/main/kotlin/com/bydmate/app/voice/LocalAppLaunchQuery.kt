package com.bydmate.app.voice

import com.bydmate.app.data.remote.AliceAppCatalog
import com.bydmate.app.data.remote.AliceAppTarget

/**
 * The offline «открой <приложение>», tried after a dictionary miss: «открой» / «запусти»
 * (optionally «приложение») and then exactly a name of the app table the agent and Alice share
 * ([AliceAppCatalog.known]). A closed set: an unknown name, or anything said after the name, goes
 * on to the agent. Navigation apps are left to the dictionary's NAVIGATOR (and the agent), so this
 * never answers for them. Pure (fork 7b417718, df875e49).
 */
internal object LocalAppLaunchQuery {

    /** [name] as said and the app it means. */
    data class Hit(val name: String, val target: AliceAppTarget)

    fun match(text: String): Hit? {
        val words = VoiceDictionary.words(text)
        if (words.firstOrNull() !in VERBS) return null
        val rest = words.drop(1).let { if (it.firstOrNull() == APP_WORD) it.drop(1) else it }
        if (rest.isEmpty()) return null
        val name = rest.joinToString(" ")
        val target = AliceAppCatalog.known(name)?.takeUnless { it is AliceAppTarget.Navigator } ?: return null
        return Hit(name, target)
    }

    private val VERBS = setOf("открой", "открыть", "запусти", "запустить")
    private const val APP_WORD = "приложение"
}
