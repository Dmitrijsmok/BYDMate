package com.bydmate.app.data.remote

/** What an Alice bridge command does, which decides the permission it needs. */
internal enum class AliceCommandKind {
    /** Climate, seats, lights, windows, sunroof, sunshade, trunk, free-text vehicle commands and
     *  upstream's raw vehicle command strings: needs [AliceBridgePermissions.vehicleControl]. */
    VEHICLE,

    /** Route, map search, point on the map: needs [AliceBridgePermissions.navigation]. */
    NAVIGATION,

    /** Launching an app (navigator apps included, without a route) and the cluster projection. */
    APP,
    MEDIA,

    /** A question about the car for the BYDMate agent; its agent turn is held to the permissions. */
    QUERY,
    UNSUPPORTED,
}

/** The two «Алиса может …» switches of the Smart Home settings; both off unless the owner turns them on. */
data class AliceBridgePermissions(val vehicleControl: Boolean = false, val navigation: Boolean = false)

/** The executing side of [AliceBridgeRouter], one entry per [AliceCommandKind]. */
interface AliceBridgeActions {
    suspend fun vehicle(command: AliceBridgeCommand): Result<Unit>
    suspend fun navigation(command: AliceBridgeCommand): Result<Unit>
    suspend fun app(command: AliceBridgeCommand): Result<Unit>
    suspend fun media(command: AliceBridgeCommand): Result<Unit>
    /** [permissions] limit the tools of the agent turn the question starts. */
    suspend fun query(command: AliceBridgeCommand, permissions: AliceBridgePermissions): Result<Unit>
}

/**
 * The single dispatch point of the Alice bridge: every command is classified here and a vehicle
 * or navigation command whose permission is off is answered [VEHICLE_CONTROL_DISABLED] /
 * [NAVIGATION_DISABLED] without reaching [AliceBridgeActions] at all. A question reaches the agent
 * with the permissions, so its tools cannot do what this router refuses. Pure.
 */
internal object AliceBridgeRouter {
    const val VEHICLE_CONTROL_DISABLED = "vehicle_control_disabled"
    const val NAVIGATION_DISABLED = "navigation_disabled"
    const val UNSUPPORTED_ACTION = "unsupported_action"

    private val vehiclePrefixes = listOf(
        "climate.", "seat.", "light.", "window.", "sunroof.", "sunshade.", "trunk.", "doors.", "fridge.",
    )

    fun kindOf(command: AliceBridgeCommand): AliceCommandKind {
        val action = command.action
        return when {
            action.isEmpty() ->
                if (command.rawCommand.isNotEmpty()) AliceCommandKind.VEHICLE else AliceCommandKind.UNSUPPORTED
            action == "vehicle.command" -> AliceCommandKind.VEHICLE
            AliceLocalCommandRouter.isNavigationAction(action) -> AliceCommandKind.NAVIGATION
            action.startsWith("app.") || action.startsWith("navigation.cluster_") -> AliceCommandKind.APP
            action.startsWith("media.") -> AliceCommandKind.MEDIA
            action == "agent.query" -> AliceCommandKind.QUERY
            vehiclePrefixes.any(action::startsWith) -> AliceCommandKind.VEHICLE
            else -> AliceCommandKind.UNSUPPORTED
        }
    }

    suspend fun execute(
        command: AliceBridgeCommand,
        permissions: AliceBridgePermissions,
        actions: AliceBridgeActions,
    ): Result<Unit> = when (kindOf(command)) {
        AliceCommandKind.VEHICLE ->
            if (permissions.vehicleControl) actions.vehicle(command) else failure(VEHICLE_CONTROL_DISABLED)
        AliceCommandKind.NAVIGATION ->
            if (permissions.navigation) actions.navigation(command) else failure(NAVIGATION_DISABLED)
        AliceCommandKind.APP -> actions.app(command)
        AliceCommandKind.MEDIA -> actions.media(command)
        AliceCommandKind.QUERY -> actions.query(command, permissions)
        AliceCommandKind.UNSUPPORTED -> failure(UNSUPPORTED_ACTION)
    }

    fun failure(reason: String): Result<Unit> = Result.failure(IllegalStateException(reason))
}
