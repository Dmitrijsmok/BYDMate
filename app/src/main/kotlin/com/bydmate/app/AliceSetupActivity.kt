package com.bydmate.app

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle

class AliceSetupActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val mode = intent?.getStringExtra("mode")
        if (mode == "browser_missing") {
            AlertDialog.Builder(this)
                .setTitle("Alice AI")
                .setMessage("Для использования Alice AI необходимо установить Yandex Browser.")
                .setPositiveButton("OK") { _, _ ->
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://apkpure.com/yandex-browser-with-protect/com.yandex.browser")))
                    finish()
                }
                .setNegativeButton("Отмена") { _, _ -> finish() }
                .show()
        } else {
            AlertDialog.Builder(this)
                .setTitle("Alice AI")
                .setMessage("Для работы Alice AI необходимо разрешить Yandex Browser доступ к микрофону.")
                .setPositiveButton("OK") { _, _ -> finish() }
                .show()
        }
    }
}
