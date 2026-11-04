package com.bydmate.app.data.remote

import com.bydmate.app.data.automation.ActionDispatcher
import com.bydmate.app.data.vehicle.VehicleApi
import kotlinx.coroutines.delay
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.math.abs

/**
 * Closed-loop window percentages for the Alice bridge («открой окно водителя на 40 процентов»).
 * The percent write is tried first; where it does not land (DiLink 3.0 has no percent family and
 * routes it to the nearest CTRL detent) the pane is driven open/close and stopped once its
 * readback passes the target. Sunroof percentages are the three detents only: 0, 50 (half slide)
 * and 100.
 *
 * Every opening move asks [speedNow] (a direct speed read) and goes through ActionDispatcher's
 * speed gate, failing closed on an unknown speed like any gated automation step.
 */
@Singleton
class AliceApertureController @Inject constructor(
    private val vehicleApi: VehicleApi,
) {
    suspend fun positionWindow(action: String, target: Int, speedNow: suspend () -> Int?): Result<Unit> {
        if (target !in 0..100) return failure("invalid_window_position")
        val channel = windowChannel(action) ?: return failure("unknown_window")
        windowEndpoint(channel, target, speedNow)?.let { return it }

        val start = channel.read() ?: return failure("window_position_unavailable")
        if (near(start, target, 2)) return Result.success(Unit)
        blockOpening(channel.open, target > start, speedNow)?.let { return it }

        if (tryNativeWindowPosition(channel, target)) return Result.success(Unit)
        return moveWindowToTarget(channel, target, start, speedNow)
    }

    suspend fun positionSunroof(target: Int, speedNow: suspend () -> Int?): Result<Unit> = when (target) {
        0 -> vehicleApi.dispatch(SUNROOF_CLOSE)
        50 -> blockOpening(SUNROOF_HALF, true, speedNow) ?: vehicleApi.dispatch(SUNROOF_HALF)
        100 -> blockOpening(SUNROOF_OPEN, true, speedNow) ?: vehicleApi.dispatch(SUNROOF_OPEN)
        else -> failure("sunroof_percent_not_supported")
    }

    private suspend fun windowEndpoint(
        channel: WindowChannel,
        target: Int,
        speedNow: suspend () -> Int?,
    ): Result<Unit>? = when (target) {
        0 -> vehicleApi.dispatch(channel.close)
        100 -> blockOpening(channel.open, true, speedNow) ?: vehicleApi.dispatch(channel.open)
        else -> null
    }

    private suspend fun tryNativeWindowPosition(channel: WindowChannel, target: Int): Boolean {
        if (channel.write(target).isFailure) return false
        val reached = waitForTarget(
            channel.read,
            WaitSpec(target, true, NATIVE_WAIT_MS, NATIVE_SAMPLE_MS, NATIVE_TOLERANCE, false),
        ) ?: return false
        delay(NATIVE_SETTLE_MS)
        val settled = channel.read() ?: reached
        return near(settled, target, NATIVE_TOLERANCE)
    }

    private suspend fun moveWindowToTarget(
        channel: WindowChannel,
        target: Int,
        start: Int,
        speedNow: suspend () -> Int?,
    ): Result<Unit> {
        val current = channel.read() ?: start
        val opening = target > current
        blockOpening(channel.open, opening, speedNow)?.let { return it }

        val started = vehicleApi.dispatch(if (opening) channel.open else channel.close)
        if (started.isFailure) return started

        val reached = waitForTarget(
            channel.read,
            WaitSpec(target, opening, MOVE_WAIT_MS, MOVE_SAMPLE_MS, 1),
        )
        val stopped = stopWindow(channel)
        if (!stopped.commandAccepted) return failure("window_stop_failed")

        // On ATTO 3 the percentage readback can lag or jump after the STOP write. Once the
        // controller actually observed the requested threshold and STOP was accepted, reporting
        // window_position_miss is a false negative even though the pane visibly moved correctly.
        // A late final sample may also be the first one that reflects the target.
        return if (windowMoveSucceeded(reached, stopped.commandAccepted, stopped.finalPosition, target)) {
            Result.success(Unit)
        } else {
            failure("window_position_miss")
        }
    }

    private suspend fun stopWindow(channel: WindowChannel): StopOutcome {
        val firstStop = vehicleApi.dispatch(channel.stop)
        if (firstStop.isFailure) return StopOutcome(commandAccepted = false, finalPosition = null)
        delay(STOP_SAMPLE_MS)
        val first = channel.read()
        delay(STOP_SAMPLE_MS)
        val second = channel.read()
        // Still moving after the first STOP: send it once more.
        if (first != null && second != null && abs(second - first) > 2) {
            vehicleApi.dispatch(channel.stop)
        }
        delay(STOP_SETTLE_MS)
        return StopOutcome(commandAccepted = true, finalPosition = channel.read())
    }

    private suspend fun waitForTarget(read: suspend () -> Int?, spec: WaitSpec): Int? {
        val deadline = System.currentTimeMillis() + spec.timeoutMs
        while (System.currentTimeMillis() < deadline) {
            delay(spec.sampleMs)
            val value = read()
            if (value != null && reached(value, spec)) return value
        }
        return null
    }

    private suspend fun blockOpening(command: String, opening: Boolean, speedNow: suspend () -> Int?): Result<Unit>? {
        if (!opening) return null
        val reason = ActionDispatcher.speedOnlyBlockReason(command, speedNow()) ?: return null
        return failure(reason.javaClass.simpleName)
    }

    private fun windowChannel(action: String): WindowChannel? = when (action) {
        "window.driver.position" -> WindowChannel(
            "主驾打开100", "主驾打开0", "主驾停止",
            { vehicleApi.readWindowDriver() }, { vehicleApi.writeWindowDriver(it) },
        )
        "window.passenger.position" -> WindowChannel(
            "副驾打开100", "副驾打开0", "副驾停止",
            { vehicleApi.readWindowPassenger() }, { vehicleApi.writeWindowPassenger(it) },
        )
        "window.rear_left.position" -> WindowChannel(
            "后左打开100", "后左打开0", "后左停止",
            { vehicleApi.readWindowRearLeft() }, { vehicleApi.writeWindowRearLeft(it) },
        )
        "window.rear_right.position" -> WindowChannel(
            "后右打开100", "后右打开0", "后右停止",
            { vehicleApi.readWindowRearRight() }, { vehicleApi.writeWindowRearRight(it) },
        )
        else -> null
    }

    private data class WindowChannel(
        val open: String,
        val close: String,
        val stop: String,
        val read: suspend () -> Int?,
        val write: suspend (Int) -> Result<Unit>,
    )

    private data class StopOutcome(val commandAccepted: Boolean, val finalPosition: Int?)

    private companion object {
        const val SUNROOF_OPEN = "天窗打开100"
        const val SUNROOF_HALF = "天窗打开50"
        const val SUNROOF_CLOSE = "天窗打开0"
        const val NATIVE_WAIT_MS = 1_500L
        const val NATIVE_SAMPLE_MS = 100L
        const val NATIVE_SETTLE_MS = 150L
        const val NATIVE_TOLERANCE = 6
        const val MOVE_WAIT_MS = 12_000L
        const val MOVE_SAMPLE_MS = 40L
        const val STOP_SAMPLE_MS = 120L
        const val STOP_SETTLE_MS = 180L
    }
}

/**
 * Whether a driven move ended where it was asked to: STOP accepted and the target seen on the
 * way, or a late final sample that is near it. Pure, kept outside the class for its test.
 */
internal fun windowMoveSucceeded(
    reached: Int?,
    stopAccepted: Boolean,
    finalPosition: Int?,
    target: Int,
): Boolean {
    if (!stopAccepted) return false
    if (reached != null) return true
    return finalPosition?.let { near(it, target, FINAL_TOLERANCE) } == true
}

private const val FINAL_TOLERANCE = 6

private data class WaitSpec(
    val target: Int,
    val opening: Boolean,
    val timeoutMs: Long,
    val sampleMs: Long,
    val tolerance: Int,
    val directional: Boolean = true,
)

private fun reached(value: Int, spec: WaitSpec): Boolean {
    if (near(value, spec.target, spec.tolerance)) return true
    if (!spec.directional) return false
    return if (spec.opening) value >= spec.target else value <= spec.target
}

private fun near(value: Int, target: Int, tolerance: Int): Boolean = abs(value - target) <= tolerance

private fun failure(message: String): Result<Unit> = Result.failure(IllegalStateException(message))
