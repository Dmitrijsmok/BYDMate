package com.bydmate.app.data.automation

import android.app.Application
import android.content.Intent
import android.net.Uri
import androidx.test.core.app.ApplicationProvider
import com.bydmate.app.cluster.ClusterVoiceControl
import com.bydmate.app.data.local.LocalePreferences
import com.bydmate.app.data.local.entity.ActionDef
import com.bydmate.app.data.vehicle.HelperClient
import com.bydmate.app.data.vehicle.VehicleApi
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29])
class ActionDispatcherNavigateTest {
    private val vehicleApi = mockk<VehicleApi>(relaxed = true)
    private val helper = mockk<HelperClient>(relaxed = true)
    private val app: Application = ApplicationProvider.getApplicationContext()
    private val dispatcher = testDispatcher(vehicleApi, helper, app, appStrings = com.bydmate.app.util.AppStrings(app))

    init {
        // The fallback reasons below are asserted in Russian; another test may leave its language set.
        LocalePreferences(app).setLanguage("ru")
    }

    private fun actionDef(payload: String) =
        ActionDef(command = "", displayName = "navi", kind = "navigate", payload = payload)

    /** Dispatches [payload] and returns the result with the activity it started, if any. */
    private suspend fun open(payload: String): Pair<DispatchResult, Intent?> =
        dispatcher.dispatch(actionDef(payload), null) to shadowOf(app).nextStartedActivity

    @Test fun `with no navigator chosen the Yandex Navigator gets shortcuts, points, routes and searches`() = runTest {
        open("""{"shortcut":"home"}""").let { (res, intent) ->
            assertTrue("home: success", res.success)
            assertEquals("home: action", "ru.yandex.yandexmaps.action.ROUTE_TO_HOME_SHORTCUT", intent!!.action)
            assertEquals("home: package", "ru.yandex.yandexnavi", intent.`package`)
            assertTrue("home: new task", intent.flags and Intent.FLAG_ACTIVITY_NEW_TASK != 0)
        }
        open("""{"shortcut":"work"}""").let { (res, intent) ->
            assertTrue("work: success", res.success)
            assertEquals("work: action", "ru.yandex.yandexmaps.action.ROUTE_TO_WORK_SHORTCUT", intent!!.action)
        }
        open("""{"shortcut":"dacha"}""").let { (res, intent) ->
            assertFalse("unknown shortcut: fails", res.success)
            assertEquals("unknown shortcut: no activity", null, intent)
        }
        open("""{"show":true,"lat":55.75,"lon":37.62,"label":"Кафе"}""").let { (res, intent) ->
            assertTrue("show point: success", res.success)
            assertEquals("show point: action", Intent.ACTION_VIEW, intent!!.action)
            assertTrue("show point: uri", intent.dataString!!.startsWith("yandexnavi://show_point_on_map?lat=55.75&lon=37.62"))
            assertTrue("show point: desc", intent.dataString!!.contains("desc="))
        }
        open("""{"show":true,"lat":55.75,"lon":37.62}""").let { (_, intent) ->
            assertFalse("show point without label: no desc", intent!!.dataString!!.contains("desc="))
        }
        open("""{"lat":57.0,"lon":36.0}""").let { (res, intent) ->
            assertTrue("route: success", res.success)
            assertEquals("route: uri", "yandexnavi://build_route_on_map?lat_to=57.0&lon_to=36.0", intent!!.dataString)
        }
        open("""{"query":"кафе"}""").let { (_, intent) ->
            assertTrue("search: uri", intent!!.dataString!!.startsWith("yandexnavi://map_search?text="))
        }
        val query = "аэропорт Сочи"
        open("""{"query":"$query"}""").let { (res, intent) ->
            assertTrue("search with spaces: success", res.success)
            assertEquals("search with spaces: action", Intent.ACTION_VIEW, intent!!.action)
            assertEquals("search with spaces: uri", "yandexnavi://map_search?text=${Uri.encode(query)}", intent.dataString)
        }
    }

