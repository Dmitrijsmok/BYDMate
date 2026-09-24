package com.bydmate.app.data.remote

import android.app.Application
import android.content.ComponentName
import android.content.Intent
import android.content.IntentFilter
import androidx.test.core.app.ApplicationProvider
import com.bydmate.app.data.automation.RouteNavigatorUris
import org.junit.Assert.assertEquals
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
            .edit().clear().commit()
    }

    @Test
    fun generic_navigator_resolves_selected_google_maps_not_yandex() {
        installLauncher("app.revanced.android.apps.maps")
        app.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .edit()
            .putString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, RouteNavigatorUris.GOOGLE_MAPS)
            .commit()

        assertEquals(
            "app.revanced.android.apps.maps",
            AliceAppResolver(app).resolveText("навигатор").getOrThrow(),
        )
    }

    @Test
    fun explicit_yandex_navigator_stays_explicit() {
        installLauncher("ru.yandex.yandexnavi")
        installLauncher("app.revanced.android.apps.maps")
        app.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .edit()
            .putString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, RouteNavigatorUris.GOOGLE_MAPS)
            .commit()

        assertEquals(
            "ru.yandex.yandexnavi",
            AliceAppResolver(app).resolveText("яндекс навигатор").getOrThrow(),
        )
    }

    private fun installLauncher(packageName: String) {
        val component = ComponentName(packageName, "$packageName.Main")
        val pm = shadowOf(app.packageManager)
        pm.addActivityIfNotPresent(component)
        pm.addIntentFilterForActivity(
            component,
            IntentFilter(Intent.ACTION_MAIN).apply { addCategory(Intent.CATEGORY_LAUNCHER) },
        )
    }
}
