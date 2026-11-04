package com.bydmate.app.data.remote

import android.content.Context
import com.bydmate.app.data.automation.RouteNavigatorDiscovery
import com.bydmate.app.data.automation.RouteNavigatorResolver
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/** What one app action resolves to on this head unit; null package = not installed. [names] are
 *  the spoken names (Alice and the local assistant alike) that lead to it. */
data class VoiceAppMatch(
    val action: String,
    val appLabel: String?,
    val packageName: String?,
    val names: List<String> = emptyList(),
)

/**
 * Resolves an [AliceAppTarget.App] to an installed package with a launcher entry, through the
 * same [AliceAppCatalog.pick] the agent's launch_app uses, and shows in Settings what every app
 * action and name would open here.
 */
@Singleton
class AliceAppResolver @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    internal fun resolve(target: AliceAppTarget.App): Result<String> =
        AliceAppCatalog.pick(target, RouteNavigatorDiscovery.launcherApps(context.packageManager)).firstOrNull()
            ?.let { Result.success(it.packageName) }
            ?: Result.failure(IllegalStateException(APP_NOT_INSTALLED))

    /** The package [AliceAppTarget.Navigator] opens, picked as ActionDispatcher.openNavigatorApp picks
     *  it; null when none of its candidates has a launcher entry. */
    internal fun navigatorPackage(navigator: String?): String? {
        val launcher = RouteNavigatorDiscovery.launcherApps(context.packageManager)
        val launchable = launcher.mapTo(HashSet()) { it.packageName }
        return RouteNavigatorResolver.launchCandidates(RouteNavigatorResolver.choice(context), navigator, launcher)
            .firstOrNull { it in launchable }
    }

    /** The package [target] opens here, or null when nothing would open. */
    internal fun packageFor(target: AliceAppTarget): String? = when (target) {
        is AliceAppTarget.Navigator -> navigatorPackage(target.navigator)
        is AliceAppTarget.App -> resolve(target).getOrNull()
        AliceAppTarget.Self -> context.packageName
        is AliceAppTarget.Settings -> AliceAppCatalog.settingsPackage(target.section)
            .takeIf { RouteNavigatorDiscovery.packageExists(context.packageManager, it) }
    }

    fun diagnosticMatches(): List<VoiceAppMatch> {
        val pm = context.packageManager
        return AliceAppCatalog.diagnosticActions.map { action ->
            val pkg = AliceAppCatalog.forAction(action)?.let(::packageFor)
            val label = pkg?.let {
                runCatching { pm.getApplicationLabel(pm.getApplicationInfo(it, 0)).toString() }.getOrNull()
            }
            VoiceAppMatch(action, label, pkg, AliceAppCatalog.spokenNames(action))
        }
    }

    companion object {
        const val APP_NOT_INSTALLED = "app_not_installed"
    }
}
