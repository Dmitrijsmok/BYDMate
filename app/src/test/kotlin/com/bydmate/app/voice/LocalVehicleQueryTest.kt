package com.bydmate.app.voice

import com.bydmate.app.data.remote.diParsData
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class LocalVehicleQueryTest {

    @Test fun battery_charge_is_answered_from_snapshot() {
        assertEquals(
            LocalVehicleQuery.Reply("soc", "Заряд 64%."),
            LocalVehicleQuery.answer("какой заряд батареи", VoiceLang.RU, diParsData(soc = 64)),
        )
    }

    @Test fun outside_temperature_is_answered_from_snapshot() {
        assertEquals(
            LocalVehicleQuery.Reply("outside_temp", "Снаружи 11 градусов."),
            LocalVehicleQuery.answer("температура на улице", VoiceLang.RU, diParsData(exteriorTemp = 11)),
        )
    }

    @Test fun outside_temperature_asr_truncation_stays_local() {
        assertEquals(
            LocalVehicleQuery.Reply("outside_temp", "Снаружи 16 градусов."),
            LocalVehicleQuery.answer("температура на улиц", VoiceLang.RU, diParsData(exteriorTemp = 16)),
        )
    }

    @Test fun temperature_in_car_phrase_is_cabin_query() {
        assertEquals(
            LocalVehicleQuery.Reply("inside_temp", "В салоне 24 градусов."),
            LocalVehicleQuery.answer("температура в машине", VoiceLang.RU, diParsData(insideTemp = 24)),
        )
    }

    @Test fun cabin_temperature_never_falls_back_to_climate_setpoint() {
        val data = diParsData(insideTemp = null, acTemp = 22)
        assertEquals(
            LocalVehicleQuery.Reply("inside_temp", "Температура в салоне недоступна."),
            LocalVehicleQuery.answer("температура в салоне", VoiceLang.RU, data),
        )
    }

    @Test fun cabin_temperature_uses_real_inside_sensor_when_present() {
        assertEquals(
            LocalVehicleQuery.Reply("inside_temp", "В салоне 21 градусов."),
            LocalVehicleQuery.answer("сколько градусов в салоне", VoiceLang.RU, diParsData(insideTemp = 21)),
        )
    }

    @Test fun explicit_climate_setpoint_query_is_local() {
        assertEquals(
            LocalVehicleQuery.Reply("climate_setpoint", "Климат установлен на 22 градусов."),
            LocalVehicleQuery.answer("какая температура климата", VoiceLang.RU, diParsData(acTemp = 22)),
        )
    }

    @Test fun ambiguous_temperature_stays_on_agent_path() {
        assertNull(LocalVehicleQuery.answer("какая температура", VoiceLang.RU, diParsData(exteriorTemp = 11)))
    }

    @Test fun action_phrase_is_not_misread_as_state_query() {
        assertNull(LocalVehicleQuery.answer("заряди батарею", VoiceLang.RU, diParsData(soc = 64)))
        assertNull(LocalVehicleQuery.answer("включи климат", VoiceLang.RU, diParsData(acTemp = 22)))
    }
}
