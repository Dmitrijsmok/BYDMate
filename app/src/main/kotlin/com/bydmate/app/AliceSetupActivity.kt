package com.bydmate.app

import android.app.Activity
import android.app.AlertDialog
import android.os.Bundle

class AliceSetupActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AlertDialog.Builder(this)
            .setTitle("Alice AI")
            .setMessage("Yandex Browser setup is required")
            .setPositiveButton("OK") { _, _ -> finish() }
            .show()
    }
}
