#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()

old = '''            SettingToggleRow(
                title = stringResource(R.string.agent_enable_title),
                description = stringResource(R.string.agent_enable_desc),
                checked = state.agentEnabled,
                onCheckedChange = { viewModel.setAgentEnabled(it) },
            )
'''
new = '''            SettingToggleRow(
                title = stringResource(R.string.agent_enable_title),
                description = stringResource(R.string.agent_enable_desc),
                checked = state.agentEnabled,
                onCheckedChange = { on ->
                    if (on && !hasAudioPerm()) {
                        pendingVoiceAction = "AGENT"
                        audioPermLauncher.launch(Manifest.permission.RECORD_AUDIO)
                    } else {
                        viewModel.setAgentEnabled(on)
                    }
                },
            )
'''
if old not in s:
    raise SystemExit("Alice4 agent toggle anchor missing")
s = s.replace(old, new, 1)

old = '                "ENABLE" -> viewModel.setVoiceEnabled(true)\n'
new = '                "ENABLE" -> viewModel.setVoiceEnabled(true)\n                "AGENT" -> viewModel.setAgentEnabled(true)\n'
if old not in s:
    raise SystemExit("Alice4 permission result anchor missing")
s = s.replace(old, new, 1)

p.write_text(s)
print("Alice4 agent permission patch applied")
