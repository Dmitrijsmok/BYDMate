#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice5.4 window-percent anchor missing: {label}")
    return text.replace(old, new, 1)


# DiLink 3.0 has a CTRL family shared across generations:
#   1=open, 2=close, 3=stop, 4=half, 5=vent.
# Existing BYDMate already carries these CTRL allowlist entries. Expose only the
# local STOP tokens required by the closed-loop positioner; the cloud still sends
# semantic window.*.position actions and never sees raw FIDs/values.
p = Path("app/src/main/kotlin/com/bydmate/app/data/vehicle/CommandTranslator.kt")
s = p.read_text()
old = '''        "后右打开100" to Resolved("window_rear_right_open",  1),
        "后右打开0"   to Resolved("window_rear_right_close", 2),

        // ── Windows (vent, individual) ── crack one window to VENT_PCT via the
'''
new = '''        "后右打开100" to Resolved("window_rear_right_open",  1),
        "后右打开0"   to Resolved("window_rear_right_close", 2),

        // Local-only STOP controls used for exact Smart Home positioning on CTRL-based
        // firmware (DiLink 3.0). Value 3 is the CTRL stop code already present in the
        // cross-generation catalog/allowlist.
        "主驾停止" to Resolved("window_driver_ctrl", 3),
        "副驾停止" to Resolved("window_passenger_ctrl", 3),
        "后左停止" to Resolved("window_rear_left_ctrl", 3),
        "后右停止" to Resolved("window_rear_right_ctrl", 3),

        // ── Windows (vent, individual) ── crack one window to VENT_PCT via the
'''
s = once(s, old, new, "window stop translator entries")
p.write_text(s)


p = Path("app/src/main/kotlin/com/bydmate/app/data/remote/AlicePollingManager.kt")
s = p.read_text()

old = '''            val appResult = appCommandDispatcher.dispatch(cmd)
'''
new = '''            if (requested in WINDOW_POSITION_ACTIONS) {
                val target = if (cmd.has("value")) cmd.optInt("value", -1) else -1
                val result = if (target in 0..100) {
                    positionWindow(requested, target)
                } else {
                    Result.failure<Unit>(IllegalArgumentException("window_position_invalid:$target"))
                }
                val success = result.isSuccess
                val error = result.exceptionOrNull()?.message
                Log.i(TAG, "BRIDGE_WINDOW_POSITION id=$id action=$requested target=$target success=$success" +
                    (error?.let { " error=${it.take(160)}" } ?: ""))
                rememberResult(id, requested, success, error)
                results += AckResult(id, success, error?.take(240))
                continue
            }

            val appResult = appCommandDispatcher.dispatch(cmd)
'''
s = once(s, old, new, "window.position dispatch")


