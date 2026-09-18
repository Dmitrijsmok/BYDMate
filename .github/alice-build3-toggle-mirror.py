#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
old = '''    fun setDisableNativeAssistant(disabled: Boolean) {
        _uiState.update { it.copy(disableNativeAssistant = disabled) }
        viewModelScope.launch {
'''
new = '''    fun setDisableNativeAssistant(disabled: Boolean) {
        _uiState.update { it.copy(disableNativeAssistant = disabled) }
        // Alice3: the Accessibility service already reads this fast SharedPreferences mirror.
        // A sentinel selects the DiLink3 dual-event route (304 trigger + 327 consume).
        // OFF uses keycode 0 so the physical microphone button is completely fail-open.
        appContext.getSharedPreferences("voice", Context.MODE_PRIVATE).edit()
            .putInt("voice_keycode", if (disabled) com.bydmate.app.cluster.DILINK3_ALICE_ROUTE else 0)
            .apply()
        Log.i("AliceBuild1", "DILINK3_TAKEOVER enabled=$disabled")
        viewModelScope.launch {
'''
if old not in s:
    raise SystemExit("Alice3 native-assistant toggle anchor missing")
p.write_text(s.replace(old, new, 1))
print("Alice3 native-assistant toggle mirror applied")
