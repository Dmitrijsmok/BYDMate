package com.bydmate.app.data.vehicle

import kotlin.math.abs

/**
 * Closed-loop side window positioning: the pane is driven with its CTRL open or close command,
 * its position is polled, and CTRL stop is sent once the readback passes the target. The fork's
 * 3.17 line drove Alice percentages this way on an ATTO 3 / DiLink 3.0 (AliceApertureController);
 * it is the one implementation for every percentage that the percent family cannot place (see
 * VehicleApiImpl.percentWindow): local voice, Alice, the agent and automations alike.
 *
 * Two bounds keep a pane whose readback lags or never changes from running to the end stop:
 * a pane that shows no movement within [NO_MOVE_MS] is stopped and reported [Outcome.NoMove],
 * and every move is stopped after [travelCapMs] (the travel time the distance needs on a slow
 * window, doubled) even when the readback has not reached the target yet.
 *
 * Pure: every car access goes through [Io]; elapsed time is the larger of the real clock and
 * the pauses taken, so a test with virtual time ends the same loops a car does.
 */
internal class WindowStepper(
    private val io: Io,
    private val realMs: () -> Long = { System.nanoTime() / NANOS_PER_MS },
) {
    enum class Move { OPEN, CLOSE, STOP }

    interface Io {
        /** Sends [move] to [pane]'s CTRL fid; true when the car accepted the write. */
        suspend fun command(pane: WindowPane, move: Move): Boolean

        /** [pane]'s position in percent (0 = closed), or null when it cannot be read. */
        suspend fun position(pane: WindowPane): Int?

        suspend fun pause(ms: Long)
    }

    sealed interface Outcome {
        val success: Boolean get() = false

        /** Within reach of the target: nothing was sent. */
        data class AlreadyThere(val position: Int) : Outcome {
            override val success get() = true
        }

        /** Stopped at (or, by the late sample, near) the target. */
        data class Reached(val position: Int?) : Outcome {
            override val success get() = true
        }

        /** No position to start from: nothing was sent. */
        data object Unreadable : Outcome

        /** The open/close write was refused: nothing moved. */
        data object NotStarted : Outcome

        /** The pane never moved after an accepted open/close; stop was sent all the same. */
        data class NoMove(val position: Int) : Outcome

        /** Moved and stopped, but away from the target (or the readback never showed it). */
        data class Missed(val position: Int?) : Outcome

        /** The stop write was refused: the pane may still be travelling. */
        data object StopFailed : Outcome
    }

    suspend fun moveTo(pane: WindowPane, target: Int): Outcome {
        val start = io.position(pane) ?: return Outcome.Unreadable
        if (abs(start - target) <= START_TOLERANCE) return Outcome.AlreadyThere(start)
        val opening = target > start
        if (!io.command(pane, if (opening) Move.OPEN else Move.CLOSE)) return Outcome.NotStarted
        val travel = travel(pane, start, target, opening)
        val stop = stop(pane)
        val final = stop.finalPosition
        val moved = travel.moved || (final != null && abs(final - start) > MOVE_TOLERANCE)
        return when {
            !stop.accepted -> Outcome.StopFailed
            !moved -> Outcome.NoMove(start)
            windowMoveSucceeded(travel.reached, true, final, target) -> Outcome.Reached(final ?: travel.reached)
            else -> Outcome.Missed(final)
        }
    }

    private class Travel(val reached: Int?, val moved: Boolean)

    private class StopResult(val accepted: Boolean, val finalPosition: Int?)

    /** Polls [pane] until it passes [target], stays still for [NO_MOVE_MS], or the cap runs out. */
    private suspend fun travel(pane: WindowPane, start: Int, target: Int, opening: Boolean): Travel {
        val clock = Elapsed()
        val cap = travelCapMs(abs(target - start))
        var moved = false
        while (true) {
            clock.pause(SAMPLE_MS)
            val now = io.position(pane)
            if (now != null && abs(now - start) > MOVE_TOLERANCE) moved = true
            if (now != null && if (opening) now >= target else now <= target) return Travel(now, true)
            val elapsed = clock.ms()
            if (!moved && elapsed >= NO_MOVE_MS) return Travel(null, false)
            if (elapsed >= cap) return Travel(null, moved)
        }
    }

    /** Stop, and once more when two samples show the pane still travelling (the fork's sequence). */
    private suspend fun stop(pane: WindowPane): StopResult {
        if (!io.command(pane, Move.STOP)) return StopResult(false, null)
        io.pause(STOP_SAMPLE_MS)
        val first = io.position(pane)
        io.pause(STOP_SAMPLE_MS)
        val second = io.position(pane)
        if (first != null && second != null && abs(second - first) > START_TOLERANCE) {
            io.command(pane, Move.STOP)
        }
        io.pause(STOP_SETTLE_MS)
        return StopResult(true, io.position(pane) ?: second ?: first)
    }

    /** Elapsed time of one move: the real clock, or the pauses taken when they are ahead of it. */
    private inner class Elapsed {
        private val startedAt = realMs()
        private var paused = 0L

        suspend fun pause(ms: Long) {
            io.pause(ms)
            paused += ms
        }

        fun ms(): Long = maxOf(realMs() - startedAt, paused)
    }

    companion object {
        /** Readback noise of a standing pane; a pane within it of the target is not moved. */
        const val START_TOLERANCE = 2
        /** Change from the start that proves the pane moves. */
        const val MOVE_TOLERANCE = 2
        const val SAMPLE_MS = 40L
        /** A commanded pane shows movement well inside this; otherwise it is stopped. */
        const val NO_MOVE_MS = 1_200L
        /** Motor start plus readback latency, added to every cap. */
        const val START_LATENCY_MS = 600L
        /** Full travel of a slow side window (ATTO 3 class: ~3.5-4 s), in ms per 100 %. */
        const val FULL_TRAVEL_MS = 4_000L
        /** The cap allows twice the travel time of the distance. */
        private const val TRAVEL_MARGIN = 2
        private const val STOP_SAMPLE_MS = 120L
        private const val STOP_SETTLE_MS = 180L
        private const val NANOS_PER_MS = 1_000_000L

        /** How long a move of [distance] percent may run before it is stopped regardless. */
        fun travelCapMs(distance: Int): Long =
            START_LATENCY_MS + FULL_TRAVEL_MS * TRAVEL_MARGIN * distance.coerceIn(0, 100) / 100
    }
}

/**
 * Whether a driven move ended where it was asked to: STOP accepted and the target seen on the
 * way, or a late final sample that is near it. On an ATTO 3 the readback can lag or jump after
 * the STOP write, so a target seen before an accepted STOP is a success whatever the late
 * sample says (fork 3.17, AliceApertureController).
 */
internal fun windowMoveSucceeded(
    reached: Int?,
    stopAccepted: Boolean,
    finalPosition: Int?,
    target: Int,
): Boolean {
    if (!stopAccepted) return false
    if (reached != null) return true
    return finalPosition?.let { abs(it - target) <= FINAL_TOLERANCE } == true
}

private const val FINAL_TOLERANCE = 6
