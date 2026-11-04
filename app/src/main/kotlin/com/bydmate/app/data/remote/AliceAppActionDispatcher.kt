package com.bydmate.app.data.remote

import android.content.Context
import android.media.AudioManager
import com.bydmate.app.data.automation.ActionDispatcher
import com.bydmate.app.data.automation.DispatchResult
import com.bydmate.app.data.local.entity.ActionDef
import com.bydmate.app.data.vehicle.HelperBootstrap
import dagger.hilt.android.qualifiers.ApplicationContext
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

/**
 * App launches, the cluster projection and media from the Alice bridge, all through
 * ActionDispatcher: app_launch (shell-first), openNavigatorApp (the navigation-app table and
 * resolver the local assistant uses), system_settings, cluster_projection, media_key / media_volume, and the
 * session-targeted [ActionDispatcher.dispatchMediaTransport] (no global media key).
 */
@Singleton
class AliceAppActionDispatcher @Inject constructor(
    @ApplicationContext private val context: Context,
    private val dispatcher: ActionDispatcher,
    private val helperBootstrap: HelperBootstrap,
    private val appResolver: AliceAppResolver,
) {
    suspend fun app(command: AliceBridgeCommand, data: DiParsData?): Result<Unit> {
        clusterProjection(command.action)?.let { return dispatcher.dispatch(it, data).asResult() }
        val target = if (command.action == "app.launch") {
            if (command.text.isEmpty()) return AliceBridgeRouter.failure("missing_app_name")
            AliceAppCatalog.forName(command.text)
        } else {
            AliceAppCatalog.forAction(command.action)
                ?: return AliceBridgeRouter.failure(AliceBridgeRouter.UNSUPPORTED_ACTION)
        }
        // A detached same-version daemon is refreshed before the shell-first launch.
        helperBootstrap.ensureRunning()
        return when (target) {
            is AliceAppTarget.Navigator -> dispatcher.openNavigatorApp(target.navigator).asResult()
            AliceAppTarget.Self -> launch(context.packageName, data)
            is AliceAppTarget.Settings -> dispatcher.dispatch(
                ActionDef("", ALICE, "system_settings", JSONObject().put("section", target.section).toString()), data,
            ).asResult()
            is AliceAppTarget.App -> {
                val pkg = appResolver.resolve(target).getOrElse { return Result.failure(it) }
                launch(pkg, data)
            }
        }
    }

    suspend fun media(command: AliceBridgeCommand, data: DiParsData?): Result<Unit> {
        transport(command.action)?.let { return dispatcher.dispatchMediaTransport(it).asResult() }
        val action = when (command.action) {
            "media.play" -> ActionDef("", ALICE, "media_key", "play")
            "media.pause" -> ActionDef("", ALICE, "media_key", "pause")
            "media.volume_up" -> volume("+1")
            "media.volume_down" -> volume("-1")
            "media.mute" -> volume("mute")
            "media.unmute" -> volume("unmute")
            "media.volume" -> command.value?.takeIf { it in 0..100 }?.let { volume(volumeIndex(it).toString()) }
                ?: return AliceBridgeRouter.failure("invalid_volume")
            else -> return AliceBridgeRouter.failure(AliceBridgeRouter.UNSUPPORTED_ACTION)
        }
        return dispatcher.dispatch(action, data).asResult()
    }

    private suspend fun launch(packageName: String, data: DiParsData?): Result<Unit> {
        val payload = JSONObject().put("packageName", packageName).toString()
        return dispatcher.dispatch(ActionDef("", ALICE, "app_launch", payload), data).asResult()
    }

    private fun clusterProjection(action: String): ActionDef? = when (action) {
        "navigation.cluster_on" -> ActionDef("", ALICE, "cluster_projection", "1")
        "navigation.cluster_off" -> ActionDef("", ALICE, "cluster_projection", "0")
        else -> null
    }

    private fun transport(action: String): ActionDispatcher.MediaTransport? = when (action) {
        "media.next" -> ActionDispatcher.MediaTransport.NEXT
        "media.previous" -> ActionDispatcher.MediaTransport.PREVIOUS
        "media.play_pause" -> ActionDispatcher.MediaTransport.PLAY_PAUSE
        else -> null
    }

    /** Alice speaks percent, media_volume takes the stream index. */
    private fun volumeIndex(percent: Int): Int {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
        val max = audio?.getStreamMaxVolume(AudioManager.STREAM_MUSIC)?.coerceAtLeast(1) ?: 1
        return percent * max / PERCENT
    }

    private fun volume(payload: String) = ActionDef("media_volume", ALICE, "media_volume", payload)

    private fun DispatchResult.asResult(): Result<Unit> =
        if (success) Result.success(Unit) else AliceBridgeRouter.failure(reason ?: "dispatch_failed")

    private companion object {
        const val ALICE = "Alice"
        const val PERCENT = 100
    }
}
