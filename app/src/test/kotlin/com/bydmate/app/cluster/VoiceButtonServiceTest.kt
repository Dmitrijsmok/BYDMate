package com.bydmate.app.cluster

import android.content.Context
import android.view.KeyEvent
import androidx.test.core.app.ApplicationProvider
import com.bydmate.app.voice.VoiceController
import io.mockk.mockk
import io.mockk.every
import io.mockk.verify
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertFalse
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import android.os.Looper
import java.time.Duration

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29, 30])
class VoiceButtonServiceTest {
    private lateinit var service: SteeringWheelKeyService
    private val voice = mockk<VoiceController>(relaxed = true)
    private val alice = mockk<YandexAliceLauncher>(relaxed = true)
    private val context: Context get() = ApplicationProvider.getApplicationContext()

    @Before fun setUp() {
        service = Robolectric.buildService(SteeringWheelKeyService::class.java).create().get()
        val ep = mockk<ClusterEntryPoint>()
        every { ep.voiceController() } returns voice
        every { alice.ownsMicButton() } returns false
        every { alice.localHandoff.requestLocal(any()) } answers { firstArg<() -> Unit>().invoke() }
        SteeringWheelKeyService::class.java.getDeclaredField("cachedEntryPoint").apply {
            isAccessible = true; set(service, ep)
        }
        SteeringWheelKeyService::class.java.getDeclaredField("aliceLauncher\$delegate").apply {
            isAccessible = true; set(service, lazyOf(alice))
        }
        context.getSharedPreferences("voice", Context.MODE_PRIVATE).edit().clear()
            .putBoolean("voice_enabled", true).putInt("voice_keycode", 304)
            .putString("voice_companions", "327").putInt("alice_keycode", 383).apply()
        context.getSharedPreferences(ClusterProjectionManager.PREFS_NAME, Context.MODE_PRIVATE).edit().clear().apply()
        resetLearning()
    }

    @After fun tearDown() { resetLearning(); service.onDestroy() }

    private fun resetLearning() {
        SteeringWheelKeyService.learnMode = false
        SteeringWheelKeyService.learnVoiceCompanions = false
        SteeringWheelKeyService.capturedKey.value = null
    }

    private fun dispatch(event: KeyEvent): Boolean = SteeringWheelKeyService::class.java
        .getDeclaredMethod("onKeyEvent", KeyEvent::class.java).apply { isAccessible = true }
        .invoke(service, event) as Boolean

    private fun event(code: Int, down: Boolean = true, time: Long = 1_000, repeat: Int = 0, device: Int = 1) =
        KeyEvent(time, time, if (down) KeyEvent.ACTION_DOWN else KeyEvent.ACTION_UP, code, repeat, 0, device, 0)

    @Test fun `dedicated local is immediate even in Navigator and companions never activate`() {
        every { alice.ownsMicButton() } returns true
        assertTrue(dispatch(event(304)))
        assertTrue(dispatch(event(304, repeat = 1)))
        assertTrue(dispatch(event(304)))
        assertTrue(dispatch(event(304, false)))
        assertTrue(dispatch(event(327)))
        assertTrue(dispatch(event(327, false)))
        verify(exactly = 1) { voice.onPttPressed() }
        verify(exactly = 0) { alice.trigger() }
    }

    @Test fun `dedicated Alice never invokes local and unassigned keys pass through`() {
        assertTrue(dispatch(event(383)))
        assertTrue(dispatch(event(383, false)))
        assertFalse(dispatch(event(384)))
        assertFalse(dispatch(event(384, false)))
        verify(exactly = 1) { alice.trigger() }
        verify(exactly = 0) { voice.onPttPressed() }
    }

