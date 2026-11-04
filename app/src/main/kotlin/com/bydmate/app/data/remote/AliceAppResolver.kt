package com.bydmate.app.data.remote

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import com.bydmate.app.data.automation.RouteNavigatorDiscovery
import com.bydmate.app.data.automation.RouteNavigatorResolver
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/** What one Alice app action resolves to on this head unit; null package = not installed. */
data class VoiceAppMatch(val action: String, val appLabel: String?, val packageName: String?)

/**
 * Resolves an [AliceAppTarget.App] to an installed package with a launcher entry, and shows in
 * Settings what every app action would open here.
 */
@Singleton
class AliceAppResolver @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    internal fun resolve(target: AliceAppTarget.App): Result<String> {
        val pm = context.packageManager
        target.packages.firstOrNull { hasLaunchIntent(pm, it) }?.let { return Result.success(it) }

        val apps = launcherApps(pm)
        val exact = apps.firstOrNull { (pkg, label) ->
            label in target.labels || pkg.lowercase() in target.packageTokens
        }
        val match = exact ?: apps.firstOrNull { (pkg, label) ->
            target.labels.any { it.isNotEmpty() && label.contains(it) } ||
                target.packageTokens.any { pkg.lowercase().contains(it) }
        }
        return match?.let { Result.success(it.first) } ?: Result.failure(IllegalStateException(APP_NOT_INSTALLED))
    }

    /** The package [AliceAppTarget.Navigator] opens, picked as ActionDispatcher.openNavigatorApp picks
     *  it; null when none of its candidates has a launcher entry. */
    internal fun navigatorPackage(navigator: String?): String? {
        val launcher = RouteNavigatorDiscovery.launcherApps(context.packageManager)
        val launchable = launcher.mapTo(HashSet()) { it.packageName }
        return RouteNavigatorResolver.launchCandidates(RouteNavigatorResolver.choice(context), navigator, launcher)
            .firstOrNull { it in launchable }
    }

    fun diagnosticMatches(): List<VoiceAppMatch> {
        val pm = context.packageManager
        return AliceAppCatalog.diagnosticActions.map { action ->
            val pkg = when (val target = AliceAppCatalog.forAction(action)) {
                is AliceAppTarget.Navigator -> navigatorPackage(target.navigator)
                is AliceAppTarget.App -> resolve(target).getOrNull()
                AliceAppTarget.Self -> context.packageName
                null -> null
            }
            val label = pkg?.let {
                runCatching { pm.getApplicationLabel(pm.getApplicationInfo(it, 0)).toString() }.getOrNull()
            }
            VoiceAppMatch(action, label, pkg)
        }
    }

    private fun hasLaunchIntent(pm: PackageManager, pkg: String): Boolean =
        runCatching { pm.getLaunchIntentForPackage(pkg) != null }.getOrDefault(false)

    /** (package, lowercase label) of every launcher entry. */
    private fun launcherApps(pm: PackageManager): List<Pair<String, String>> {
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        return runCatching {
            pm.queryIntentActivities(intent, 0).mapNotNull { info ->
                val pkg = info.activityInfo?.packageName ?: return@mapNotNull null
                val label = runCatching { info.loadLabel(pm).toString() }.getOrDefault("")
                pkg to label.trim().lowercase().replace('ё', 'е')
            }
        }.getOrDefault(emptyList())
    }

    companion object {
        const val APP_NOT_INSTALLED = "app_not_installed"
    }
}