    /** #190: the setting sends the route to 2GIS, package pinned, longitude first. */
    @Test fun `2GIS chosen gets the route, search and point, and falls back to Yandex while missing`() = runTest {
        selectNavigator(RouteNavigatorUris.DGIS)

        // 2GIS chosen but absent: the action still works, through Yandex, and says why.
        open("""{"lat":57.0,"lon":36.0}""").let { (res, intent) ->
            assertTrue("missing: success", res.success)
            assertTrue("missing: the reason must mention the fallback: ${res.reason}", res.reason!!.contains("2ГИС"))
            assertEquals("missing: uri", "yandexnavi://build_route_on_map?lat_to=57.0&lon_to=36.0", intent!!.dataString)
            assertEquals("missing: package", null, intent.`package`)
        }

        installDgis()
        open("""{"lat":57.0,"lon":36.0}""").let { (res, intent) ->
            assertTrue("route: success", res.success)
            assertEquals("route: reason", null, res.reason)
            assertEquals("route: uri", "dgis://2gis.ru/routeSearch/rsType/car/to/36.0,57.0", intent!!.dataString)
            assertEquals("route: package", "ru.dublgis.dgismobile", intent.`package`)
        }
        open("""{"query":"кафе"}""").let { (_, intent) ->
            assertTrue("search: uri", intent!!.dataString!!.startsWith("dgis://2gis.ru/search/"))
        }
        open("""{"show":true,"lat":55.75,"lon":37.62}""").let { (_, intent) ->
            assertEquals("show: uri", "dgis://2gis.ru/geo/37.62,55.75", intent!!.dataString)
        }
    }

    /** #200: the setting sends the route to Yandex Maps' own dialect, no package pin. */
    @Test fun `Yandex Maps chosen gets its own dialect, and falls back to the Navigator while missing`() = runTest {
        selectNavigator(RouteNavigatorUris.MAPS)

        // Maps chosen but absent: the action still works, through Yandex Navigator, and says why.
        open("""{"lat":57.0,"lon":36.0}""").let { (res, intent) ->
            assertTrue("missing: success", res.success)
            assertTrue("missing: the reason must mention the fallback: ${res.reason}", res.reason!!.contains("Яндекс Карты"))
            assertEquals("missing: uri", "yandexnavi://build_route_on_map?lat_to=57.0&lon_to=36.0", intent!!.dataString)
            assertEquals("missing: package", null, intent.`package`)
        }

        installYandexMaps()
        open("""{"lat":57.0,"lon":36.0}""").let { (res, intent) ->
            assertTrue("route: success", res.success)
            assertEquals("route: reason", null, res.reason)
            assertEquals("route: uri", "yandexmaps://maps.yandex.ru/?rtext=~57.0,36.0&rtt=auto", intent!!.dataString)
            assertEquals("route: package", null, intent.`package`)
        }
        open("""{"query":"кафе"}""").let { (_, intent) ->
            assertTrue("search: uri", intent!!.dataString!!.startsWith("yandexmaps://maps.yandex.ru/?text="))
        }
        open("""{"show":true,"lat":55.75,"lon":37.62}""").let { (_, intent) ->
            assertEquals("show: uri", "yandexmaps://maps.yandex.ru/?pt=55.75,37.62&z=14", intent!!.dataString)
        }
        // Maps chosen also covers «поехали домой/на работу» - navigateMaps() has its own
        // ROUTE_TO_HOME/WORK dialect for that.
        open("""{"shortcut":"home"}""").let { (res, intent) ->
            assertTrue("home: success", res.success)
            assertEquals("home: action", "ru.yandex.yandexmaps.action.ROUTE_TO_HOME_SHORTCUT", intent!!.action)
            assertEquals("home: package", "ru.yandex.yandexmaps", intent.`package`)
        }
        // Review P2: with Maps chosen, «поехали домой» (go=true) must not wait for the Navigator's
        // «Поехали» button - that a11y read only ever looks at the Navigator's window. Without the
        // fix autoGoSupported stays true for any shortcut, and the dispatch fails with the
        // "не удалось проверить маршрут" a11y timeout even though Maps opened successfully.
        val go = dispatcher.dispatch(actionDef("""{"shortcut":"home","go":true}"""), null)
        assertTrue("go on a Maps shortcut must not wait for the Navigator's «Поехали»: ${go.reason}", go.success)
    }