    @Test fun `clearing Alice restores the delayed single and double press route`() {
        context.getSharedPreferences("voice", Context.MODE_PRIVATE).edit().putInt("alice_keycode", 0).apply()
        dispatch(event(304))
        verify(exactly = 0) { voice.onPttPressed() }
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(250))
        verify(exactly = 1) { voice.onPttPressed() }
        dispatch(event(304, false))
        dispatch(event(304, time = 2_000))
        dispatch(event(304, false, time = 2_001))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100))
        dispatch(event(304, time = 2_100))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(300))
        verify(exactly = 1) { alice.trigger() }
        verify(exactly = 1) { voice.onPttPressed() }
    }

    @Test fun `learning includes companion after primary release but not another device`() {
        SteeringWheelKeyService.learnVoiceCompanions = true
        SteeringWheelKeyService.learnMode = true
        dispatch(event(304))
        dispatch(event(304, false, 5_000))
        dispatch(event(327, time = 5_030, device = 2))
        assertEquals(emptySet<Int>(), SteeringWheelKeyService.capturedKey.value!!.companions)
        dispatch(event(327, time = 5_059))
        val capture = SteeringWheelKeyService.capturedKey.value!!
        assertEquals(setOf(327), capture.companions)
        assertTrue(capture.primaryReleased)
        verify(exactly = 0) { voice.onPttPressed() }
        verify(exactly = 0) { alice.trigger() }
    }

    @Test fun `cancelling learning consumes the already captured key up without saving`() {
        SteeringWheelKeyService.learnVoiceCompanions = true
        SteeringWheelKeyService.learnMode = true
        dispatch(event(384))
        resetLearning()
        assertTrue(dispatch(event(384, false)))
        assertFalse(dispatch(event(384, time = 2_000)))
        assertEquals(383, context.getSharedPreferences("voice", Context.MODE_PRIVATE).getInt("alice_keycode", 0))
    }

    @Test fun `pressing the learned primary again waits for its new release before saving`() {
        SteeringWheelKeyService.learnVoiceCompanions = true
        SteeringWheelKeyService.learnMode = true
        dispatch(event(304))
        dispatch(event(304, false, time = 1_010))
        assertTrue(SteeringWheelKeyService.capturedKey.value!!.primaryReleased)

        dispatch(event(304, time = 2_000))
        assertFalse(SteeringWheelKeyService.capturedKey.value!!.primaryReleased)
        dispatch(event(304, false, time = 5_000))
        assertTrue(SteeringWheelKeyService.capturedKey.value!!.primaryReleased)
        assertEquals(5_000L, SteeringWheelKeyService.capturedKey.value!!.atMs)
    }

    @Test fun `another primary press reanchors companion learning without activating assistants`() {
        SteeringWheelKeyService.learnVoiceCompanions = true
        SteeringWheelKeyService.learnMode = true
        dispatch(event(304))
        dispatch(event(304, false, time = 1_010))

        dispatch(event(304, time = 2_000))
        dispatch(event(327, time = 2_059))
        assertEquals(setOf(327), SteeringWheelKeyService.capturedKey.value!!.companions)
        verify(exactly = 0) { voice.onPttPressed() }
        verify(exactly = 0) { alice.trigger() }
    }

    @Test fun `legacy 304 fallback is confined to Android 10 with takeover enabled`() {
        val prefs = context.getSharedPreferences("voice", Context.MODE_PRIVATE)
        prefs.edit().clear().putBoolean("voice_enabled", true).putBoolean("alice_native_takeover", true).apply()
        assertEquals(android.os.Build.VERSION.SDK_INT == 29, dispatch(event(304)))
        prefs.edit().putBoolean("alice_native_takeover", false).apply()
        assertFalse(dispatch(event(327)))
    }
    @Test fun `learning Alice as 327 cannot also launch Local through the legacy 304 fallback`() {
        context.getSharedPreferences("voice", Context.MODE_PRIVATE).edit().clear()
            .putBoolean("voice_enabled", true).putBoolean("alice_native_takeover", true)
            .putInt("alice_keycode", 327).apply()
        assertEquals(android.os.Build.VERSION.SDK_INT == 29, dispatch(event(304)))
        dispatch(event(327))
        verify(exactly = 1) { alice.trigger() }
        verify(exactly = 0) { voice.onPttPressed() }
    }

    @Test fun `legacy 327 preference remains companion only on Android 10`() {
        context.getSharedPreferences("voice", Context.MODE_PRIVATE).edit().clear()
            .putBoolean("voice_enabled", true).putBoolean("alice_native_takeover", true)
            .putInt("voice_keycode", 327).apply()
        dispatch(event(327))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(300))
        verify(exactly = if (android.os.Build.VERSION.SDK_INT == 29) 0 else 1) { voice.onPttPressed() }
        verify(exactly = 0) { alice.trigger() }
    }

}
