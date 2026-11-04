package com.bydmate.app.data.vehicle

import com.bydmate.app.data.autoservice.AutoserviceClient
import com.bydmate.app.data.local.dao.VehicleWriteLogDao
import com.bydmate.app.data.nativestack.ParsReader
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * ATTO 3 / Yuan Plus on DiLink 3.0 (field log 1.1.1): every percent write to 1276219408 is
 * accepted, nudged and anchored, and the glass never moves; BODYWORK_WINDOW_PERCENTAGE_CONTROL_
 * CONFIG reads -10011. On such a legacy unit a percentage is driven by the closed loop (CTRL
 * open/close, position polled, CTRL stop). Every other car keeps the upstream percent path.
 */
class VehicleApiWindowStepTest {

    private companion object {
        const val DEV = 1001
        const val CONFIG_FID = 1222639652
        const val NO_DATA = -10011L
        val POS_FIDS = mapOf(1276219408 to 947912728, 1276219424 to 1267728400, 1276219416 to 947912736, 1276219432 to 947912752)
        val CTRL_FIDS = mapOf(1125122104 to 947912728, 1125122107 to 1267728400, 1125122112 to 947912736, 1125122115 to 947912752)
        const val DRIVER_POS = 1276219408
        const val DRIVER_CTRL = 1125122104
        const val DRIVER_READ = 947912728
        const val STEP_PER_READ = 2
    }

    /** What the unit does with each family; positions per read fid. */
    private var percentMoves = false
    private var ctrlMoves = true
    private val positions = mutableMapOf<Int, Int>()
    private val direction = mutableMapOf<Int, Int>()
    private val writes = mutableListOf<Pair<Int, Int>>()

    private fun writesTo(fid: Int) = writes.filter { it.first == fid }.map { it.second }

    private fun write(fid: Int, value: Int): Int {
        writes += fid to value
        POS_FIDS[fid]?.let { read -> if (percentMoves && value in 0..100) positions[read] = value }
        CTRL_FIDS[fid]?.let { read ->
            direction[read] = when (value) {
                1 -> if (ctrlMoves) 1 else 0
                2 -> if (ctrlMoves) -1 else 0
                else -> 0
            }
        }
        return 1
    }

    /** Each read of a commanded pane finds it [STEP_PER_READ] percent further. */
    private fun read(fid: Int): Int {
        val now = ((positions[fid] ?: 0) + (direction[fid] ?: 0) * STEP_PER_READ).coerceIn(0, 100)
        positions[fid] = now
        return now
    }

