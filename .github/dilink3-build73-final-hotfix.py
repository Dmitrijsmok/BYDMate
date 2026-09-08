#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build73 final anchor missing: {label}")
    return text.replace(old, new, 1)

# Final production semantics: a connection that passes the exact live-agent probe
# becomes primary AND leaves the agent enabled. A failed probe restores both previous
# primary and previous enabled state. This mirrors the proven Build66 wizard behavior
# without bringing the wizard UI back.
p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsViewModel.kt")
s = p.read_text()
old = '''            if (!wasEnabled) settingsRepository.setString(SettingsRepository.KEY_AGENT_ENABLED, "false")
            if (compatible && conn != null) {
                settingsRepository.setString(SettingsRepository.KEY_AGENT_PRIMARY_CONN, conn.id)
                _uiState.update { it.copy(primaryConn = conn.id) }
            } else {
                settingsRepository.setString(SettingsRepository.KEY_AGENT_PRIMARY_CONN, previousPrimary)
            }
'''
new = '''            if (compatible && conn != null) {
                settingsRepository.setString(SettingsRepository.KEY_AGENT_PRIMARY_CONN, conn.id)
                settingsRepository.setString(SettingsRepository.KEY_AGENT_ENABLED, "true")
                _uiState.update { it.copy(primaryConn = conn.id, agentEnabled = true) }
            } else {
                settingsRepository.setString(SettingsRepository.KEY_AGENT_PRIMARY_CONN, previousPrimary)
                if (!wasEnabled) settingsRepository.setString(SettingsRepository.KEY_AGENT_ENABLED, "false")
                _uiState.update { it.copy(primaryConn = previousPrimary, agentEnabled = wasEnabled) }
            }
'''
s = replace_once(s, old, new, "compatibility keeps agent enabled")
p.write_text(s)

print("Build73 final hotfix applied: successful compatibility => primary + agent enabled")
