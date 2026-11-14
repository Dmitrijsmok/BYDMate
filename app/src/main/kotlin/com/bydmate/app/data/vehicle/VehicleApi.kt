package com.bydmate.app.data.vehicle

import com.bydmate.app.data.autoservice.BatteryReading

/**
 * Single in-process facade for vehicle reads + writes.
 *
 * Reads delegate to AutoserviceClient (Phase 1b stack).
 * Writes (Group C, populated from Phase 2c probe) go through HelperClient
 * via WriteAllowlist.
 *
 * Returns null on any read failure (sentinel, daemon down, parse failure).
 * Returns Result.failure(VehicleWriteError) on any write failure — never throws.
 * The error type carries actionName + details for structured logging.
 */
interface VehicleApi {
    // Liveness / snapshots — passthroughs to AutoserviceClient.
    suspend fun isAvailable(): Boolean
    suspend fun readBatterySnapshot(): BatteryReading?

    // Side window positions and percent writes (0..100): the Alice bridge's aperture control (fork).
    // Defaults for fakes that never touch a window: no reading, every write unsupported.
    suspend fun readWindowDriver(): Int? = null
    suspend fun readWindowPassenger(): Int? = null
    suspend fun readWindowRearLeft(): Int? = null
    suspend fun readWindowRearRight(): Int? = null
    suspend fun writeWindowDriver(percent: Int): Result<Unit> = windowUnsupported()
    suspend fun writeWindowPassenger(percent: Int): Result<Unit> = windowUnsupported()
    suspend fun writeWindowRearLeft(percent: Int): Result<Unit> = windowUnsupported()
    suspend fun writeWindowRearRight(percent: Int): Result<Unit> = windowUnsupported()

    // Write entrypoint, wired to WriteAllowlist + HelperClient (Group C).
    // Failure reason available via Result.exceptionOrNull() as VehicleWriteError.
    suspend fun dispatch(commandString: String): Result<Unit>

    /**
     * Drives a side window to [percent] by the closed loop (CTRL open/close, position polled,
     * CTRL stop at the target; see WindowStepper), whatever the percent family does. Not speed
     * gated: callers gate an opening move first.
     */
    suspend fun driveWindow(pane: WindowPane, percent: Int): Result<Unit> =
        Result.failure(VehicleWriteError.Unsupported("window_step"))

    private fun windowUnsupported(): Result<Unit> = Result.failure(VehicleWriteError.Unsupported("window_percent"))

    /** Rear seats whose heat this car has (#327). */
    suspend fun rearSeatHeatSides(): Set<RearSeat> = emptySet()
}
