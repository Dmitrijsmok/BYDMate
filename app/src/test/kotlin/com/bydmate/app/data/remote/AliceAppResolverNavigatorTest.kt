package com.bydmate.app.data.remote

import android.app.Application
import android.content.ComponentName
import android.content.Context
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

/** What the Alice app actions open on a head unit, resolved like ActionDispatcher.openNavigatorApp. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29])
class AliceAppResolverNavigatorTest {
    private val app: Application = ApplicationProvider.getApplicationContext()
    private val prefs get() = app.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, Context.MODE_PRIVATE)

    @Before
    fun resetPrefs() {
        prefs.edit().clear().commit()
    }

    private fun navigatorFor(name: String): String? =
        AliceAppResolver(app).navigatorPackage((AliceAppCatalog.forName(name) as AliceAppTarget.Navigator).navigator)

    @Test
    fun generic_navigator_resolves_selected_google_maps_not_yandex() {
        installLauncher("ru.yandex.yandexnavi")
        installLauncher("app.revanced.android.apps.maps")
        prefs.edit().putString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, RouteNavigatorUris.GOOGLE_MAPS).commit()

        assertEquals("app.revanced.android.apps.maps", navigatorFor("навигатор"))
    }

    @Test
    fun explicit_yandex_navigator_stays_explicit() {
        installLauncher("ru.yandex.yandexnavi")
        installLauncher("app.revanced.android.apps.maps")
        prefs.edit().putString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, RouteNavigatorUris.GOOGLE_MAPS).commit()

        assertEquals("ru.yandex.yandexnavi", navigatorFor("яндекс навигатор"))
    }

    @Test
    fun manual_navigator_package_wins_for_the_chosen_app() {
        installLauncher("com.waze")
        installLauncher("org.example.waze.patched")
        prefs.edit()
            .putString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, RouteNavigatorUris.WAZE)
            .putString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR_PACKAGE, "org.example.waze.patched")
            .commit()

        assertEquals("org.example.waze.patched", navigatorFor("навигатор"))
        assertEquals(
            "org.example.waze.patched",
            AliceAppResolver(app).navigatorPackage(RouteNavigatorUris.WAZE),
        )
    }

    @Test
    fun revanced_youtube_is_launched_when_the_stock_one_is_missing() {
        installLauncher("app.revanced.android.youtube")
        val target = AliceAppCatalog.forAction("app.youtube.open") as AliceAppTarget.App

        assertEquals("app.revanced.android.youtube", AliceAppResolver(app).resolve(target).getOrThrow())
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
