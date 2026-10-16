package com.bydmate.app.cluster

import android.content.Context
import android.media.AudioManager
import android.os.Looper
import android.view.accessibility.AccessibilityNodeInfo
import io.mockk.every
import io.mockk.mockk
import io.mockk.spyk
import io.mockk.verify
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import java.time.Duration

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29])
class AliceLocalHandoffRunnerTest {
    private val service = spyk(Robolectric.buildService(SteeringWheelKeyService::class.java).create().get())
    private val audio = mockk<AudioManager>()
    private val root = mockk<AccessibilityNodeInfo>()
    private var localStarts = 0
    private var aliceCancels = 0
    private var aliceReleases = 0

    private fun runner(owned: Boolean): AliceLocalHandoffRunner {
        every { service.getSystemService(Context.AUDIO_SERVICE) } returns audio
        every { audio.activeRecordingConfigurations } returns emptyList()
        every { service.rootInActiveWindow } returns root
        every { root.packageName } returns "com.bydmate.dilink3.app"
        return AliceLocalHandoffRunner(service, { owned }, { false }, { aliceCancels++ }, { aliceReleases++ })
    }

    @Test fun `idle dedicated Local starts synchronously without launching Alice`() {
        val guard = runner(false)
        guard.requestLocal { localStarts++ }
        assertEquals(1, localStarts)
        assertEquals(0, aliceCancels)
    }

    @Test fun `owned Alice must exit and release recorder before Local starts once`() {
        val guard = runner(true)
        guard.requestLocal { localStarts++ }
        guard.requestLocal { localStarts++ }
        assertEquals(0, localStarts)
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(1_300))
        assertEquals(1, localStarts)
        assertEquals(1, aliceCancels)
        assertEquals(1, aliceReleases)
        assertFalse(guard.active)
    }

    @Test fun `active recorder prevents starting Local even after the window exits`() {
        val guard = runner(true)
        every { audio.activeRecordingConfigurations } returns listOf(mockk())
        guard.requestLocal { localStarts++ }
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(5))
        assertEquals(0, localStarts)
        assertEquals(0, aliceReleases)
        assertFalse(guard.active)
    }

    @Test fun `cancellation prevents stale Local start`() {
        val guard = runner(true)
        guard.requestLocal { localStarts++ }
        guard.cancel()
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(5))
        assertEquals(0, localStarts)
        assertEquals(0, aliceReleases)
    }
    @Test fun `cancelling Alice before UI launch does not navigate back out of Navigator`() {
        runner(false) // Set up the service observations.
        every { root.packageName } returns "ru.yandex.yandexnavi"
        val guard = AliceLocalHandoffRunner(service, { true }, { false }, {}, {}, { false })
        guard.requestLocal { localStarts++ }
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(1_300))
        assertEquals(1, localStarts)
        verify(exactly = 0) { service.performGlobalAction(any()) }
    }

}
