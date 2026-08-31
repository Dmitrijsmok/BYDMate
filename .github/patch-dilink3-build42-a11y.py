from pathlib import Path

# Build 42: move the steering-wheel microphone interception test one level above Activity.
# Real-car build41 proved Activity.dispatchKeyEvent consumes both 304 DOWN/UP while the BYD
# assistant still launches. The stock HelperDaemon already has a narrow, non-clobbering
# TX_ENABLE_ACCESSIBILITY operation, but its protocol constants target the production package.
# This diagnostic build retargets ONLY those self-package constants to the .dilink3diag APK,
# starts a version-matched helper, enables this APK's SteeringWheelKeyService, and logs whether
# Android actually binds it before the block test.

# ---------------------------------------------------------------------------
# 1) Retarget helper's narrow self-package operations to the diagnostic applicationId.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/helper/HelperBinderProtocol.kt')
s = p.read_text()
old_pkg = 'const val APP_PACKAGE = "com.bydmate.app"'
new_pkg = 'const val APP_PACKAGE = "com.bydmate.app.dilink3diag"'
if old_pkg not in s:
    raise SystemExit('build42 APP_PACKAGE anchor not found')
s = s.replace(old_pkg, new_pkg, 1)
old_component = '"com.bydmate.app/com.bydmate.app.cluster.SteeringWheelKeyService"'
new_component = '"com.bydmate.app.dilink3diag/com.bydmate.app.cluster.SteeringWheelKeyService"'
if old_component not in s:
    raise SystemExit('build42 accessibility component anchor not found')
s = s.replace(old_component, new_component, 1)
p.write_text(s)
print('Build42: helper self-package retargeted to diagnostic APK')

# ---------------------------------------------------------------------------
# 2) Wizard: boot the helper, enable THIS APK's accessibility service, and wait for a real bind.
# ---------------------------------------------------------------------------
p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

import_anchor = 'import com.bydmate.app.cluster.SteeringWheelKeyService\n'
import_replacement = '''import com.bydmate.app.cluster.SteeringWheelKeyService
import com.bydmate.app.cluster.ClusterEntryPoint
import dagger.hilt.android.EntryPointAccessors
'''
if import_anchor not in s:
    raise SystemExit('build42 wizard import anchor not found')
s = s.replace(import_anchor, import_replacement, 1)

vars_anchor = '''    val audioManager = remember { context.getSystemService(Context.AUDIO_SERVICE) as AudioManager }\n'''
vars_replacement = '''    val audioManager = remember { context.getSystemService(Context.AUDIO_SERVICE) as AudioManager }
    val clusterEntryPoint = remember {
        EntryPointAccessors.fromApplication(context.applicationContext, ClusterEntryPoint::class.java)
    }
    val helperClient = remember { clusterEntryPoint.helperClient() }
    val helperBootstrap = remember { clusterEntryPoint.helperBootstrap() }
    var build42HelperReady by remember { mutableStateOf<Boolean?>(null) }
    var build42A11yEnableResult by remember { mutableStateOf<Boolean?>(null) }
    var build42A11yConnectedAfterEnable by remember { mutableStateOf<Boolean?>(null) }
'''
if vars_anchor not in s:
    raise SystemExit('build42 wizard vars anchor not found')
s = s.replace(vars_anchor, vars_replacement, 1)

launch_anchor = '''    LaunchedEffect(Unit) {\n'''
launch_insert = '''    LaunchedEffect(Unit) {
        // Build42: use the app's existing shell-uid helper, but with diagnostic-package constants.
        // enableAccessibilityService() appends our component; it never overwrites other enabled
        // accessibility services. A real SteeringWheelKeyService.onServiceConnected is the only
        // success criterion for the subsequent 304 interception test.
        DiLink3DebugLog.log(context, "BUILD42_HELPER_START", "package=${context.packageName} expectedA11y=com.bydmate.app.dilink3diag/com.bydmate.app.cluster.SteeringWheelKeyService")
        val helperOk = runCatching { helperBootstrap.ensureRunning() }
            .onFailure { DiLink3DebugLog.log(context, "BUILD42_HELPER_ERROR", "${it::class.java.simpleName}: ${it.message}") }
            .getOrDefault(false)
        build42HelperReady = helperOk
        DiLink3DebugLog.log(context, "BUILD42_HELPER_READY", "ready=$helperOk")
        if (helperOk) {
            val enableOk = runCatching { helperClient.enableAccessibilityService() }
                .onFailure { DiLink3DebugLog.log(context, "BUILD42_A11Y_ENABLE_ERROR", "${it::class.java.simpleName}: ${it.message}") }
                .getOrDefault(false)
            build42A11yEnableResult = enableOk
            DiLink3DebugLog.log(context, "BUILD42_A11Y_ENABLE_RESULT", "accepted=$enableOk connectedBeforeWait=${SteeringWheelKeyService.isConnected}")
            repeat(30) {
                if (SteeringWheelKeyService.isConnected) return@repeat
                delay(100)
            }
            build42A11yConnectedAfterEnable = SteeringWheelKeyService.isConnected
            DiLink3DebugLog.log(
                context,
                "BUILD42_A11Y_BIND_RESULT",
                "helper=$helperOk enableAccepted=$enableOk connected=${SteeringWheelKeyService.isConnected}"
            )
        } else {
            build42A11yEnableResult = false
            build42A11yConnectedAfterEnable = false
            DiLink3DebugLog.log(context, "BUILD42_A11Y_BIND_RESULT", "helper=false enableAccepted=false connected=${SteeringWheelKeyService.isConnected}")
        }
'''
if launch_anchor not in s:
    raise SystemExit('build42 LaunchedEffect anchor not found')
s = s.replace(launch_anchor, launch_insert, 1)

# Make step-3 arming explicitly report whether the higher-level Accessibility filter is live.
block_log = '''DiLink3DebugLog.log(context, "WIZARD_BLOCK_TEST_ARMED", "keyCode=$key")'''
block_log_new = '''DiLink3DebugLog.log(context, "WIZARD_BLOCK_TEST_ARMED", "keyCode=$key a11yConnected=${SteeringWheelKeyService.isConnected} helper=$build42HelperReady enableAccepted=$build42A11yEnableResult")'''
if block_log not in s:
    raise SystemExit('build42 block log anchor not found')
s = s.replace(block_log, block_log_new, 1)

# Add the build42 state to the step-1 diagnostic text if the warmup line exists.
status_anchor = '''                        Text("ℹ️ Прогрев: $warmupStatus")\n'''
status_new = '''                        Text("ℹ️ Прогрев: $warmupStatus")
                        Text("ℹ️ Build42 helper: ${build42HelperReady ?: "..."}; A11y enable: ${build42A11yEnableResult ?: "..."}; connected: ${build42A11yConnectedAfterEnable ?: SteeringWheelKeyService.isConnected}")
'''
if status_anchor in s:
    s = s.replace(status_anchor, status_new, 1)
else:
    print('Build42: warmup status UI anchor absent; logs still contain helper/A11y state')

p.write_text(s)
print('Build42: wizard now enables diagnostic AccessibilityService before the 304 block test')
