package com.bydmate.app.cluster

/** A primary DOWN invokes the action; learned companion codes are consumed, never invoked. */
data class VoiceButtonBinding(val primary: Int = 0, val companions: Set<Int> = emptySet()) {
    val codes: Set<Int> get() = if (primary > 0) companions + primary else emptySet()

    fun canAssign(occupied: Set<Int>): Boolean =
        primary > 0 && codes.all { isVoiceAssignable(it) && it !in occupied }
}

// Only new voice assignments use this stricter gate. Existing projection/automation behavior stays intact.
fun isVoiceAssignable(code: Int): Boolean = code > 0 && isAssignable(code) &&
    code !in setOf(79, 85, 86, 87, 88, 89, 90, 91, 126, 127, 129, 130, 164, 220, 221, 222, 223, 224, 225, 226, 272, 273, 274, 275, VOLUME_KNOB_PRESS_KEYCODE)

enum class VoiceButtonTarget { LOCAL, ALICE, COMPANION, UNASSIGNED }

fun assignedVoiceTarget(key: Int, local: VoiceButtonBinding, alice: VoiceButtonBinding): VoiceButtonTarget = when {
    key <= 0 -> VoiceButtonTarget.UNASSIGNED
    key == local.primary -> VoiceButtonTarget.LOCAL
    key == alice.primary -> VoiceButtonTarget.ALICE
    key in local.codes || key in alice.codes -> VoiceButtonTarget.COMPANION
    else -> VoiceButtonTarget.UNASSIGNED
}

/** Keep the existing opt-in Android 10 fallback until a complete observed pair replaces it. */
fun useLegacyVoiceFallback(
    sdk: Int,
    nativeTakeover: Boolean,
    local: VoiceButtonBinding,
    alice: VoiceButtonBinding,
): Boolean = sdk <= 29 && nativeTakeover &&
    !local.codes.containsAll(setOf(304, 327)) && !alice.codes.containsAll(setOf(304, 327))

// The companion window and CSV format are upstream's (SteeringWheelKeyDecision.kt); the voice
// buttons only add the stricter isVoiceAssignable gate on top.
fun isVoiceLearnCompanion(keyCode: Int, isDown: Boolean, primaryKeyCode: Int, primaryAtMs: Long, nowMs: Long): Boolean =
    isLearnCompanion(keyCode, isDown, primaryKeyCode, primaryAtMs, nowMs) && isVoiceAssignable(keyCode)

/** A stored companion list is used only when every code is still voice-assignable. */
fun voiceBindingCompanionsFromCsv(csv: String?): Set<Int> =
    voiceCompanionsFromCsv(csv).takeIf { codes -> codes.all(::isVoiceAssignable) } ?: emptySet()

/** DOWN/UP identity is device-specific; repeats cannot become a second gesture. */
internal class VoiceButtonPresses {
    private val down = mutableMapOf<Pair<Int, Int>, Long>()

    fun firstDown(key: Int, device: Int, downTime: Long, repeat: Int): Boolean {
        if (repeat != 0) return false
        val identity = key to device
        if (down[identity] == downTime) return false
        down[identity] = downTime
        return true
    }

    fun release(key: Int, device: Int) { down.remove(key to device) }
    fun clear() { down.clear() }
}
