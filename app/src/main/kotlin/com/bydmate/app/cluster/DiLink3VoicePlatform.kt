package com.bydmate.app.cluster

import android.os.Build

/**
 * Field-confirmed DiLink 3 microphone-button quirk.
 *
 * ATTO 3 / DiLink 3.0 on Android 10 reports the physical voice button through
 * keycode 304 plus a companion 327 event instead of the generic BYD voice code 320.
 * Keep this gate deliberately narrow so other Android 10 BYD systems retain their
 * existing key routing unchanged.
 */
internal fun isDiLink3VoiceAliasPlatform(
    sdkInt: Int,
    fingerprint: String,
    device: String,
    product: String,
): Boolean {
    if (sdkInt != Build.VERSION_CODES.Q) return false
    val confirmedFingerprint = fingerprint.contains("BYD-AUTO/DiLink3.0/", ignoreCase = true)
    val confirmedDevice = device.equals("DiLink3.0", ignoreCase = true)
    val confirmedProduct = product.equals("DiLink3.0", ignoreCase = true)
    return confirmedFingerprint || confirmedDevice || confirmedProduct
}

internal fun isDiLink3VoiceAliasPlatform(): Boolean =
    isDiLink3VoiceAliasPlatform(
        sdkInt = Build.VERSION.SDK_INT,
        fingerprint = Build.FINGERPRINT.orEmpty(),
        device = Build.DEVICE.orEmpty(),
        product = Build.PRODUCT.orEmpty(),
    )
