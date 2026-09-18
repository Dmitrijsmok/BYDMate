#!/usr/bin/env python3
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Alice5.4 anchor missing: {label}")
    return text.replace(old, new, 1)


# Identity: install as a normal update over Alice 5.3 with the same stable signer.
p = Path("app/build.gradle.kts")
s = p.read_text()
s = once(s, "versionCode = 64014", "versionCode = 64015", "versionCode")
s = once(
    s,
    'versionName = "3.16.0-alice5.3-upstream-rebase"',
    'versionName = "3.16.0-alice5.4-sunroof-percent"',
    "versionName",
)
p.write_text(s)


# Smart Home can now ask for a semantic sunroof.position with value 0..100.
# The car exposes a validated percent READBACK but the validated WRITE surface is
# mode-based (open/close/tilt/stop). Therefore arbitrary positions are achieved
# locally in BYDMate as a closed loop:
#   start opening/closing -> watch live sunroof % -> STOP at target.
# This keeps raw FIDs out of the cloud and uses only already validated vehicle commands.
p = Path("app/src/main/kotlin/com/bydmate/app/data/remote/AlicePollingManager.kt")
s = p.read_text()

old = '''            val requested = cmd.optString("action", "<missing>").trim().lowercase()

            val appResult = appCommandDispatcher.dispatch(cmd)
'''
new = '''            val requested = cmd.optString("action", "<missing>").trim().lowercase()

            if (requested == "sunroof.position") {
                val target = if (cmd.has("value")) cmd.optInt("value", -1) else -1
                val result = if (target in 0..100) {
                    positionSunroof(target)
                } else {
                    Result.failure<Unit>(IllegalArgumentException("sunroof_position_invalid:$target"))
                }
                val success = result.isSuccess
                val error = result.exceptionOrNull()?.message
                Log.i(TAG, "BRIDGE_SUNROOF_POSITION id=$id target=$target success=$success" +
                    (error?.let { " error=${it.take(160)}" } ?: ""))
                rememberResult(id, requested, success, error)
                results += AckResult(id, success, error?.take(240))
                continue
            }

            val appResult = appCommandDispatcher.dispatch(cmd)
'''
s = once(s, old, new, "sunroof.position dispatch")

old = '''        if (results.isNotEmpty()) ack(endpoint, apiKey, results)
    }

    private fun rememberResult(id: String, action: String, success: Boolean, error: String?) {
'''
new = '''        if (results.isNotEmpty()) ack(endpoint, apiKey, results)
    }

    private suspend fun positionSunroof(target: Int): Result<Unit> {
        val desired = target.coerceIn(0, 100)

        // Full close is always safe and does not need a position snapshot.
        if (desired == 0) {
            return vehicleApi.dispatch("天窗打开0")
        }

        val start = latestData?.sunroof
            ?: return Result.failure(IllegalStateException("sunroof_position_unavailable"))

        if (kotlin.math.abs(start - desired) <= SUNROOF_TARGET_TOLERANCE_PCT) {
            Log.i(TAG, "BRIDGE_SUNROOF_POSITION already_at_target current=$start target=$desired")
            return Result.success(Unit)
        }

        // Any movement that increases aperture uses the existing fail-closed 80 km/h
        // sunroof gate. Closing toward a smaller percentage remains allowed.
        if (desired > start) {
            val block = ActionDispatcher.speedGateBlockReason("天窗打开$desired", latestData?.speed)
            if (block != null) {
                return Result.failure(
                    IllegalStateException("sunroof_position_blocked:${block.javaClass.simpleName}")
                )
            }
        }

        // Keep the three native detents native; they are the most accurate endpoints.
        if (desired == 50) {
            return vehicleApi.dispatch("天窗打开50")
        }
        if (desired == 100) {
            return vehicleApi.dispatch("天窗打开100")
        }

        val opening = desired > start
        val motionCommand = if (opening) "天窗打开100" else "天窗打开0"
        val started = vehicleApi.dispatch(motionCommand)
        if (started.isFailure) return started

        val deadline = System.currentTimeMillis() + SUNROOF_POSITION_TIMEOUT_MS
        var last = start
        var reached = false

        while (System.currentTimeMillis() < deadline) {
            delay(SUNROOF_POSITION_SAMPLE_MS)
            val current = latestData?.sunroof ?: continue
            last = current

            val crossed = if (opening) current >= desired else current <= desired
            val near = kotlin.math.abs(current - desired) <= SUNROOF_TARGET_TOLERANCE_PCT
            if (crossed || near) {
                reached = true
                break
            }
        }

        // STOP is always sent after a partial-position attempt, including timeout.
        val stopped = vehicleApi.dispatch("天窗停止")
        if (stopped.isFailure) return stopped

        delay(SUNROOF_SETTLE_MS)
        val finalPosition = latestData?.sunroof ?: last
        Log.i(
            TAG,
            "BRIDGE_SUNROOF_POSITION target=$desired start=$start observed=$last final=$finalPosition reached=$reached"
        )

        if (!reached) {
            return Result.failure(
                IllegalStateException("sunroof_position_timeout:target=$desired:last=$finalPosition")
            )
        }

        if (kotlin.math.abs(finalPosition - desired) > SUNROOF_FINAL_TOLERANCE_PCT) {
            return Result.failure(
                IllegalStateException("sunroof_position_miss:target=$desired:final=$finalPosition")
            )
        }

        return Result.success(Unit)
    }

    private fun rememberResult(id: String, action: String, success: Boolean, error: String?) {
'''
s = once(s, old, new, "closed-loop sunroof positioning")

old = '''        private const val STATE_REPORT_EVERY = 10
    }
'''
new = '''        private const val STATE_REPORT_EVERY = 10

        // Closed-loop sunroof positioning uses the live percent readback already present
        // in DiParsData. Ten-percent voice steps are expected; these tolerances only
        // absorb telemetry/actuator latency and never change the requested target.
        private const val SUNROOF_POSITION_SAMPLE_MS = 75L
        private const val SUNROOF_SETTLE_MS = 300L
        private const val SUNROOF_POSITION_TIMEOUT_MS = 15_000L
        private const val SUNROOF_TARGET_TOLERANCE_PCT = 1
        private const val SUNROOF_FINAL_TOLERANCE_PCT = 4
    }
'''
s = once(s, old, new, "sunroof positioning constants")

p.write_text(s)

print("Alice 5.4 applied: closed-loop Smart Home sunroof percentage positioning")
