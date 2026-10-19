package com.bydmate.app.voice

import android.content.Context
import com.bydmate.app.BuildConfig
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AsrLabStore @Inject constructor(@ApplicationContext context: Context) {
    private val prefs = context.getSharedPreferences("asr_lab", Context.MODE_PRIVATE)
    private val selected = MutableStateFlow(prefs.getInt("pre_roll_ms", 0).takeIf { it in speechPreRollDurations } ?: 0)
    val selectedMs = selected.asStateFlow()
    private val history = MutableStateFlow<List<AsrLabResult>>(emptyList())
    val results = history.asStateFlow()

    fun select(ms: Int) {
        require(ms in speechPreRollDurations)
        prefs.edit().putInt("pre_roll_ms", ms).apply()
        selected.value = ms
    }

    fun add(result: AsrLabResult) { history.value = (listOf(result) + history.value).take(100) }
    fun clear() { history.value = emptyList() }
    fun csv() = labCsv(history.value, BuildConfig.VERSION_NAME, BuildConfig.VERSION_CODE, BuildConfig.ASR_LAB_BASELINE)
}
