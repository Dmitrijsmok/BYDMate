from pathlib import Path

p = Path('app/src/main/kotlin/com/bydmate/app/ui/diagnostics/DiLink3VoiceDebugPanel.kt')
s = p.read_text()

anchor = '            Text("После серии тестов просто экспортируйте один лог. Особо важны LAB_*, SYSTEM_ASSISTANT_ROUTING и A11Y_KEY_*.", style = MaterialTheme.typography.bodySmall)'
if anchor not in s:
    raise SystemExit('build46 log-share UI anchor not found')

if 'ОТПРАВИТЬ ДИАГНОСТИЧЕСКИЙ ЛОГ' not in s:
    ui = '''            Button(
                onClick = {
                    DiLink3DebugLog.log(context, "BUILD46_LOG_SHARE_PRESSED", "path=${context.filesDir.absolutePath}/dilink3-voice-debug.log")
                    val opened = DiLink3DebugLog.shareToTelegram(context)
                    status = if (opened) {
                        "Окно отправки лога открыто"
                    } else {
                        "Не удалось открыть отправку лога"
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("ОТПРАВИТЬ ДИАГНОСТИЧЕСКИЙ ЛОГ")
            }
            Text(
                "Файл: ${context.filesDir.absolutePath}/dilink3-voice-debug.log",
                style = MaterialTheme.typography.bodySmall,
            )
'''
    s = s.replace(anchor, ui + anchor, 1)

p.write_text(s)
print('build46 visible log-share button installed')