    /** #305: the setting sends the route to Waze, package pinned, latitude first. */
    @Test fun `Waze chosen gets routes, searches and favorites, and falls back to Yandex while missing`() = runTest {
        selectNavigator("waze")

        // Waze chosen but absent: the action still works, through Yandex, and says why.
        open("""{"lat":57.0,"lon":36.0}""").let { (res, intent) ->
            assertTrue("missing: success", res.success)
            assertTrue("missing: the reason must mention the fallback: ${res.reason}", res.reason!!.contains("Waze"))
            assertEquals("missing: uri", "yandexnavi://build_route_on_map?lat_to=57.0&lon_to=36.0", intent!!.dataString)
            assertEquals("missing: package", null, intent.`package`)
        }
        // Waze chosen but absent: Home stays on the Navigator's own shortcut, as before.
        open("""{"shortcut":"home"}""").let { (_, intent) ->
            assertEquals("missing, home: action", "ru.yandex.yandexmaps.action.ROUTE_TO_HOME_SHORTCUT", intent!!.action)
        }

        installWaze()
        open("""{"lat":57.0,"lon":36.0}""").let { (res, intent) ->
            assertTrue("route: success", res.success)
            assertEquals("route: reason", null, res.reason)
            assertEquals("route: uri", "waze://?ll=57.0,36.0&navigate=yes", intent!!.dataString)
            assertEquals("route: package", "com.waze", intent.`package`)
        }
        open("""{"query":"кафе"}""").let { (_, intent) ->
            assertTrue("search: uri", intent!!.dataString!!.startsWith("waze://?q="))
        }
        open("""{"show":true,"lat":55.75,"lon":37.62}""").let { (_, intent) ->
            assertEquals("show: uri", "waze://?ll=55.75,37.62", intent!!.dataString)
        }
        // #334: Home/Work with Waze chosen goes to Waze's own saved favorites, not to Yandex.
        open("""{"shortcut":"home"}""").let { (res, intent) ->
            assertTrue("home: success", res.success)
            assertEquals("home: uri", "waze://?favorite=home&navigate=yes", intent!!.dataString)
            assertEquals("home: package", "com.waze", intent.`package`)
        }
        open("""{"shortcut":"work"}""").let { (_, intent) ->
            assertEquals("work: uri", "waze://?favorite=work&navigate=yes", intent!!.dataString)
        }
        // The Waze favorite link starts the route itself, and «Поехали» is pressed through the
        // Yandex Navigator's a11y window that Waze does not have: nothing waits for it.
        assertFalse("home: no auto go", dispatcher.autoGoSupported(org.json.JSONObject("""{"shortcut":"home"}""")))
        assertFalse("route: no auto go", dispatcher.autoGoSupported(org.json.JSONObject("""{"lat":57.0,"lon":36.0}""")))
    }

    /** #305: AgentTools waits for the package the intent was pinned to, so this must agree with
     *  sendNavigateIntent: pinned for an installed 2GIS/Waze, never for Maps. Home/Work with Waze
     *  chosen now opens Waze's own favourite, so it is pinned to Waze too (it was Yandex Navigator's
     *  shortcut before); with 2GIS chosen it still is the Navigator's. */
    @Test fun willOpenPinned_follows_the_routing() {
        selectNavigator("waze")
        assertEquals(null, dispatcher.willOpenPinned(org.json.JSONObject("""{"lat":57.0,"lon":36.0}""")))

        installWaze()
        assertEquals("com.waze", dispatcher.willOpenPinned(org.json.JSONObject("""{"lat":57.0,"lon":36.0}""")))
        assertEquals(null, dispatcher.willOpenPinned(org.json.JSONObject("""{"app":"maps","lat":57.0,"lon":36.0}""")))
        assertEquals("com.waze", dispatcher.willOpenPinned(org.json.JSONObject("""{"shortcut":"home"}""")))

        selectNavigator(RouteNavigatorUris.DGIS)
        installDgis()
        assertEquals(null, dispatcher.willOpenPinned(org.json.JSONObject("""{"shortcut":"home"}""")))
    }

