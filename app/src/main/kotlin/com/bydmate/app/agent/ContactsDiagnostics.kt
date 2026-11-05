package com.bydmate.app.agent

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.ContactsContract
import androidx.core.content.ContextCompat

/**
 * The «--- contacts ---» block of the diagnostic dump: where this head unit keeps the phonebook
 * the call_contact tool needs (#91). Counts, account types and provider authorities only — never
 * a name or a number.
 */
object ContactsDiagnostics {
    private const val BT_CALL_PACKAGE = "com.byd.bluetoothcall"
    private val PHONEBOOK_HINTS = listOf("contact", "pbap", "phonebook", "bluetoothcall", "btcall")

    fun lines(context: Context): List<String> = buildList {
        val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) ==
            PackageManager.PERMISSION_GRANTED
        add("permission: ${if (granted) "granted" else "denied"}")
        if (granted) {
            add("phones: ${count(context, ContactsContract.CommonDataKinds.Phone.CONTENT_URI)}")
            add("raw_contacts by account type: ${accountTypes(context)}")
        }
        add("$BT_CALL_PACKAGE providers: ${btCallProviders(context)}")
        add("phonebook-like providers: ${phonebookProviders(context)}")
    }

    private fun count(context: Context, uri: Uri): String = runCatching {
        context.contentResolver.query(uri, arrayOf("_id"), null, null, null)?.use { it.count.toString() }
            ?: "null cursor"
    }.getOrElse { "error ${it.javaClass.simpleName}" }

    private fun accountTypes(context: Context): String = runCatching {
        val types = sortedMapOf<String, Int>()
        context.contentResolver.query(
            ContactsContract.RawContacts.CONTENT_URI,
            arrayOf(ContactsContract.RawContacts.ACCOUNT_TYPE), null, null, null,
        )?.use { c ->
            while (c.moveToNext()) {
                val type = c.getString(0) ?: "(local)"
                types[type] = (types[type] ?: 0) + 1
            }
        }
        if (types.isEmpty()) "none" else types.entries.joinToString { "${it.key}=${it.value}" }
    }.getOrElse { "error ${it.javaClass.simpleName}" }

    private fun btCallProviders(context: Context): String = runCatching {
        @Suppress("DEPRECATION")
        val info = context.packageManager.getPackageInfo(BT_CALL_PACKAGE, PackageManager.GET_PROVIDERS)
        info.providers?.takeIf { it.isNotEmpty() }?.joinToString { p ->
            "${p.authority} exported=${p.exported} read=${p.readPermission ?: "-"}"
        } ?: "none"
    }.getOrElse { if (it is PackageManager.NameNotFoundException) "not installed" else "error ${it.javaClass.simpleName}" }

    private fun phonebookProviders(context: Context): String = runCatching {
        @Suppress("DEPRECATION")
        val all = context.packageManager.queryContentProviders(null as String?, 0, 0)
        all
            .filter { p -> PHONEBOOK_HINTS.any { p.authority.orEmpty().contains(it, ignoreCase = true) } }
            .joinToString { p -> "${p.authority} (${p.packageName}) exported=${p.exported}" }
            .ifEmpty { "none" }
    }.getOrElse { "error ${it.javaClass.simpleName}" }
}
