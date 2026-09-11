#!/usr/bin/env python3
from pathlib import Path


def once(s, old, new, name):
    if old not in s:
        raise SystemExit(f"Build91 export anchor missing: {name}")
    return s.replace(old, new, 1)

p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text()
s = once(s, "import android.content.ClipData\n", "import android.content.ClipData\nimport android.content.ContentValues\n", "ContentValues")
s = once(s, "import android.os.Looper\n", "import android.os.Looper\nimport android.os.Environment\n", "Environment")
s = once(s, "import android.provider.Settings\n", "import android.provider.Settings\nimport android.provider.MediaStore\n", "MediaStore")
s = once(s, "import java.util.Locale\n", "import java.util.Locale\nimport java.util.zip.ZipEntry\nimport java.util.zip.ZipOutputStream\n", "zip imports")

s = once(s, '''    fun share(context: Context) {
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
''', '''    fun shareText(context: Context) {
        val text = snapshot()
        if (text.isBlank()) { Toast.makeText(context, "Лог пуст", Toast.LENGTH_SHORT).show(); return }
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
            putExtra(Intent.EXTRA_SUBJECT, "BYDMate Assistant Lab Build91")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        runCatching { context.startActivity(Intent.createChooser(send, "Отправить лог как текст").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
            .onFailure { Toast.makeText(context, "Share text: ${it.message}", Toast.LENGTH_LONG).show() }
    }

    fun saveTxt(context: Context) = saveDownload(context, false)
    fun saveZip(context: Context) = saveDownload(context, true)

    private fun saveDownload(context: Context, zipped: Boolean) {
        val text = snapshot()
        if (text.isBlank()) { Toast.makeText(context, "Лог пуст", Toast.LENGTH_SHORT).show(); return }
        val ext = if (zipped) "zip" else "txt"
        val name = "BYDMate-AssistantLab-Build91-${System.currentTimeMillis()}.$ext"
        runCatching {
            val values = ContentValues().apply {
                put(MediaStore.MediaColumns.DISPLAY_NAME, name)
                put(MediaStore.MediaColumns.MIME_TYPE, if (zipped) "application/zip" else "text/plain")
                put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/BYDMate")
            }
            val uri = context.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                ?: error("Downloads insert failed")
            context.contentResolver.openOutputStream(uri)?.use { out ->
                if (zipped) ZipOutputStream(out).use { zip ->
                    zip.putNextEntry(ZipEntry("BYDMate-AssistantLab-Build91.txt"))
                    zip.write(text.toByteArray(Charsets.UTF_8))
                    zip.closeEntry()
                } else out.write(text.toByteArray(Charsets.UTF_8))
            } ?: error("Downloads output failed")
            add("EXPORT saved Downloads/BYDMate/$name")
            Toast.makeText(context, "Сохранено: Downloads/BYDMate/$name", Toast.LENGTH_LONG).show()
        }.onFailure { Toast.makeText(context, "Save log: ${it.message}", Toast.LENGTH_LONG).show() }
    }
''', "share functions")

s = once(s, '''        content.addView(buttonRow(context,
            actionButton(context, "START TRACE") {
                AssistantLabTrace.start(context)
                refresh()
            },
            actionButton(context, "STOP + SAVE") {
                AssistantLabTrace.stop(context)
                refresh()
            },
            actionButton(context, "SHARE LOG") { AssistantLabTrace.share(context) },
            actionButton(context, "CLEAR") { AssistantLabTrace.clear(); refresh() },
        ))
''', '''        content.addView(buttonRow(context,
            actionButton(context, "START TRACE") { AssistantLabTrace.start(context); refresh() },
            actionButton(context, "STOP") { AssistantLabTrace.stop(context); refresh() },
            actionButton(context, "CLEAR") { AssistantLabTrace.clear(); refresh() },
        ))
        content.addView(buttonRow(context,
            actionButton(context, "SHARE TEXT") { AssistantLabTrace.shareText(context) },
            actionButton(context, "SAVE TXT") { AssistantLabTrace.saveTxt(context) },
            actionButton(context, "SAVE ZIP") { AssistantLabTrace.saveZip(context) },
        ))
''', "export buttons")

p.write_text(s)
print("Build91 log export applied")
