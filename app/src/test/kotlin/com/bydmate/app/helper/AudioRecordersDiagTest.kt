package com.bydmate.app.helper

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioRecordersDiagTest {
    @Test fun `the record activity section lists each recording client`() {
        val dump = """
            Audio routes:
              mMainType=0x0
            RecordActivityMonitor dump time: 09:37:01
              session:121 -- source client=VOICE_RECOGNITION -- uid:10125 pack:com.bydmate.dilink3.app -- silenced:true
              session:97 -- source client=MIC -- uid:10210 pack:com.overdrive.app -- silenced:false

            AudioDeviceBroker:
              foo
        """.trimIndent()
        val out = AudioRecordersDiag.parse(dump)
        assertEquals(2, out.size)
        assertTrue(out[1].contains("com.overdrive.app"))
    }

    @Test fun `without the section only silenced lines are kept and nothing else leaks`() {
        val out = AudioRecordersDiag.parse("x\n  client uid=1 silenced=false\nother")
        assertEquals(listOf("client uid=1 silenced=false"), out)
        assertTrue(AudioRecordersDiag.parse("nothing here").isEmpty())
    }

    @Test fun `the holder is the other app that is not silenced`() {
        val lines = listOf(
            "session:121 -- source client=VOICE_RECOGNITION -- uid:10125 pack:com.bydmate.dilink3.app -- silenced:true",
            "session:90 -- source client=MIC -- uid:10300 pack:com.idle.app -- silenced:true",
            "session:97 -- source client=MIC -- uid:10210 pack:com.overdrive.app -- silenced:false",
        )
        assertEquals(listOf("com.overdrive.app", "com.idle.app"),
            AudioRecordersDiag.holderPackages(lines, "com.bydmate.dilink3.app"))
        assertTrue(AudioRecordersDiag.holderPackages(lines.take(1), "com.bydmate.dilink3.app").isEmpty())
    }
}
