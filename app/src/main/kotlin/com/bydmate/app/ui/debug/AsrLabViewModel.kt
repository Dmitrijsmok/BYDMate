package com.bydmate.app.ui.debug

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.bydmate.app.voice.AsrLabAttempt
import com.bydmate.app.voice.AsrLabStore
import com.bydmate.app.voice.VoiceController
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AsrLabViewModel @Inject constructor(
    val store: AsrLabStore,
    private val voice: VoiceController,
) : ViewModel() {
    val running = MutableStateFlow(false)
    private var test: Job? = null

    fun start() {
        if (running.value) return
        val attempt = AsrLabAttempt(store.selectedMs.value)
        running.value = true
        test = viewModelScope.launch {
            try {
                store.add(voice.runAsrLab(attempt))
            } catch (cancelled: CancellationException) {
                store.add(attempt.result("cancelled"))
                throw cancelled
            } finally {
                running.value = false
            }
        }
    }

    fun stop() { test?.cancel() }
}
