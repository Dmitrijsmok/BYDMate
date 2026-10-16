package com.bydmate.app.cluster

import android.accessibilityservice.AccessibilityService
import android.media.AudioManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.widget.Toast
import com.bydmate.app.R

internal enum class HandoffResult { WAIT, READY, TIMEOUT }

/** A transient/unknown window or an active recorder resets confirmation; timeout fails closed. */
internal class AliceLocalHandoff(private val startedAt: Long) {
    private var clearSince: Long? = null

    fun observe(now: Long, exitConfirmed: Boolean): HandoffResult {
        if (now - startedAt > 4_000L) return HandoffResult.TIMEOUT
        if (!exitConfirmed) clearSince = null
        else if (clearSince == null) clearSince = now
        return if (clearSince?.let { now - it >= 1_200L } == true) HandoffResult.READY else HandoffResult.WAIT
    }
}

/** Dedicated-button guard. No audio capture or routing changes; observations fail closed. */
internal class AliceLocalHandoffRunner(
    private val service: AccessibilityService,
    private val ownsSession: () -> Boolean,
    private val localActive: () -> Boolean,
    private val cancelAlice: () -> Unit,
    private val releaseAlice: () -> Unit,
    private val requiresExit: () -> Boolean = { true },
) {
    private val handler = Handler(Looper.getMainLooper())
    var active = false
        private set

    val recorderIdle: Boolean get() = runCatching {
        service.getSystemService(AudioManager::class.java)?.activeRecordingConfigurations?.isEmpty() == true
    }.getOrDefault(false)

    fun requestLocal(onReady: () -> Unit) {
        if (active) return
        if (!ownsSession()) {
            // A PTT toggle must still be able to stop its own Local session.
            if (localActive() || recorderIdle) onReady() else refuse()
            return
        }
        val waitForExit = requiresExit()
        cancelAlice()
        start(waitForExit) {
            releaseAlice()
            onReady()
        }
    }

    private fun start(waitForExit: Boolean, onReady: () -> Unit) {
        active = true
        val pkg = activePackage()
        if (waitForExit && pkg != null && isAliceContextPackage(pkg)) {
            service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
        }
        awaitExit(AliceLocalHandoff(SystemClock.elapsedRealtime()), waitForExit, onReady)
    }

    fun cancel() {
        handler.removeCallbacksAndMessages(null)
        active = false
    }

    private fun activePackage(): String? = runCatching {
        service.rootInActiveWindow?.packageName?.toString()?.takeIf { it.isNotBlank() }
    }.getOrNull()

    private fun awaitExit(gate: AliceLocalHandoff, waitForExit: Boolean, onReady: () -> Unit) {
        val pkg = activePackage()
        val windowClear = !waitForExit || (pkg != null && !isAliceContextPackage(pkg))
        val confirmed = windowClear && recorderIdle
        when (gate.observe(SystemClock.elapsedRealtime(), confirmed)) {
            HandoffResult.READY -> { cancel(); onReady() }
            HandoffResult.WAIT -> handler.postDelayed({ awaitExit(gate, waitForExit, onReady) }, 180L)
            HandoffResult.TIMEOUT -> { cancel(); refuse() }
        }
    }

    fun refuse() {
        Toast.makeText(service, R.string.voice_button_handoff_failed, Toast.LENGTH_LONG).show()
    }
}
