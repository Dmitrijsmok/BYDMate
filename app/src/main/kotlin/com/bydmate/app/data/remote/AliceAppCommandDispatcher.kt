package com.bydmate.app.data.remote

import android.content.Context
import android.content.Intent
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Executes the deliberately small set of non-vehicle actions exposed by the
 * Alice/Yandex command bridge.
 *
 * App actions are kept separate from [AliceBridgeCommandTranslator] so a cloud
 * request can never be interpreted as a raw BYD vehicle write. Unknown actions
 * return null and continue through the normal vehicle-command path.
 */
@Singleton
class AliceAppCommandDispatcher @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    fun dispatch(rawAction: String): Result<Unit>? {
        val action = rawAction.trim().lowercase()
        return when (action) {
            ACTION_WAZE_OPEN -> runCatching {
                val launchIntent = context.packageManager
                    .getLaunchIntentForPackage(WAZE_PACKAGE)
                    ?: error("waze_not_installed")
                launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(launchIntent)
            }
            else -> null
        }
    }

    companion object {
        const val ACTION_WAZE_OPEN = "app.waze.open"
        private const val WAZE_PACKAGE = "com.waze"

        val supportedActions: Set<String> = setOf(ACTION_WAZE_OPEN)
    }
}