    /** Fork 76aca583: «домой» with Waze chosen opens Waze's saved Home, navigation started. */
    @Test fun waze_home_shortcut_uses_the_favorite_deep_link() = runTest {
        selectNavigator("waze")
        installWaze()

        val res = dispatcher.dispatch(actionDef("""{"shortcut":"home","go":true}"""), null)
        assertTrue(res.reason ?: "", res.success)
        val intent = shadowOf(app).nextStartedActivity
        assertEquals("waze://?favorite=home&navigate=yes", intent.dataString)
        assertEquals("com.waze", intent.`package`)
        assertFalse(dispatcher.autoGoSupported(org.json.JSONObject("""{"shortcut":"home","go":true}""")))

        dispatcher.dispatch(actionDef("""{"shortcut":"work"}"""), null)
        assertEquals("waze://?favorite=work&navigate=yes", shadowOf(app).nextStartedActivity.dataString)
    }

    @Test fun waze_unknown_shortcut_is_refused() = runTest {
        selectNavigator("waze")
        installWaze()

        val res = dispatcher.dispatch(actionDef("""{"shortcut":"dacha"}"""), null)
        assertFalse(res.success)
        assertEquals(null, shadowOf(app).nextStartedActivity)
    }

    // --- one command, one named app (`app`), whatever is chosen in settings ---

    /** Fork e9110fc5/00b5d4a5: an explicit Google Maps is not redirected into the Waze default. */
    @Test fun explicit_google_maps_ignores_default_waze() = runTest {
        selectNavigator("waze")
        installWaze()
        installLauncherApp("com.google.android.apps.maps", "Карты")

        val res = dispatcher.dispatch(actionDef("""{"app":"google_maps","lat":57.0,"lon":36.0}"""), null)
        assertTrue(res.success)
        val intent = shadowOf(app).nextStartedActivity
        assertEquals("com.google.android.apps.maps", intent.`package`)
        assertTrue(intent.dataString!!.startsWith("https://www.google.com/maps/dir/"))
    }

    /** The Waze manual package is the default's: a command naming Google Maps does not take it. */
    @Test fun explicit_google_maps_is_not_sent_to_the_manual_waze_package() = runTest {
        selectNavigator("waze")
        setManualPackage("com.vendor.waze")
        installLauncherApp("app.revanced.android.apps.maps", "Google Maps")

        dispatcher.dispatch(actionDef("""{"app":"google_maps","lat":57.0,"lon":36.0}"""), null)
        assertEquals("app.revanced.android.apps.maps", shadowOf(app).nextStartedActivity.`package`)
    }

    @Test fun explicit_waze_with_yandex_chosen_goes_to_waze() = runTest {
        installWaze()

        dispatcher.dispatch(actionDef("""{"app":"waze","lat":57.0,"lon":36.0}"""), null)
        val intent = shadowOf(app).nextStartedActivity
        assertEquals("waze://?ll=57.0,36.0&navigate=yes", intent.dataString)
        assertEquals("com.waze", intent.`package`)
        assertEquals("com.waze", dispatcher.willOpenPinned(org.json.JSONObject("""{"app":"waze","lat":57.0,"lon":36.0}""")))
    }

    /** A named app that is not installed is not swapped for Yandex Navigator: its own package is
     *  asked, and a missing one fails honestly on the car. */
    @Test fun explicit_missing_app_does_not_fall_back() = runTest {
        val res = dispatcher.dispatch(actionDef("""{"app":"waze","lat":57.0,"lon":36.0}"""), null)
        assertEquals(null, res.reason)
        val intent = shadowOf(app).nextStartedActivity
        assertEquals("com.waze", intent.`package`)
        assertEquals("waze://?ll=57.0,36.0&navigate=yes", intent.dataString)
    }

