package com.bydmate.app.agent

import org.json.JSONArray
import org.json.JSONObject

/**
 * «Мои контакты»: the owner's own name → number list for voice calls. The head unit's phonebook
 * is not readable by apps (field 1.1.6: the Contacts provider has no numbers, the Bluetooth
 * phonebook provider needs a system permission), so calls by name use this list. [aliases] are
 * the other ways the name is said or misheard («амис», «темп»).
 */
data class MyContact(val name: String, val phone: String, val aliases: List<String> = emptyList())

/** Finds a contact by a spoken name: exact, then the same word in another case form, then a near miss. */
object MyContactMatcher {
    private const val MIN_STEM = 3
    private const val ENDING_SLACK = 2
    private const val SHORT_WORD = 5

    fun normalize(text: String): String = text.lowercase()
        .replace('ё', 'е')
        .replace(Regex("[^\\p{L}\\p{N} ]"), " ")
        .replace(Regex("\\s+"), " ")
        .trim()

    /** The contacts the [query] names best; several when they tie (the caller asks which one). */
    fun find(query: String, contacts: List<MyContact>): List<MyContact> {
        val q = normalize(query)
        if (q.isEmpty()) return emptyList()
        val scored = contacts.mapNotNull { c -> score(q, c)?.let { c to it } }
        val best = scored.minOfOrNull { it.second } ?: return emptyList()
        return scored.filter { it.second == best }.map { it.first }
    }

    /** 0 exact, 1 another case form («жене» / «жена»), 2 one or two letters off; null no match. */
    private fun score(q: String, c: MyContact): Int? {
        val keys = (listOf(c.name) + c.aliases).map(::normalize).filter { it.isNotEmpty() }
        val candidates = keys + keys.flatMap { it.split(' ') }.filter { it.length >= MIN_STEM }
        return candidates.mapNotNull { keyScore(q, it) }.minOrNull()
    }

    private fun keyScore(q: String, key: String): Int? {
        if (q == key) return 0
        val shorter = minOf(q.length, key.length)
        val prefix = q.zip(key).takeWhile { (a, b) -> a == b }.size
        if (shorter >= MIN_STEM && prefix >= maxOf(MIN_STEM, shorter - ENDING_SLACK) &&
            maxOf(q.length, key.length) - prefix <= ENDING_SLACK + 1
        ) return 1
        val allowed = if (shorter <= SHORT_WORD) 1 else 2
        return if (shorter >= MIN_STEM && levenshtein(q, key) <= allowed) 2 else null
    }

    private fun levenshtein(a: String, b: String): Int {
        var prev = IntArray(b.length + 1) { it }
        for (i in 1..a.length) {
            val cur = IntArray(b.length + 1)
            cur[0] = i
            for (j in 1..b.length) {
                val cost = if (a[i - 1] == b[j - 1]) 0 else 1
                cur[j] = minOf(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            }
            prev = cur
        }
        return prev[b.length]
    }

    /** A phrase that is a dictated number (at least five digits, nothing but digits and separators). */
    fun dialableNumber(text: String): String? {
        val trimmed = text.trim()
        if (!trimmed.matches(Regex("\\+?[0-9 ()\\-]+"))) return null
        val digits = trimmed.filter(Char::isDigit)
        if (digits.length < MIN_DIGITS) return null
        return (if (trimmed.startsWith("+")) "+" else "") + digits
    }

    private const val MIN_DIGITS = 5
}

/** JSON in the settings table (so it is in the settings backup). */
object MyContactsCodec {
    fun decode(raw: String?): List<MyContact> = runCatching {
        if (raw.isNullOrBlank()) return emptyList()
        val arr = JSONArray(raw)
        (0 until arr.length()).mapNotNull { i ->
            val o = arr.optJSONObject(i) ?: return@mapNotNull null
            val name = o.optString("name").trim()
            val phone = o.optString("phone").trim()
            if (name.isEmpty() || phone.isEmpty()) return@mapNotNull null
            val aliases = o.optJSONArray("aliases")?.let { a ->
                (0 until a.length()).map { a.optString(it).trim() }.filter { it.isNotEmpty() }
            }.orEmpty()
            MyContact(name, phone, aliases)
        }
    }.getOrDefault(emptyList())

    fun encode(contacts: List<MyContact>): String = JSONArray().apply {
        contacts.forEach { c ->
            put(JSONObject().put("name", c.name).put("phone", c.phone).put("aliases", JSONArray(c.aliases)))
        }
    }.toString()
}
