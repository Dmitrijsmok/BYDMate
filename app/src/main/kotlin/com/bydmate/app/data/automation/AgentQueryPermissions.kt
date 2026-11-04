package com.bydmate.app.data.automation

import org.json.JSONObject

/**
 * What a restricted caller allows the agent turn of an "agent_query" action to do. The Alice
 * bridge forwards its two permissions («Алиса может управлять машиной» / «… навигацией») in the
 * payload, so a question asked through it cannot reach a tool the bridge itself would refuse; an
 * automation's payload has no such key and keeps the full detached tool set. Pure.
 *
 * Payload shape: `{"prompt": "…", "permissions": {"vehicle_control": false, "navigation": false}}`.
 */
internal data class AgentQueryPermissions(val vehicleControl: Boolean, val navigation: Boolean) {

    /** [payload] with these permissions added. */
    fun writeTo(payload: JSONObject): JSONObject =
        payload.put(KEY, JSONObject().put(VEHICLE_CONTROL, vehicleControl).put(NAVIGATION, navigation))

    companion object {
        const val KEY = "permissions"
        private const val VEHICLE_CONTROL = "vehicle_control"
        private const val NAVIGATION = "navigation"

        /** Null when [payload] carries no permissions (unrestricted). Once the key is there, a value
         *  that is not an object or a flag that is missing reads as "not allowed": fail closed. */
        fun from(payload: JSONObject?): AgentQueryPermissions? {
            if (payload == null || !payload.has(KEY)) return null
            val flags = payload.optJSONObject(KEY) ?: return AgentQueryPermissions(vehicleControl = false, navigation = false)
            return AgentQueryPermissions(
                vehicleControl = flags.optBoolean(VEHICLE_CONTROL, false),
                navigation = flags.optBoolean(NAVIGATION, false),
            )
        }
    }
}
