package com.bydmate.app.agent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ContactsDiagnosticsTest {

    // The DiLink 3 1.1.9 dump cut this message at 160 characters, just before the permission.
    @Test fun `a refused query names the permission it requires`() {
        val e = SecurityException(
            "Permission Denial: reading com.android.bluetooth.data.ContactContentProvider uri " +
                "content://com.android.bluetooth.contactprovider/contacts from pid=12207, uid=10125 " +
                "requires android.permission.BLUETOOTH_PRIVILEGED, or grantUriPermission()",
        )
        val text = ContactsDiagnostics.failureText(e)
        assertEquals("error SecurityException requires=android.permission.BLUETOOTH_PRIVILEGED: " + e.message!!.take(160), text)
        // The cut message alone would not have named it.
        assertTrue("BLUETOOTH_PRIVILEGED" !in e.message!!.take(160))
    }

    @Test fun `an error without a required permission says nothing about one`() {
        assertEquals("error IllegalStateException: boom", ContactsDiagnostics.failureText(IllegalStateException("boom")))
        assertEquals("error NullPointerException: ", ContactsDiagnostics.failureText(NullPointerException()))
    }
}
