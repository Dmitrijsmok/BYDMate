#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
old = '''    fun setAgentEnabled(enabled: Boolean) {
        _uiState.update { it.copy(agentEnabled = enabled) }
        viewModelScope.launch { settingsRepository.setAgentEnabled(enabled) }
    }
'''
new = '''    fun setAgentEnabled(enabled: Boolean) {
        _uiState.update { it.copy(agentEnabled = enabled) }
        if (enabled && !_uiState.value.voiceEnabled) {
            setVoiceEnabled(true)
        }
        viewModelScope.launch { settingsRepository.setAgentEnabled(enabled) }
    }
'''
if old not in s:
    raise SystemExit("Alice4 agent master anchor missing")
p.write_text(s.replace(old, new, 1))
print("Alice4 agent master patch applied")
