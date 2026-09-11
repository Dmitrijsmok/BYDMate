#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text()
s = s.replace("import android.content.ClipData\n", "import android.content.ClipData\nimport android.content.ContentValues\n", 1)
s = s.replace("import android.os.Looper\n", "import android.os.Looper\nimport android.os.Environment\n", 1)
s = s.replace("import android.provider.Settings\n", "import android.provider.Settings\nimport android.provider.MediaStore\n", 1)
s = s.replace("import java.util.Locale\n", "import java.util.Locale\nimport java.util.zip.ZipEntry\nimport java.util.zip.ZipOutputStream\n", 1)

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
                putExtra(Intent.EXTRA_SUBJECT, "BYDMate Assistant Lab Build91")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(Intent.createChooser(send, "Отправить лог как текст").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }.onFailure { Toast.makeText(context, "Share log: ${it.message}", Toast.LENGTH_LONG).show() }
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
                if (zipped) {
                    ZipOutputStream(out).use { zip ->
                        zip.putNextEntry(ZipEntry("BYDMate-AssistantLab-Build91.txt"))
                        zip.write(text.toByteArray(Charsets.UTF_8))
                        zip.closeEntry()
                    }
                } else {
                    out.write(text.toByteArray(Charsets.UTF_8))
                }
            } ?: error("Downloads output failed")
            add("EXPORT saved Downloads/BYDMate/$name")
            Toast.makeText(context, "Сохранено: Downloads/BYDMate/$name", Toast.LENGTH_LONG).show()
        }.onFailure { Toast.makeText(context, "Save log: ${it.message}", Toast.LENGTH_LONG).show() }
    }
'''
if old not in s:
    raise SystemExit("Build91 share anchor missing")
s = s.replace(old, new, 1)
s = s.replace('actionButton(context, "SHARE LOG") { AssistantLabTrace.share(context) }', 'actionButton(context, "SHARE TEXT") { AssistantLabTrace.share(context) }', 1)

anchor = '''        val alice = actionButton(context, "Alice") { launchOrInstall(context, AssistantTarget.ALICE) }
'''
export_row = '''        content.addView(buttonRow(context,
            actionButton(context, "SAVE TXT") { AssistantLabTrace.saveTxt(context) },
            actionButton(context, "SAVE ZIP") { AssistantLabTrace.saveZip(context) },
        ))

'''
if anchor not in s:
    raise SystemExit("Build91 export row anchor missing")
s = s.replace(anchor, export_row + anchor, 1)
p.write_text(s)
print("Build91 text-share + TXT/ZIP export applied")