    @Test fun explicit_yandex_with_waze_chosen_goes_to_the_navigator() = runTest {
        selectNavigator("waze")
        installWaze()

        dispatcher.dispatch(actionDef("""{"app":"yandex","lat":57.0,"lon":36.0}"""), null)
        assertEquals("yandexnavi://build_route_on_map?lat_to=57.0&lon_to=36.0",
            shadowOf(app).nextStartedActivity.dataString)
        assertTrue(dispatcher.autoGoSupported(org.json.JSONObject("""{"app":"yandex","lat":57.0,"lon":36.0}""")))
    }

    /** Home/Work in a named 2GIS is refused with advice, not opened in Yandex Navigator. */
    @Test fun explicit_dgis_home_shortcut_is_refused() = runTest {
        installDgis()

        val res = dispatcher.dispatch(actionDef("""{"app":"dgis","shortcut":"home"}"""), null)
        assertFalse(res.success)
        assertTrue(res.reason!!, res.reason!!.contains("BYDMate"))
        assertEquals(null, shadowOf(app).nextStartedActivity)
    }

    /** Field build 64023: Waze was installed, but the getLaunchIntentForPackage probe said it was
     *  not and the route went to Yandex. A package that exists is installed, launch intent or not. */
    @Test fun waze_installed_without_a_launcher_entry_is_not_reported_missing() = runTest {
        selectNavigator("waze")
        shadowOf(app.packageManager).installPackage(android.content.pm.PackageInfo().apply { packageName = "com.waze" })

        val res = dispatcher.dispatch(actionDef("""{"lat":57.0,"lon":36.0}"""), null)
        assertTrue(res.success)
        assertEquals(null, res.reason)
        val intent = shadowOf(app).nextStartedActivity
        assertEquals("waze://?ll=57.0,36.0&navigate=yes", intent.dataString)
        assertEquals("com.waze", intent.`package`)
    }

    /** A vendor build under its own package is found by its launcher label and the route goes there. */
    @Test fun waze_vendor_build_is_found_by_its_label() = runTest {
        selectNavigator("waze")
        installLauncherApp("com.vendor.navi.w", "Waze")

        val res = dispatcher.dispatch(actionDef("""{"lat":57.0,"lon":36.0}"""), null)
        assertTrue(res.success)
        assertEquals(null, res.reason)
        assertEquals("com.vendor.navi.w", shadowOf(app).nextStartedActivity.`package`)
        assertEquals("com.vendor.navi.w", dispatcher.willOpenPinned(org.json.JSONObject("""{"lat":57.0,"lon":36.0}""")))
    }

    /** The manual package from settings is authoritative: no probe, no false fallback (fork e9110fc5). */
    @Test fun waze_manual_package_is_authoritative_and_does_not_false_fallback() = runTest {
        selectNavigator("waze")
        setManualPackage("com.vendor.waze")

        val res = dispatcher.dispatch(actionDef("""{"lat":57.0,"lon":36.0}"""), null)
        assertTrue(res.success)
        assertEquals(null, res.reason)
        val intent = shadowOf(app).nextStartedActivity
        assertEquals("com.vendor.waze", intent.`package`)
        assertEquals("waze://?ll=57.0,36.0&navigate=yes", intent.dataString)
    }

    /** A manual package belongs to the chosen app: a command naming Maps does not go into it. */
    @Test fun manual_package_does_not_take_an_explicit_maps_command() = runTest {
        selectNavigator("waze")
        setManualPackage("com.vendor.waze")

        dispatcher.dispatch(actionDef("""{"app":"maps","lat":57.0,"lon":36.0}"""), null)
        val intent = shadowOf(app).nextStartedActivity
        assertEquals("yandexmaps://maps.yandex.ru/?rtext=~57.0,36.0&rtt=auto", intent.dataString)
        assertEquals(null, intent.`package`)
    }

    /** With Yandex chosen, a manual package pins its links, which otherwise resolve by scheme. */
    @Test fun yandex_manual_package_pins_routes_and_home() = runTest {
        selectNavigator(RouteNavigatorUris.YANDEX)
        setManualPackage("ru.yandex.yandexnavi.vendor")

        dispatcher.dispatch(actionDef("""{"lat":57.0,"lon":36.0}"""), null)
        val route = shadowOf(app).nextStartedActivity
        assertEquals("yandexnavi://build_route_on_map?lat_to=57.0&lon_to=36.0", route.dataString)
        assertEquals("ru.yandex.yandexnavi.vendor", route.`package`)

        dispatcher.dispatch(actionDef("""{"shortcut":"home"}"""), null)
        assertEquals("ru.yandex.yandexnavi.vendor", shadowOf(app).nextStartedActivity.`package`)
    }

