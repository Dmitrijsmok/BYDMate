package com.bydmate.app.voice

/**
 * Whether the session's microphone really hears anything, from the raw capture frames. A capture
 * Android silences (another app holds the mic on Android 10: Alice in Yandex Browser, Android
 * Auto) delivers frames of exact digital zeros; a working car microphone never does, its noise
 * floor alone is non-zero. Capture thread only.
 */
internal class MicLiveness(private val silentAfterMs: Long = SILENT_AFTER_MS) {
    enum class Event { LIVE, SILENT }

    private var live = false
    private var silentReported = false
    private var zeroMs = 0L

    /** [Event.LIVE] on the first frame with signal (again after a silence), [Event.SILENT] once
     *  per run of [silentAfterMs] of nothing but zeros, also when the mic went quiet mid-session
     *  (field 1.1.7: live at the press, then 30 s of nothing while another app took the mic);
     *  null otherwise. */
    fun onFrame(samples: ShortArray, frameMs: Long): Event? {
        if (samples.any { it.toInt() != 0 }) {
            zeroMs = 0L
            silentReported = false
            if (live) return null
            live = true
            return Event.LIVE
        }
        zeroMs += frameMs
        if (!silentReported && zeroMs >= silentAfterMs) {
            silentReported = true
            live = false
            return Event.SILENT
        }
        return null
    }

    companion object {
        const val SILENT_AFTER_MS = 1500L
    }
}
