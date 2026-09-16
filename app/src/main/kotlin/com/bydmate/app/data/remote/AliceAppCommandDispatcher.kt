package com.bydmate.app.data.remote

import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.net.Uri
import android.provider.Settings
import android.view.KeyEvent
import com.bydmate.app.cluster.ClusterVoiceControl
import com.bydmate.app.navdata.NavPackages
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.Locale
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Non-vehicle executor for Alice/Yandex commands.
 *
 * The cloud side is deliberately semantic: it may request app.waze.open or
 * media.next, but it never supplies an arbitrary Android package/component.
 * This keeps remote execution on a small allowlist while still letting us
 * support different DiLink fleets through package-candidate and launcher-label
 * fallbacks.
 */
@Singleton
class AliceAppCommandDispatcher @Inject constructor(
    @ApplicationContext private val context: Context,
    private val clusterVoiceControl: ClusterVoiceControl,
) {
    private data class AppTarget(
        val packages: List<String>,
        val labelKeywords: List<String> = emptyList(),
    )

    fun dispatch(rawAction: String): Result<Unit>? {
        val action = rawAction.trim().lowercase(Locale.ROOT)

        APP_TARGETS[action]?.let { target ->
            return runCatching { launchTarget(action, target) }
        }

        return when (action) {
            ACTION_BROWSER_OPEN -> runCatching { launchBrowser() }
            ACTION_ANDROID_SETTINGS_OPEN -> runCatching { launchAndroidSettings() }
            ACTION_BYDMATE_OPEN -> runCatching { launchPackage(context.packageName, action) }

            ACTION_CLUSTER_ON -> runCatching {
                clusterVoiceControl.apply(true)
                clusterVoiceControl.lastFailure()?.let { error("cluster_projection_failed:$it") }
            }
            ACTION_CLUSTER_OFF -> runCatching {
                clusterVoiceControl.apply(false)
                clusterVoiceControl.lastFailure()?.let { error("cluster_projection_failed:$it") }
            }

            ACTION_MEDIA_PLAY -> mediaKey(KeyEvent.KEYCODE_MEDIA_PLAY)
            ACTION_MEDIA_PAUSE -> mediaKey(KeyEvent.KEYCODE_MEDIA_PAUSE)
            ACTION_MEDIA_NEXT -> mediaKey(KeyEvent.KEYCODE_MEDIA_NEXT)
            ACTION_MEDIA_PREVIOUS -> mediaKey(KeyEvent.KEYCODE_MEDIA_PREVIOUS)
            ACTION_MEDIA_PLAY_PAUSE -> mediaKey(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE)
            ACTION_MEDIA_VOLUME_UP -> adjustVolume(AudioManager.ADJUST_RAISE)
            ACTION_MEDIA_VOLUME_DOWN -> adjustVolume(AudioManager.ADJUST_LOWER)
            ACTION_MEDIA_MUTE -> adjustVolume(AudioManager.ADJUST_MUTE)
            ACTION_MEDIA_UNMUTE -> adjustVolume(AudioManager.ADJUST_UNMUTE)

            else -> null
        }
    }

    private fun launchTarget(action: String, target: AppTarget) {
        for (pkg in target.packages) {
            val intent = context.packageManager.getLaunchIntentForPackage(pkg) ?: continue
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            return
        }

        if (target.labelKeywords.isNotEmpty()) {
            val launcherIntent = Intent(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_LAUNCHER)
            }
            val pm = context.packageManager
            val candidates = pm.queryIntentActivities(launcherIntent, 0)
            val match = candidates.firstOrNull { info ->
                val label = info.loadLabel(pm).toString().lowercase(Locale.ROOT)
                target.labelKeywords.any { keyword ->
                    label.contains(keyword.lowercase(Locale.ROOT))
                }
            }
            if (match != null) {
                val pkg = match.activityInfo.packageName
                val intent = pm.getLaunchIntentForPackage(pkg)
                    ?: Intent(Intent.ACTION_MAIN).apply {
                        addCategory(Intent.CATEGORY_LAUNCHER)
                        setClassName(pkg, match.activityInfo.name)
                    }
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
                return
            }
        }

        error("app_not_installed:$action")
    }

    private fun launchPackage(packageName: String, action: String) {
        val intent = context.packageManager.getLaunchIntentForPackage(packageName)
            ?: error("app_not_installed:$action")
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    private fun launchBrowser() {
        // Prefer the same Chrome package used by current BYDMate aliases. If a
        // particular car ships another browser, ACTION_VIEW lets Android select it.
        val chrome = context.packageManager.getLaunchIntentForPackage("com.android.chrome")
        if (chrome != null) {
            chrome.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(chrome)
            return
        }
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://www.google.com")).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }

    private fun launchAndroidSettings() {
        val intent = Intent(Settings.ACTION_SETTINGS).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }

    private fun mediaKey(keyCode: Int): Result<Unit> = runCatching {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, keyCode))
        audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, keyCode))
    }

    private fun adjustVolume(direction: Int): Result<Unit> = runCatching {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, direction, AudioManager.FLAG_SHOW_UI)
    }

    companion object {
        const val ACTION_WAZE_OPEN = "app.waze.open"
        const val ACTION_YANDEX_NAVI_OPEN = "app.yandex_navi.open"
        const val ACTION_YANDEX_MAPS_OPEN = "app.yandex_maps.open"
        const val ACTION_MUSIC_OPEN = "app.music.open"
        const val ACTION_YOUTUBE_OPEN = "app.youtube.open"
        const val ACTION_BROWSER_OPEN = "app.browser.open"
        const val ACTION_CAR_SETTINGS_OPEN = "app.car_settings.open"
        const val ACTION_ANDROID_SETTINGS_OPEN = "app.android_settings.open"
        const val ACTION_CAMERA_OPEN = "app.camera.open"
        const val ACTION_DASHCAM_OPEN = "app.dashcam.open"
        const val ACTION_FILES_OPEN = "app.files.open"
        const val ACTION_DRIVE_MODES_OPEN = "app.drive_modes.open"
        const val ACTION_SENTRY_OPEN = "app.sentry.open"
        const val ACTION_ABRP_OPEN = "app.abrp.open"
        const val ACTION_MEDIA_CENTER_OPEN = "app.media_center.open"
        const val ACTION_PHONE_OPEN = "app.phone.open"
        const val ACTION_RADIO_OPEN = "app.radio.open"
        const val ACTION_BYDMATE_OPEN = "app.bydmate.open"

        const val ACTION_CLUSTER_ON = "navigation.cluster_on"
        const val ACTION_CLUSTER_OFF = "navigation.cluster_off"

        const val ACTION_MEDIA_PLAY = "media.play"
        const val ACTION_MEDIA_PAUSE = "media.pause"
        const val ACTION_MEDIA_NEXT = "media.next"
        const val ACTION_MEDIA_PREVIOUS = "media.previous"
        const val ACTION_MEDIA_PLAY_PAUSE = "media.play_pause"
        const val ACTION_MEDIA_VOLUME_UP = "media.volume_up"
        const val ACTION_MEDIA_VOLUME_DOWN = "media.volume_down"
        const val ACTION_MEDIA_MUTE = "media.mute"
        const val ACTION_MEDIA_UNMUTE = "media.unmute"

        private val APP_TARGETS: Map<String, AppTarget> = mapOf(
            ACTION_WAZE_OPEN to AppTarget(
                packages = listOf("com.waze"),
                labelKeywords = listOf("waze"),
            ),
            ACTION_YANDEX_NAVI_OPEN to AppTarget(
                packages = NavPackages.YANDEX_NAVI.toList(),
                labelKeywords = listOf("яндекс навигатор", "yandex navigator", "navigator"),
            ),
            ACTION_YANDEX_MAPS_OPEN to AppTarget(
                packages = NavPackages.YANDEX_MAPS.toList(),
                labelKeywords = listOf("яндекс карты", "yandex maps"),
            ),
            ACTION_MUSIC_OPEN to AppTarget(
                packages = listOf("ru.yandex.music"),
                labelKeywords = listOf("яндекс музыка", "yandex music", "music", "музыка"),
            ),
            ACTION_YOUTUBE_OPEN to AppTarget(
                packages = listOf("anddea.youtube", "com.google.android.youtube"),
                labelKeywords = listOf("youtube", "ютуб"),
            ),
            ACTION_CAR_SETTINGS_OPEN to AppTarget(
                packages = listOf("com.byd.carsettings"),
                labelKeywords = listOf("настройки", "settings", "设置"),
            ),
            ACTION_CAMERA_OPEN to AppTarget(
                packages = listOf("com.byd.avc"),
                labelKeywords = listOf("камера", "camera", "全景影像"),
            ),
            ACTION_DASHCAM_OPEN to AppTarget(
                packages = listOf("com.byd.cdr"),
                labelKeywords = listOf("регистратор", "dashcam", "recorder", "行车记录"),
            ),
            ACTION_FILES_OPEN to AppTarget(
                packages = listOf("com.byd.filemanager"),
                labelKeywords = listOf("файлы", "file", "文件"),
            ),
            ACTION_DRIVE_MODES_OPEN to AppTarget(
                packages = listOf("com.byd.drivemode"),
                labelKeywords = listOf("режим вождения", "drive mode", "驾驶模式"),
            ),
            ACTION_SENTRY_OPEN to AppTarget(
                packages = listOf("com.byd.sentrymode"),
                labelKeywords = listOf("часовой", "охрана", "sentry"),
            ),
            ACTION_ABRP_OPEN to AppTarget(
                packages = listOf("com.iternio.abrpapp"),
                labelKeywords = listOf("abrp", "routeplanner"),
            ),
            ACTION_MEDIA_CENTER_OPEN to AppTarget(
                packages = listOf("com.byd.mediacenter"),
                labelKeywords = listOf("медиацентр", "media center", "player", "плеер"),
            ),
            ACTION_PHONE_OPEN to AppTarget(
                packages = listOf("com.byd.bluetoothcall"),
                labelKeywords = listOf("телефон", "phone", "bluetooth call", "电话"),
            ),
            ACTION_RADIO_OPEN to AppTarget(
                packages = listOf("com.byd.radio", "com.byd.mediacenter"),
                labelKeywords = listOf("радио", "radio", "fm", "收音机"),
            ),
        )

        val supportedActions: Set<String> = APP_TARGETS.keys + setOf(
            ACTION_BROWSER_OPEN,
            ACTION_ANDROID_SETTINGS_OPEN,
            ACTION_BYDMATE_OPEN,
            ACTION_CLUSTER_ON,
            ACTION_CLUSTER_OFF,
            ACTION_MEDIA_PLAY,
            ACTION_MEDIA_PAUSE,
            ACTION_MEDIA_NEXT,
            ACTION_MEDIA_PREVIOUS,
            ACTION_MEDIA_PLAY_PAUSE,
            ACTION_MEDIA_VOLUME_UP,
            ACTION_MEDIA_VOLUME_DOWN,
            ACTION_MEDIA_MUTE,
            ACTION_MEDIA_UNMUTE,
        )
    }
}
