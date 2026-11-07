package com.bydmate.app.voice

import android.content.Context
import com.bydmate.app.data.vehicle.HelperClient
import com.bydmate.app.helper.AudioRecordersDiag

/** Names the app that holds the microphone when our capture gets only silence; null = unknown. */
fun interface MicHolderLookup {
    suspend fun holder(): String?
}

/** Reads the recording clients through the helper daemon (shell can see packages, the app
 *  uid cannot) and returns the first other app's visible label, else its package name. */
class DaemonMicHolderLookup(
    private val helper: HelperClient,
    private val context: Context,
) : MicHolderLookup {
    override suspend fun holder(): String? {
        val lines = runCatching { helper.audioRecorders() }.getOrNull() ?: return null
        val pkg = AudioRecordersDiag.holderPackages(lines, context.packageName).firstOrNull() ?: return null
        val pm = context.packageManager
        return runCatching { pm.getApplicationLabel(pm.getApplicationInfo(pkg, 0)).toString() }
            .getOrNull()?.takeIf { it.isNotBlank() } ?: pkg
    }
}