    private fun api(legacy: Boolean = true, config: Long? = NO_DATA): VehicleApiImpl {
        val helper = mockk<HelperClient>()
        coEvery { helper.write(any(), any(), any()) } coAnswers { write(secondArg(), thirdArg()) >= 0 }
        coEvery { helper.writeStatus(any(), any(), any(), any()) } coAnswers { write(secondArg(), thirdArg()) }
        coEvery { helper.read(any(), any(), any()) } returns null
        coEvery { helper.read(DEV, CONFIG_FID, any()) } returns config
        val autoservice = mockk<AutoserviceClient>(relaxed = true)
        coEvery { autoservice.getIntRaw(any(), any()) } coAnswers { read(secondArg()) }
        val store = object : WindowChannelStore {
            override fun winner() = WindowChannel.PERCENT
            override fun setWinner(channel: WindowChannel) = Unit
            override fun ctrlCandidateAtMs() = 0L
            override fun setCtrlCandidateAtMs(ts: Long) = Unit
        }
        val seatStore = object : SeatChannelStore {
            override fun winner() = SeatChannel.UNKNOWN
            override fun setWinner(channel: SeatChannel) = Unit
            override fun reprobeExhausted() = false
            override fun claimReprobe() = true
        }
        val allowlist = WriteAllowlist(
            (WriteAllowlist.LIVE_VALIDATED + WriteAllowlist.CANDIDATE_UNVALIDATED).associateBy { it.actionName.lowercase() },
        )
        return VehicleApiImpl(
            mockk<ParsReader>(relaxed = true), autoservice, helper, allowlist, mockk<VehicleWriteLogDao>(relaxed = true),
            seatStore, store, legacyHeadUnit = legacy,
        ).also { it.readbackScope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined) }
    }

    @Test fun `a legacy unit without the percent family drives the vent by the closed loop`() = runTest {
        val result = api().dispatch("主驾通风")

        assertTrue(result.exceptionOrNull()?.message, result.isSuccess)
        assertEquals(emptyList<Int>(), writesTo(DRIVER_POS))
        assertEquals(listOf(1, 3), writesTo(DRIVER_CTRL))
        assertTrue("stopped at ${positions[DRIVER_READ]}", positions[DRIVER_READ]!! in 10..14)
    }

    @Test fun `the half detent and an explicit percentage take the same loop`() = runTest {
        val api = api()
        assertTrue(api.dispatch("主驾半开").isSuccess)
        assertTrue("stopped at ${positions[DRIVER_READ]}", positions[DRIVER_READ]!! in 50..54)
        assertTrue(api.dispatch("主驾打开30").isSuccess)
        assertTrue("stopped at ${positions[DRIVER_READ]}", positions[DRIVER_READ]!! in 26..30)
        assertEquals(listOf(1, 3, 2, 3), writesTo(DRIVER_CTRL))
        assertEquals(emptyList<Int>(), writesTo(DRIVER_POS))
    }

    /** Alice's percent write ends in the same place. */
    @Test fun `the structured percent write of Alice takes the loop too`() = runTest {
        assertTrue(api().writeWindowDriver(40).isSuccess)
        assertTrue("stopped at ${positions[DRIVER_READ]}", positions[DRIVER_READ]!! in 40..44)
        assertEquals(emptyList<Int>(), writesTo(DRIVER_POS))
    }

    @Test fun `a percent write that does not move falls back to the loop on a legacy unit`() = runTest {
        val result = api(config = 1L).dispatch("主驾半开")

        assertTrue(result.exceptionOrNull()?.message, result.isSuccess)
        // The upstream sequence first: the write, its nudge, the anchor and the target again.
        assertEquals(listOf(50, 51, 0, 50), writesTo(DRIVER_POS).filter { it != 255 })
        assertEquals(listOf(1, 3), writesTo(DRIVER_CTRL))
        assertTrue("stopped at ${positions[DRIVER_READ]}", positions[DRIVER_READ]!! in 50..54)
    }

    @Test fun `a legacy unit whose percent write works never touches CTRL`() = runTest {
        percentMoves = true
        assertTrue(api(config = 1L).dispatch("主驾半开").isSuccess)
        assertEquals(listOf(50), writesTo(DRIVER_POS).filter { it != 255 })
        assertEquals(emptyList<Int>(), writesTo(DRIVER_CTRL))
    }

    /** Upstream behaviour on every other car: the percent path and its failure, no CTRL write. */
    @Test fun `a unit that is not legacy keeps the upstream percent path`() = runTest {
        val result = api(legacy = false).dispatch("主驾半开")

        val err = result.exceptionOrNull() as VehicleWriteError.ReadbackMismatch
        assertEquals(listOf(WindowPane.DRIVER), err.stuckPanes)
        assertEquals(emptyList<Int>(), writesTo(DRIVER_CTRL))
    }

    @Test fun `a percent car that is not legacy never touches CTRL`() = runTest {
        percentMoves = true
        assertTrue(api(legacy = false).dispatch("主驾打开30").isSuccess)
        assertEquals(listOf(30), writesTo(DRIVER_POS).filter { it != 255 })
        assertEquals(emptyList<Int>(), writesTo(DRIVER_CTRL))
    }

    /** A unit whose CTRL family is the dead one (#197): the percent write is the second chance. */
    @Test fun `a pane the loop cannot move gets the percent write`() = runTest {
        ctrlMoves = false
        percentMoves = true
        assertTrue(api().dispatch("主驾通风").isSuccess)
        assertEquals(listOf(1, 3), writesTo(DRIVER_CTRL))
        assertEquals(listOf(10), writesTo(DRIVER_POS).filter { it != 255 })
    }

    @Test fun `nothing moving anywhere is the stuck window error`() = runTest {
        ctrlMoves = false
        val err = api().dispatch("主驾通风").exceptionOrNull() as VehicleWriteError.ReadbackMismatch
        assertEquals(listOf(WindowPane.DRIVER), err.stuckPanes)
    }

    @Test fun `the full open and close keep their own commands`() = runTest {
        api().dispatch("主驾打开100")
        assertEquals(listOf(1), writesTo(DRIVER_CTRL))
        assertEquals(emptyList<Int>(), writesTo(DRIVER_POS))
    }

    @Test fun `the all-window vent drives every pane by the loop`() = runTest {
        val result = api().dispatch("车窗通风")

        assertTrue(result.exceptionOrNull()?.message, result.isSuccess)
        for ((ctrl, read) in CTRL_FIDS) {
            assertEquals("ctrl $ctrl", listOf(1, 3), writesTo(ctrl))
            assertTrue("pane $read at ${positions[read]}", positions[read]!! in 10..14)
        }
        assertTrue(writes.none { it.first in POS_FIDS.keys })
    }
}
