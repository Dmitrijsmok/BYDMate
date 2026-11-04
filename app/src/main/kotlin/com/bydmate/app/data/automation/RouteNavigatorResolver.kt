package com.bydmate.app.data.automation

import android.content.Context

/** The «Навигатор для маршрутов» setting: the app, and the exact package of a non-standard build. */
internal data class NavigatorChoice(val navigator: String, val manualPackage: String?)

/**
 * Where one navigate action goes: [navigator] is the app whose deep-link dialect is used, [pkg]
 * the package the intent is pinned to (null = resolved by the URI scheme), [fellBackFrom] the
 * chosen app that was replaced by Yandex Navigator because it is not installed.
 */
internal data class NavigatorTarget(val navigator: String, val pkg: String?, val fellBackFrom: String? = null)

/**
 * The one place that turns the setting into an app and a package, for routes (ActionDispatcher)
 * and for opening the app by name (the agent's launch_app, the offline «открой навигатор»).
 */
internal object RouteNavigatorResolver {

    fun choice(context: Context): NavigatorChoice {
        val prefs = runCatching {
            context.getSharedPreferences(RouteNavigatorUris.PREFS_NAME, Context.MODE_PRIVATE)
        }.getOrNull()
        val navigator = runCatching { prefs?.getString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR, null) }.getOrNull()
        val manual = runCatching { prefs?.getString(RouteNavigatorUris.KEY_ROUTE_NAVIGATOR_PACKAGE, null) }.getOrNull()
        return NavigatorChoice(RouteNavigatorUris.normalize(navigator), manual?.trim()?.takeIf(String::isNotEmpty))
    }

    fun resolve(context: Context, requested: String?): NavigatorTarget =
        resolve(choice(context), requested) { RouteNavigatorDiscovery.firstPackage(context.packageManager, it) }

    /**
     * [requested] is the app the command itself named (null = the setting); [installed] gives the
     * package a navigator is installed under, or null. Pure.
     *
     * - The manual package is used as given, for the app it was entered for only: a command that
     *   names another app is never redirected into it.
     * - Yandex Navigator and an explicitly named Yandex Maps are not probed: their links resolve
     *   by scheme, as they always have.
     * - A chosen app that is not installed falls back to Yandex Navigator and says so; an app
     *   the command named stays that app, and a missing one fails honestly.
     */
    fun resolve(choice: NavigatorChoice, requested: String?, installed: (String) -> String?): NavigatorTarget {
        val id = requested ?: choice.navigator
        if (id == choice.navigator && choice.manualPackage != null) return NavigatorTarget(id, choice.manualPackage)
        if (id == RouteNavigatorUris.YANDEX) return NavigatorTarget(id, null)
        if (id == RouteNavigatorUris.MAPS && requested != null) return NavigatorTarget(id, null)
        val pkg = installed(id)
        return when {
            // Maps stays unpinned: the scheme reaches whichever store variant is installed.
            pkg != null -> NavigatorTarget(id, pkg.takeUnless { id == RouteNavigatorUris.MAPS })
            requested != null -> NavigatorTarget(id, RouteNavigatorUris.packageOf(id))
            else -> NavigatorTarget(RouteNavigatorUris.YANDEX, null, fellBackFrom = id)
        }
    }

    /**
     * Packages that open [navigator]'s app, most preferred first: the manual package, the known
     * variants, then [launcher] entries that are builds of it. [navigator] null = the app chosen
     * in settings, and then Yandex Navigator's packages follow as the fallback routes take too.
     * The caller launches the first one it can. Pure.
     */
    fun launchCandidates(
        choice: NavigatorChoice,
        navigator: String?,
        launcher: List<RouteNavigatorDiscovery.LauncherApp>,
    ): List<String> {
        val id = navigator ?: choice.navigator
        fun packagesOf(n: String) = RouteNavigatorDiscovery.knownPackages(n) +
            launcher.filter { RouteNavigatorDiscovery.matches(n, it.packageName, it.label) }.map { it.packageName }
        val manual = listOfNotNull(choice.manualPackage.takeIf { id == choice.navigator })
        val fallback = if (navigator == null) packagesOf(RouteNavigatorUris.YANDEX) else emptyList()
        return (manual + packagesOf(id) + fallback).distinct()
    }
}
