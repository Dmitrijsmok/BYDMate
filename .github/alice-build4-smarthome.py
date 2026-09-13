#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/ui/settings/SettingsScreen.kt")
s = p.read_text()
old = '''            SettingsSection.entries.forEach { section ->
                val isHidden = section == SettingsSection.SMART_HOME
                if (isHidden && !smartHomeUnlocked) return@forEach
                RailItem(
                    section = section,
                    isActive = section == selected,
                    isHidden = isHidden,
                    onClick = { onSelect(section) },
                )
            }

            Spacer(modifier = Modifier.weight(1f))
            HorizontalDivider(color = CardBorder)
'''
new = '''            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
            ) {
                SettingsSection.entries.forEach { section ->
                    val isHidden = section == SettingsSection.SMART_HOME
                    if (isHidden && !smartHomeUnlocked) return@forEach
                    RailItem(
                        section = section,
                        isActive = section == selected,
                        isHidden = isHidden,
                        onClick = { onSelect(section) },
                    )
                }
            }

            HorizontalDivider(color = CardBorder)
'''
if old not in s:
    raise SystemExit("Alice4 Smart Home rail anchor missing")
p.write_text(s.replace(old, new, 1))
print("Alice4 Smart Home rail patch applied")
