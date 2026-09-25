package com.bydmate.app.cluster

import android.os.Build
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DiLink3VoicePlatformTest {
    @Test fun `accepts field ATTO3 DiLink3 fingerprint on Android 10`() {
        assertTrue(
            isDiLink3VoiceAliasPlatform(
                sdkInt = Build.VERSION_CODES.Q,
                fingerprint = "BYD-AUTO/DiLink3.0/DiLink3.0:10/QKQ1.210910.001/test:user/release-keys",
                device = "BYD AUTO",
                product = "BYD AUTO",
            )
        )
    }

    @Test fun `accepts exact DiLink3 device identifier on Android 10`() {
        assertTrue(
            isDiLink3VoiceAliasPlatform(
                sdkInt = Build.VERSION_CODES.Q,
                fingerprint = "unknown",
                device = "DiLink3.0",
                product = "unknown",
            )
        )
    }

    @Test fun `rejects generic Android 10 BYD platform`() {
        assertFalse(
            isDiLink3VoiceAliasPlatform(
                sdkInt = Build.VERSION_CODES.Q,
                fingerprint = "BYD-AUTO/generic/generic:10/test",
                device = "BYD AUTO",
                product = "BYD AUTO",
            )
        )
    }

    @Test fun `rejects DiLink4 marker even on Android 10`() {
        assertFalse(
            isDiLink3VoiceAliasPlatform(
                sdkInt = Build.VERSION_CODES.Q,
                fingerprint = "BYD-AUTO/DiLink4.0/DiLink4.0:10/test",
                device = "DiLink4.0",
                product = "DiLink4.0",
            )
        )
    }

    @Test fun `rejects DiLink3 marker on a different Android generation`() {
        assertFalse(
            isDiLink3VoiceAliasPlatform(
                sdkInt = Build.VERSION_CODES.S,
                fingerprint = "BYD-AUTO/DiLink3.0/DiLink3.0:12/test",
                device = "DiLink3.0",
                product = "DiLink3.0",
            )
        )
    }
}
