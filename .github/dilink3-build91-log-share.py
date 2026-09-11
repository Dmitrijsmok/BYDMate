#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text()
old = '''    fun share(context: Context) {
        val text = snapshot()
        if (text.isBlank()) { Toast.makeText(context, "Лог пуст", Toast.LENGTH_SHORT).show(); return }
        runCatching {
            val dir = File(context.cacheDir, "assistant-lab-share").apply { mkdirs() }
            val file = File(dir, "BYDMate-AssistantLab-Build91.txt").apply { writeText(text) }
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.assistantlab.files", file)
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_STREAM, uri)
                clipData = ClipData.newRawUri("BYDMate Assistant Lab", uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(Intent.createChooser(send, "Отправить лог").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }.onFailure { Toast.makeText(context, "Share log: ${it.message}", Toast.LENGTH_LONG).show() }
    }
'''
new = '''    fun share(context: Context) {
        val text = snapshot()
        if (text.isBlank()) { Toast.makeText(context, "Лог пуст", Toast.LENGTH_SHORT).show(); return }
        runCatching {
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, text)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(Intent.createChooser(send, "Отправить лог как текст").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }.onFailure { Toast.makeText(context, "Share log: ${it.message}", Toast.LENGTH_LONG).show() }
    }
'''
if old not in s:
    raise SystemExit("Build91 share anchor missing")
s = s.replace(old, new, 1)
s = s.replace('actionButton(context, "SHARE LOG") { AssistantLabTrace.share(context) }', 'actionButton(context, "SHARE TEXT") { AssistantLabTrace.share(context) }', 1)
p.write_text(s)
print("Build91 text-share applied")
