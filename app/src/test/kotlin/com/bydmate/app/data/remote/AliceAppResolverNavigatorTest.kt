package com.bydmate.app.data.remote

import android.app.Application
import android.content.ComponentName
import android.content.Intent
import androidx.test.core.app.ApplicationProvider
import com.bydmate.app.data.automation.RouteNavigatorUris
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29])
class AliceAppResolverNavigatorTest {
    private val app: Application = ApplicationProvider.getApplicationContext()

    @Before
    fun resetPrefs() {
        app.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .edit()
            .clear()
            .commit()
    }

    @Test
    fun `generic navigator resolves selected ReVanced Google Maps locally`() {
        installLauncher("app.revanced.android.apps.maps")
        app.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .edit()
            .putString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, RouteNavigatorUris.GOOGLE_MAPS)
            .commit()

        val resolved = AliceAppResolver(app).resolveText("навигатор")

        assertTrue(resolved.isSuccess)
        assertEquals("app.revanced.android.apps.maps", resolved.getOrNull())
    }

    @Test
    fun `explicit Yandex Navigator never falls back to selected Google Maps`() {
        installLauncher("app.revanced.android.apps.maps")
        app.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .edit()
            .putString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, RouteNavigatorUris.GOOGLE_MAPS)
            .commit()

        val resolved = AliceAppResolver(app).resolveText("яндекс навигатор")

        assertTrue(resolved.isFailure)
    }

    private fun installLauncher(packageName: String) {
        val component = ComponentName(packageName, "$packageName.Main")
        val pm = shadowOf(app.packageManager)
        pm.addActivityIfNotPresent(component)
        pm.addIntentFilterForActivity(
            component,
            android.content.IntentFilter(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_LAUNCHER)
            },
        )
    }
}
