package com.bydmate.app.cluster

import android.content.Context
import android.content.SharedPreferences
import com.bydmate.app.data.repository.SettingsRepository

fun SharedPreferences.localVoiceBinding(): VoiceButtonBinding = VoiceButtonBinding(
    getInt(SettingsRepository.KEY_VOICE_KEYCODE, DEFAULT_VOICE_KEYCODE),
    voiceCompanionsFromCsv(getString(SettingsRepository.KEY_VOICE_COMPANIONS, null)),
)

fun SharedPreferences.aliceVoiceBinding(): VoiceButtonBinding = VoiceButtonBinding(
    getInt(SettingsRepository.KEY_ALICE_KEYCODE, 0),
    voiceCompanionsFromCsv(getString(SettingsRepository.KEY_ALICE_COMPANIONS, null)),
)

/** Reserve saved projection assignments even while disabled; do not silently steal them. */
fun reservedVoiceKeys(context: Context): Set<Int> {
    val cluster = context.getSharedPreferences(ClusterProjectionManager.PREFS_NAME, Context.MODE_PRIVATE)
    return setOf(cluster.getInt(ClusterProjectionManager.KEY_TRIGGER_KEYCODE, DEFAULT_TRIGGER_KEYCODE))
}
