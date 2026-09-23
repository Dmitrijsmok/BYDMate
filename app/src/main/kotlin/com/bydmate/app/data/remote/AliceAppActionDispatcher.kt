package com.bydmate.app.data.remote

import android.content.Context
import android.media.AudioManager
import android.view.KeyEvent
import com.bydmate.app.data.automation.ActionDispatcher
import com.bydmate.app.data.local.entity.ActionDef
import com.bydmate.app.data.vehicle.HelperBootstrap
import dagger.hilt.android.qualifiers.ApplicationContext
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AliceAppActionDispatcher @Inject constructor(
    @ApplicationContext context: Context,
    private val dispatcher: ActionDispatcher,
    private val helperBootstrap: HelperBootstrap,
    private val appResolver: AliceAppResolver,
) {
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    suspend fun dispatch(json: JSONObject, data: DiParsData?): Result<Unit>? {
        val action = json.optString("action").trim().lowercase()
        if (action == "app.launch") {
            val query = json.optString("text").trim()
                .ifEmpty { json.optString("query").trim() }
            if (query.isEmpty()) return Result.failure(IllegalArgumentException("missing_app_name"))
            return launch(appResolver.resolveText(query), data)
        }

        appResolver.resolveAction(action)?.let { return launch(it, data) }
        actionDef(action, json)?.let { return dispatcher.dispatch(it, data).asResult() }
        mediaKey(action)?.let { return dispatchMediaKey(it) }
        return null
    }

    private suspend fun launch(
        packageResult: Result<String>,
        data: DiParsData?,
    ): Result<Unit> {
        val packageName = packageResult.getOrNull()
            ?: return Result.failure(
                packageResult.exceptionOrNull() ?: IllegalStateException("app_not_installed")
            )

        // Refresh a detached same-version daemon before shell-first app launch.
        helperBootstrap.ensureRunning()
        val payload = JSONObject().put("packageName", packageName).toString()
        return dispatcher.dispatch(ActionDef("", "Alice", "app_launch", payload), data).asResult()
    }

    private fun actionDef(action: String, json: JSONObject): ActionDef? = when (action) {
        "navigation.cluster_on" -> ActionDef("", "Alice", "cluster_projection", "1")
        "navigation.cluster_off" -> ActionDef("", "Alice", "cluster_projection", "0")
        "media.volume_up" -> aliceVolumeAction("+1")
        "media.volume_down" -> aliceVolumeAction("-1")
        "media.mute" -> aliceVolumeAction("mute")
        "media.unmute" -> aliceVolumeAction("unmute")
        "media.volume" -> absoluteVolumeAction(json)
        else -> null
    }

    private fun absoluteVolumeAction(json: JSONObject): ActionDef? {
        val percent = json.optInt("value", -1).takeIf { it in 0..100 } ?: return null
        val max = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC).coerceAtLeast(1)
        return aliceVolumeAction((percent * max / 100.0).toInt().toString())
    }

    private fun mediaKey(action: String): Int? = when (action) {
        "media.play" -> KeyEvent.KEYCODE_MEDIA_PLAY
        "media.pause" -> KeyEvent.KEYCODE_MEDIA_PAUSE
        "media.next" -> KeyEvent.KEYCODE_MEDIA_NEXT
        "media.previous" -> KeyEvent.KEYCODE_MEDIA_PREVIOUS
        "media.play_pause" -> KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
        else -> null
    }

    private fun dispatchMediaKey(keyCode: Int): Result<Unit> {
        val now = android.os.SystemClock.uptimeMillis()
        audioManager.dispatchMediaKeyEvent(KeyEvent(now, now, KeyEvent.ACTION_DOWN, keyCode, 0))
        audioManager.dispatchMediaKeyEvent(KeyEvent(now, now, KeyEvent.ACTION_UP, keyCode, 0))
        return Result.success(Unit)
    }

    private fun com.bydmate.app.data.automation.DispatchResult.asResult(): Result<Unit> =
        if (success) Result.success(Unit)
        else Result.failure(IllegalStateException(reason ?: "dispatch_failed"))
}

private fun aliceVolumeAction(value: String): ActionDef =
    ActionDef("media_volume", "Alice", "media_volume", value)