    /** A Navigator installed only as a store variant gets the Home/Work action, not the absent canonical one. */
    @Test fun home_shortcut_goes_to_the_installed_navigator_variant() = runTest {
        installLauncherApp("ru.yandex.yandexnavi.rustore", "Навигатор")

        dispatcher.dispatch(actionDef("""{"shortcut":"home"}"""), null)
        assertEquals("ru.yandex.yandexnavi.rustore", shadowOf(app).nextStartedActivity.`package`)
        assertEquals("ru.yandex.yandexnavi.rustore", dispatcher.willOpenPinned(org.json.JSONObject("""{"shortcut":"home"}""")))
    }

    /** Fork 76aca583: the setting sends the route to Google Maps' own URL, pinned to the app. */
    @Test fun google_maps_selected_and_installed_opens_google_maps() = runTest {
        selectNavigator(RouteNavigatorUris.GOOGLE_MAPS)
        installLauncherApp("com.google.android.apps.maps", "Карты")

        val res = dispatcher.dispatch(actionDef("""{"lat":57.0,"lon":36.0}"""), null)
        assertTrue(res.success)
        assertEquals(null, res.reason)
        val intent = shadowOf(app).nextStartedActivity
        assertEquals(
            "https://www.google.com/maps/dir/?api=1&destination=57.0%2C36.0&travelmode=driving&dir_action=navigate",
            intent.dataString,
        )
        assertEquals("com.google.android.apps.maps", intent.`package`)
    }

    /** Google Maps chosen but absent: the action still works, through Yandex, and says why. */
    @Test fun google_maps_selected_but_missing_falls_back_to_yandex() = runTest {
        selectNavigator(RouteNavigatorUris.GOOGLE_MAPS)

        val res = dispatcher.dispatch(actionDef("""{"lat":57.0,"lon":36.0}"""), null)
        assertTrue(res.success)
        assertTrue("the reason must mention the fallback: ${res.reason}", res.reason!!.contains("Google Maps"))
        val intent = shadowOf(app).nextStartedActivity
        assertEquals("yandexnavi://build_route_on_map?lat_to=57.0&lon_to=36.0", intent.dataString)
        assertEquals(null, intent.`package`)
    }

    /** The MicroG (ReVanced) build is found and preferred, search and pin included (fork 1df6d6c3). */
    @Test fun google_maps_revanced_build_gets_the_route_search_and_pin() = runTest {
        selectNavigator(RouteNavigatorUris.GOOGLE_MAPS)
        installLauncherApp("com.google.android.apps.maps", "Карты")
        installLauncherApp("app.revanced.android.apps.maps", "Google Maps")

        dispatcher.dispatch(actionDef("""{"query":"кафе"}"""), null)
        val search = shadowOf(app).nextStartedActivity
        assertTrue(search.dataString!!.startsWith("https://www.google.com/maps/search/?api=1&query="))
        assertEquals("app.revanced.android.apps.maps", search.`package`)

        dispatcher.dispatch(actionDef("""{"show":true,"lat":55.75,"lon":37.62}"""), null)
        assertEquals("app.revanced.android.apps.maps", shadowOf(app).nextStartedActivity.`package`)
        assertEquals("app.revanced.android.apps.maps",
            dispatcher.willOpenPinned(org.json.JSONObject("""{"lat":57.0,"lon":36.0}""")))
    }

    /** Fork 00b5d4a5: a manual package overrides the detected Google Maps build. */
    @Test fun manual_package_overrides_selected_google_maps_variant() = runTest {
        selectNavigator(RouteNavigatorUris.GOOGLE_MAPS)
        installLauncherApp("com.google.android.apps.maps", "Карты")
        setManualPackage("app.rvx.android.apps.maps")

        val res = dispatcher.dispatch(actionDef("""{"lat":57.0,"lon":36.0}"""), null)
        assertTrue(res.success)
        assertEquals("app.rvx.android.apps.maps", shadowOf(app).nextStartedActivity.`package`)
    }