old = '''    private fun rememberResult(id: String, action: String, success: Boolean, error: String?) {
'''
new = '''    private suspend fun positionWindow(action: String, target: Int): Result<Unit> {
        val desired = target.coerceIn(0, 100)

        val openCommand = when (action) {
            "window.driver.position" -> "主驾打开100"
            "window.passenger.position" -> "副驾打开100"
            "window.rear_left.position" -> "后左打开100"
            "window.rear_right.position" -> "后右打开100"
            else -> return Result.failure(IllegalArgumentException("window_position_action_unknown:$action"))
        }
        val closeCommand = when (action) {
            "window.driver.position" -> "主驾打开0"
            "window.passenger.position" -> "副驾打开0"
            "window.rear_left.position" -> "后左打开0"
            "window.rear_right.position" -> "后右打开0"
            else -> return Result.failure(IllegalArgumentException("window_position_action_unknown:$action"))
        }
        val stopCommand = when (action) {
            "window.driver.position" -> "主驾停止"
            "window.passenger.position" -> "副驾停止"
            "window.rear_left.position" -> "后左停止"
            "window.rear_right.position" -> "后右停止"
            else -> return Result.failure(IllegalArgumentException("window_position_action_unknown:$action"))
        }

        // Preserve the already field-tested dedicated endpoints.
        if (desired == 0) return vehicleApi.dispatch(closeCommand)
        if (desired == 100) return vehicleApi.dispatch(openCommand)

        val start = currentWindowPosition(action)
            ?: return Result.failure(IllegalStateException("window_position_unavailable:$action"))

        if (kotlin.math.abs(start - desired) <= WINDOW_TARGET_TOLERANCE_PCT) {
            Log.i(TAG, "BRIDGE_WINDOW_POSITION already_at_target action=$action current=$start target=$desired")
            return Result.success(Unit)
        }

        val opening = desired > start
        if (opening) {
            // Existing BYDMate window gate: opening is fail-closed with unknown speed and
            // blocked above 120 km/h. Closing toward a smaller aperture remains allowed.
            val block = ActionDispatcher.speedGateBlockReason(openCommand, latestData?.speed)
            if (block != null) {
                return Result.failure(
                    IllegalStateException("window_position_blocked:${block.javaClass.simpleName}")
                )
            }
        }

        val started = vehicleApi.dispatch(if (opening) openCommand else closeCommand)
        if (started.isFailure) return started

        val deadline = System.currentTimeMillis() + WINDOW_POSITION_TIMEOUT_MS
        var last = start
        var reached = false

        while (System.currentTimeMillis() < deadline) {
            delay(WINDOW_POSITION_SAMPLE_MS)
            val current = currentWindowPosition(action) ?: continue
            last = current

            val crossed = if (opening) current >= desired else current <= desired
            val near = kotlin.math.abs(current - desired) <= WINDOW_TARGET_TOLERANCE_PCT
            if (crossed || near) {
                reached = true
                break
            }
        }

        // CTRL value 3 is STOP. Always attempt it after a partial move, even on timeout.
        val stopped = vehicleApi.dispatch(stopCommand)
        if (stopped.isFailure) return stopped

        delay(WINDOW_SETTLE_MS)
        val finalPosition = currentWindowPosition(action) ?: last

        Log.i(
            TAG,
            "BRIDGE_WINDOW_POSITION action=$action target=$desired start=$start observed=$last " +
                "final=$finalPosition reached=$reached"
        )

        if (!reached) {
            return Result.failure(
                IllegalStateException("window_position_timeout:$action:target=$desired:last=$finalPosition")
            )
        }

        if (kotlin.math.abs(finalPosition - desired) > WINDOW_FINAL_TOLERANCE_PCT) {
            return Result.failure(
                IllegalStateException("window_position_miss:$action:target=$desired:final=$finalPosition")
            )
        }

        return Result.success(Unit)
    }

    private fun currentWindowPosition(action: String): Int? = when (action) {
        "window.driver.position" -> latestData?.windowFL
        "window.passenger.position" -> latestData?.windowFR
        "window.rear_left.position" -> latestData?.windowRL
        "window.rear_right.position" -> latestData?.windowRR
        else -> null
    }

    private fun rememberResult(id: String, action: String, success: Boolean, error: String?) {
'''
s = once(s, old, new, "closed-loop window positioning")


old = '''        private const val SUNROOF_FINAL_TOLERANCE_PCT = 4
    }
'''
new = '''        private const val SUNROOF_FINAL_TOLERANCE_PCT = 4

        private val WINDOW_POSITION_ACTIONS = setOf(
            "window.driver.position",
            "window.passenger.position",
            "window.rear_left.position",
            "window.rear_right.position",
        )
        private const val WINDOW_POSITION_SAMPLE_MS = 60L
        private const val WINDOW_SETTLE_MS = 250L
        private const val WINDOW_POSITION_TIMEOUT_MS = 12_000L
        private const val WINDOW_TARGET_TOLERANCE_PCT = 2
        private const val WINDOW_FINAL_TOLERANCE_PCT = 6
    }
'''
s = once(s, old, new, "window positioning constants")

p.write_text(s)

print("Alice 5.4 window percent applied: closed-loop 0..100 positioning via open/close + CTRL stop")
