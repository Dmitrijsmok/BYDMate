package com.bydmate.app.voice

import com.bydmate.app.data.remote.AliceAppCatalog
import com.bydmate.app.data.remote.AliceAppTarget

/**
 * The offline «открой <приложение>», tried after a dictionary miss: «открой» / «запусти»
 * (optionally «приложение») and then exactly a name of the app table the agent and Alice share
 * ([AliceAppCatalog.known]). A closed set: an unknown name, or anything said after the name, goes
 * on to the agent. Navigation apps are left to the dictionary's NAVIGATOR (and the agent), so this
 * never answers for them. Pure (fork 7b417718, df875e49).
 *
 * [matchClose] is the same for «закрой» / «выключи» <приложение>: it is tried only after the
 * dictionary missed too, so «закрой окна», «закрой люк» or «выключи свет» never get here, and it
 * takes the same closed set of names, so «закрой багажник» is no app either.
 */
internal object LocalAppLaunchQuery {

    /** [name] as said and the app it means. */
    data class Hit(val name: String, val target: AliceAppTarget)

    fun match(text: String): Hit? {
        val name = nameAfter(text, OPEN_VERBS) ?: return null
        val target = AliceAppCatalog.known(name)?.takeUnless { it is AliceAppTarget.Navigator } ?: return null
        return Hit(name, target)
    }

    /**
     * «закрой тикток», «выключи ютуб»: an app of the table to close, or null. Only an app or a
     * navigation app is closed: a settings screen and BYDMate itself are not, and neither is the
     * sentry app, whose names («выключи охрану») mean disarming, not killing the app.
     */
    fun matchClose(text: String): Hit? {
        val name = nameAfter(text, CLOSE_VERBS) ?: return null
        val target = AliceAppCatalog.known(name) ?: return null
        if (target !is AliceAppTarget.App && target !is AliceAppTarget.Navigator) return null
        if (target == AliceAppCatalog.forAction(SENTRY_ACTION)) return null
        return Hit(name, target)
    }

    /** The words after one of [verbs] (and an optional «приложение»), or null. */
    private fun nameAfter(text: String, verbs: Set<String>): String? {
        val words = VoiceDictionary.words(text)
        if (words.firstOrNull() !in verbs) return null
        val rest = words.drop(1).let { if (it.firstOrNull() == APP_WORD) it.drop(1) else it }
        return rest.takeIf { it.isNotEmpty() }?.joinToString(" ")
    }

    private val OPEN_VERBS = setOf("открой", "открыть", "запусти", "запустить")
    private val CLOSE_VERBS = setOf("закрой", "закрыть", "закройте", "выключи", "выключить")
    private const val APP_WORD = "приложение"
    private const val SENTRY_ACTION = "app.sentry.open"
}