    /** Google Maps has no Home/Work deep link: refused with advice, not sent to another app. */
    @Test fun google_maps_home_shortcut_is_refused_with_advice() = runTest {
        selectNavigator(RouteNavigatorUris.GOOGLE_MAPS)
        installLauncherApp("com.google.android.apps.maps", "Карты")

        val res = dispatcher.dispatch(actionDef("""{"shortcut":"home","go":true}"""), null)
        assertFalse(res.success)
        assertTrue(res.reason!!, res.reason!!.contains("BYDMate"))
        assertEquals(null, shadowOf(app).nextStartedActivity)
        assertFalse(dispatcher.autoGoSupported(org.json.JSONObject("""{"shortcut":"home"}""")))
    }

    // --- willOpenMaps: what AgentTools asks to pick the right foreground-verification app ---

    @Test fun `willOpenMaps follows an explicit app and the installed Maps setting`() {
        assertTrue("explicit app maps", dispatcher.willOpenMaps(org.json.JSONObject("""{"app":"maps"}""")))

        selectNavigator(RouteNavigatorUris.MAPS)
        assertFalse("setting maps, not installed",
            dispatcher.willOpenMaps(org.json.JSONObject("""{"lat":57.0,"lon":36.0}""")))

        installYandexMaps()
        assertTrue("setting maps, installed", dispatcher.willOpenMaps(org.json.JSONObject("""{"lat":57.0,"lon":36.0}""")))
        assertTrue("setting maps, shortcut", dispatcher.willOpenMaps(org.json.JSONObject("""{"shortcut":"home"}""")))
    }

    private fun selectNavigator(value: String) {
        app.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .edit().putString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, value).commit()
    }

    private fun setManualPackage(pkg: String) {
        app.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .edit().putString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR_PACKAGE, pkg).commit()
    }

    /** A launcher entry of [pkg] labelled [label]. */
    private fun installLauncherApp(pkg: String, label: String) {
        val component = android.content.ComponentName(pkg, "$pkg.Main")
        val pm = shadowOf(app.packageManager)
        pm.addActivityIfNotPresent(component).nonLocalizedLabel = label
        pm.addIntentFilterForActivity(
            component,
            android.content.IntentFilter(Intent.ACTION_MAIN).apply { addCategory(Intent.CATEGORY_LAUNCHER) },
        )
    }

    /** A launcher activity for 2GIS (the dispatcher finds the package either way: it exists). */
    private fun installDgis() {
        val pm = shadowOf(app.packageManager)
        pm.addActivityIfNotPresent(
            android.content.ComponentName("ru.dublgis.dgismobile", "ru.dublgis.dgismobile.Main"))
        pm.addIntentFilterForActivity(
            android.content.ComponentName("ru.dublgis.dgismobile", "ru.dublgis.dgismobile.Main"),
            android.content.IntentFilter(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_LAUNCHER)
            },
        )
    }

    /** Same as [installDgis], for Waze (#305). */
    private fun installWaze() {
        val pm = shadowOf(app.packageManager)
        pm.addActivityIfNotPresent(android.content.ComponentName("com.waze", "com.waze.FreeMapAppActivity"))
        pm.addIntentFilterForActivity(
            android.content.ComponentName("com.waze", "com.waze.FreeMapAppActivity"),
            android.content.IntentFilter(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_LAUNCHER)
            },
        )
    }

    /** Same as [installDgis], for one of the store variants of Yandex Maps (#200). */
    private fun installYandexMaps() {
        val pm = shadowOf(app.packageManager)
        pm.addActivityIfNotPresent(
            android.content.ComponentName("ru.yandex.yandexmaps", "ru.yandex.yandexmaps.Main"))
        pm.addIntentFilterForActivity(
            android.content.ComponentName("ru.yandex.yandexmaps", "ru.yandex.yandexmaps.Main"),
            android.content.IntentFilter(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_LAUNCHER)
            },
        )
    }
}
