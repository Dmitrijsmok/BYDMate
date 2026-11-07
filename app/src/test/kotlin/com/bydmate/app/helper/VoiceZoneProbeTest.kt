package com.bydmate.app.helper

import org.junit.Assert.assertEquals
import org.junit.Test

class VoiceZoneProbeTest {
    @Test fun `only voice-looking keys survive, tagged with their table`() {
        val output = """
            ## system
            screen_brightness=120
            vr_wakeup_zone=1
            ## global
            server_url=https://example
            voice_driver_only=1
            ## secure
            android_id=abc
            voice_interaction_service=com.byd.vrassistant/.Svc
            ## props
            [ro.build.id]: [QKQ1]
            [persist.vendor.audio.aec.enable]: [true]
            ## vrassistant
              versionName=3.1.0
              User 0: ceDataInode=1 installed=true hidden=false suspended=false stopped=false notLaunched=false enabled=3
                disabledComponents:
                  com.byd.vrassistant.WakeupService
              mPermissions: foo
        """.trimIndent()
        assertEquals(
            listOf(
                "system: vr_wakeup_zone=1",
                "global: voice_driver_only=1",
                "secure: voice_interaction_service=com.byd.vrassistant/.Svc",
                "props: [persist.vendor.audio.aec.enable]: [true]",
                "vrassistant: versionName=3.1.0",
                "vrassistant: User 0: ceDataInode=1 installed=true hidden=false suspended=false stopped=false notLaunched=false enabled=3",
                "vrassistant: disabledComponents:",
                "vrassistant: com.byd.vrassistant.WakeupService",
            ),
            VoiceZoneProbe.filter(output),
        )
    }
}
