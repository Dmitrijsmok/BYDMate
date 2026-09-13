#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/cluster/SteeringWheelKeyService.kt")
s = p.read_text()

start = s.find("    private fun launchYandexAliceOrApkPure() {")
end = s.find("    private fun openApkPure()", start)
if start < 0 or end < 0:
    raise SystemExit("Alice3 browser launcher anchors missing")
launcher = '''    private fun launchYandexAliceOrApkPure() {
        val browserLaunchIntent = packageManager.getLaunchIntentForPackage(YANDEX_BROWSER_PACKAGE)
        if (browserLaunchIntent == null) {
            Log.w(TAG, "YANDEX_BROWSER_MISSING package=$YANDEX_BROWSER_PACKAGE")
            cancelAliceClick("browser_missing")
            showAliceSetup("browser_missing")
            return
        }

        val micGranted = packageManager.checkPermission(
            android.Manifest.permission.RECORD_AUDIO,
            YANDEX_BROWSER_PACKAGE,
        ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        if (!micGranted) {
            Log.w(TAG, "YANDEX_MIC_PERMISSION_MISSING")
            cancelAliceClick("microphone_permission_missing")
            showAliceSetup("microphone_permission")
            return
        }

        Log.i(TAG, "YANDEX_BROWSER_FOUND package=$YANDEX_BROWSER_PACKAGE micGranted=true")

        // Build95 behavior: if Browser is already visible, first try the exact top-right
        // toolbar Alice control before moving or relaunching the Browser window.
        aliceClickPending = true
        if (tryClickAliceNode("warm_toolbar")) {
            Log.i(TAG, "ALICE_TOOLBAR_EXACT warm=true")
            return
        }
        aliceClickPending = false

        val launched = runCatching {
            browserLaunchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            startActivity(browserLaunchIntent)
            true
        }.getOrElse {
            Log.e(TAG, "YANDEX_BROWSER_LAUNCH_FAILED", it)
            false
        }
        Log.i(TAG, "YANDEX_BROWSER_LAUNCH normal=true success=$launched")
        if (launched) armAliceClick() else cancelAliceClick("launch_failed")
    }

    private fun showAliceSetup(mode: String) {
        val ok = runCatching {
            startActivity(
                Intent(this, com.bydmate.app.AliceSetupActivity::class.java).apply {
                    putExtra("mode", mode)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
            )
            true
        }.getOrDefault(false)
        Log.i(TAG, "ALICE_SETUP_DIALOG mode=$mode success=$ok")
    }

'''
s = s[:start] + launcher + s[end:]

s = s.replace(
    'private const val APKPURE_YANDEX_SEARCH_URL = "https://apkpure.com/search?q=com.yandex.browser"',
    'private const val APKPURE_YANDEX_SEARCH_URL = "https://apkpure.com/yandex-browser-with-protect/com.yandex.browser"',
    1,
)

fallback_start = s.find("        // Fallback: content description used by the old working experiment.")
fallback_end = s.find("        return false\n    }\n\n    private fun clickAliceCandidate", fallback_start)
if fallback_start < 0 or fallback_end < 0:
    raise SystemExit("Alice3 fallback anchors missing")
s = s[:fallback_start] + "        Log.d(TAG, \"ALICE_TOOLBAR_EXACT_NOT_FOUND source=$source\")\n" + s[fallback_end:]

p.write_text(s)
print("Alice3 exact toolbar Browser route applied")
