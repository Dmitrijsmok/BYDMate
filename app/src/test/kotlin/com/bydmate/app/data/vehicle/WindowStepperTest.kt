package com.bydmate.app.data.vehicle

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The closed loop the ATTO 3 / DiLink 3.0 windows fall back to: CTRL open/close, the position
 * polled, CTRL stop at the target. A simulated pane travels [ratePerMs] percent per millisecond
 * of pause while it is commanded; time is virtual (the pauses), the real clock stands still.
 */
class WindowStepperTest {

    private class Pane(
        var position: Int,
        private val ratePerMs: Double = 0.025, // 4 s for 100 %
        var moves: Boolean = true,
        var readable: Boolean = true,
        var acceptStop: Boolean = true,
        var acceptStart: Boolean = true,
    ) : WindowStepper.Io {
        val commands = mutableListOf<WindowStepper.Move>()
        var elapsedMs = 0L
        private var direction = 0
        private var exact = position.toDouble()

        override suspend fun command(pane: WindowPane, move: WindowStepper.Move): Boolean {
            commands += move
            val accepted = if (move == WindowStepper.Move.STOP) acceptStop else acceptStart
            if (!accepted) return false
            direction = when (move) {
                WindowStepper.Move.OPEN -> 1
                WindowStepper.Move.CLOSE -> -1
                WindowStepper.Move.STOP -> 0
            }
            return true
        }

        override suspend fun position(pane: WindowPane): Int? = if (readable) position else null

        override suspend fun pause(ms: Long) {
            elapsedMs += ms
            if (moves && direction != 0) {
                exact = (exact + direction * ratePerMs * ms).coerceIn(0.0, 100.0)
                position = exact.toInt()
            }
        }
    }

    private fun stepper(pane: Pane) = WindowStepper(pane, realMs = { 0L })

    @Test fun `opening to a percentage stops at the target`() = runBlocking {
        val pane = Pane(0)
        val outcome = stepper(pane).moveTo(WindowPane.DRIVER, 10)

        assertTrue(outcome.toString(), outcome.success)
        assertEquals(WindowStepper.Move.OPEN, pane.commands.first())
        assertEquals(WindowStepper.Move.STOP, pane.commands[1])
        assertTrue("stopped at ${pane.position}", pane.position in 10..12)
    }

    @Test fun `closing to a percentage drives the pane down`() = runBlocking {
        val pane = Pane(80)
        val outcome = stepper(pane).moveTo(WindowPane.REAR_LEFT, 50)

        assertTrue(outcome.toString(), outcome.success)
        assertEquals(listOf(WindowStepper.Move.CLOSE, WindowStepper.Move.STOP), pane.commands)
        assertTrue("stopped at ${pane.position}", pane.position in 48..50)
    }

    @Test fun `a pane already at the target is not commanded`() = runBlocking {
        val pane = Pane(51)
        assertEquals(WindowStepper.Outcome.AlreadyThere(51), stepper(pane).moveTo(WindowPane.DRIVER, 50))
        assertTrue(pane.commands.isEmpty())
    }

    @Test fun `a pane that never moves is stopped and reported as such`() = runBlocking {
        val pane = Pane(0, moves = false)
        val outcome = stepper(pane).moveTo(WindowPane.DRIVER, 50)

        assertEquals(WindowStepper.Outcome.NoMove(0), outcome)
        assertEquals(listOf(WindowStepper.Move.OPEN, WindowStepper.Move.STOP), pane.commands)
        assertTrue(pane.elapsedMs < WindowStepper.travelCapMs(50))
    }

    /** A readback that never follows the glass: the time cap stops it near the travel time. */
    @Test fun `a frozen readback is bounded by the travel cap`() = runBlocking {
        val pane = object : WindowStepper.Io {
            val inner = Pane(0)
            var moved = false
            override suspend fun command(pane: WindowPane, move: WindowStepper.Move) = inner.command(pane, move)
            override suspend fun position(pane: WindowPane): Int? = if (moved) 3 else 0
            override suspend fun pause(ms: Long) { inner.pause(ms); if (inner.position > 3) moved = true }
        }
        val outcome = WindowStepper(pane, realMs = { 0L }).moveTo(WindowPane.DRIVER, 10)

        assertTrue(outcome is WindowStepper.Outcome.Missed)
        // Stopped by the cap: 600 + 80 * 10 ms, then the stop samples; the glass stays bounded.
        assertTrue("glass at ${pane.inner.position}", pane.inner.position <= 40)
        assertEquals(WindowStepper.Move.STOP, pane.inner.commands[1])
    }

    @Test fun `no position means nothing is sent`() = runBlocking {
        val pane = Pane(0, readable = false)
        assertEquals(WindowStepper.Outcome.Unreadable, stepper(pane).moveTo(WindowPane.DRIVER, 50))
        assertTrue(pane.commands.isEmpty())
    }

    @Test fun `a refused start is reported and nothing else is sent`() = runBlocking {
        val pane = Pane(0, acceptStart = false)
        assertEquals(WindowStepper.Outcome.NotStarted, stepper(pane).moveTo(WindowPane.DRIVER, 50))
        assertEquals(listOf(WindowStepper.Move.OPEN), pane.commands)
    }

    @Test fun `a refused stop is never a success`() = runBlocking {
        val pane = Pane(0, acceptStop = false)
        assertEquals(WindowStepper.Outcome.StopFailed, stepper(pane).moveTo(WindowPane.DRIVER, 30))
    }

    @Test fun `the travel cap grows with the distance`() {
        assertEquals(1_400L, WindowStepper.travelCapMs(10))
        assertEquals(4_600L, WindowStepper.travelCapMs(50))
        assertEquals(8_600L, WindowStepper.travelCapMs(100))
    }
}
