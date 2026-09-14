#!/usr/bin/env python3
from pathlib import Path

p = Path('app/src/main/kotlin/com/bydmate/app/AliceSetupActivity.kt')
s = p.read_text()
anchor = '        when (intent?.getStringExtra("mode")) {\n'
case = '''            "autostart" -> {
                AlertDialog.Builder(this)
                    .setTitle("BYDMate Alice")
                    .setMessage("Для стабильной работы после перезапуска DiLink разрешите автозапуск BYDMate Alice в настройках приложения.")
                    .setPositiveButton("Открыть настройки") { _, _ ->
                        startActivity(
                            Intent(
                                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.parse("package:$packageName")
                            )
                        )
                        finish()
                    }
                    .setNegativeButton("Позже") { _, _ -> finish() }
                    .show()
            }
'''
if anchor not in s:
    raise SystemExit('Alice4.2 setup activity anchor missing')
s = s.replace(anchor, anchor + case, 1)
p.write_text(s)

p = Path('app/src/main/kotlin/com/bydmate/app/MainActivity.kt')
s = p.read_text()
if 'import android.content.Intent\n' not in s:
    s = s.replace('import android.content.Context\n', 'import android.content.Context\nimport android.content.Intent\n', 1)
old = '''        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        requestPermissionsIfNeeded()
'''
new = '''        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        requestPermissionsIfNeeded()
        maybePromptAliceAutostartOnce()
'''
if old not in s:
    raise SystemExit('Alice4.2 MainActivity onCreate anchor missing')
s = s.replace(old, new, 1)
helper_anchor = '    private fun requestPermissionsIfNeeded() {\n'
helper = '''    private fun maybePromptAliceAutostartOnce() {
        val voicePrefs = getSharedPreferences("voice", Context.MODE_PRIVATE)
        if (!voicePrefs.getBoolean("alice_native_takeover", false)) return
        val setup = getSharedPreferences("alice4_setup", Context.MODE_PRIVATE)
        if (setup.getBoolean("autostart_prompted_v42", false)) return
        setup.edit().putBoolean("autostart_prompted_v42", true).apply()
        runCatching {
            startActivity(
                Intent(this, AliceSetupActivity::class.java).apply {
                    putExtra("mode", "autostart")
                }
            )
        }.onFailure { Log.w(TAG, "Autostart setup prompt failed: ${it.message}") }
    }

'''
if helper_anchor not in s:
    raise SystemExit('Alice4.2 MainActivity helper anchor missing')
s = s.replace(helper_anchor, helper + helper_anchor, 1)
p.write_text(s)

p = Path('app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt')
s = p.read_text()
old = '''    fun setAgentEnabled(enabled: Boolean) {
        _uiState.update { it.copy(agentEnabled = enabled) }
        if (enabled && !_uiState.value.voiceEnabled) {
            setVoiceEnabled(true)
        }
        viewModelScope.launch { settingsRepository.setAgentEnabled(enabled) }
    }
'''
new = '''    fun setAgentEnabled(enabled: Boolean) {
        _uiState.update { it.copy(agentEnabled = enabled) }
        if (enabled && !_uiState.value.voiceEnabled) {
            setVoiceEnabled(true)
        }
        if (enabled) {
            val setup = appContext.getSharedPreferences("alice4_setup", Context.MODE_PRIVATE)
            if (!setup.getBoolean("autostart_prompted_v42", false)) {
                setup.edit().putBoolean("autostart_prompted_v42", true).apply()
                runCatching {
                    appContext.startActivity(
                        Intent(appContext, com.bydmate.app.AliceSetupActivity::class.java).apply {
                            putExtra("mode", "autostart")
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        }
                    )
                }.onFailure { Log.w("AliceBuild1", "Autostart setup prompt failed: ${it.message}") }
            }
        }
        viewModelScope.launch { settingsRepository.setAgentEnabled(enabled) }
    }
'''
if old not in s:
    raise SystemExit('Alice4.2 agent autostart anchor missing')
s = s.replace(old, new, 1)
p.write_text(s)
print('Alice4.2 autostart guidance applied')
