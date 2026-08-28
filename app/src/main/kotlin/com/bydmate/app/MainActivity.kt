package com.bydmate.app

import android.Manifest
import android.content.Context
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.os.Build
import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.unit.dp
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.bydmate.app.data.local.LocalePreferences
import com.bydmate.app.data.repository.SettingsRepository
import com.bydmate.app.service.TrackingService
import com.bydmate.app.service.UpdateChecker
import com.bydmate.app.ui.components.ConsumptionThresholds
import com.bydmate.app.ui.components.LocalConsumptionThresholds
import com.bydmate.app.ui.navigation.AppNavigation
import com.bydmate.app.ui.theme.BYDMateTheme
import com.bydmate.app.voice.VoiceController
import com.bydmate.app.voice.VoiceUiState
import dagger.hilt.android.AndroidEntryPoint
import java.util.Locale
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : AppCompatActivity() {

    @Inject lateinit var settingsRepository: SettingsRepository
    @Inject lateinit var updateChecker: UpdateChecker
    @Inject lateinit var voiceController: VoiceController

    companion object {
        private const val TAG = "MainActivity"
        private const val PERMISSION_REQUEST_CODE = 1001
        private const val BACKGROUND_LOCATION_REQUEST_CODE = 1002
        private const val AUDIO_PERMISSION_REQUEST_CODE = 1003
        private const val DEFAULT_LANG = "ru"
    }

    override fun attachBaseContext(newBase: Context) {
        // Cold-start: read stored language and wrap baseContext with a Configuration
        // that already has the right locale. Without this, initial layouts paint in
        // the system locale for one frame before AppCompat catches up.
        val lang = newBase.getSharedPreferences(LocalePreferences.FILE, Context.MODE_PRIVATE)
            .getString(LocalePreferences.KEY_LANG, null) ?: DEFAULT_LANG
        val locale = Locale.forLanguageTag(lang)
        Locale.setDefault(locale)
        val cfg = Configuration(newBase.resources.configuration).apply { setLocale(locale) }
        super.attachBaseContext(newBase.createConfigurationContext(cfg))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        requestPermissionsIfNeeded()

        setContent {
            val thresholds by produceState(initialValue = ConsumptionThresholds.Default) {
                settingsRepository.observeConsumptionThresholds().collect { (good, bad) ->
                    value = ConsumptionThresholds(good = good, bad = bad)
                }
            }

            // Runtime locale switch: listen to LocalePreferences via SharedPreferences,
            // mutate Activity resources in place (deprecated since API 24 but functional
            // on Android 12), then bump `lang` state. The new LocalConfiguration value
            // triggers recomposition of every stringResource consumer in the tree.
            // LocalContext is left untouched so Hilt's `instanceof Activity` check passes.
            val prefs = remember {
                applicationContext.getSharedPreferences(
                    LocalePreferences.FILE, Context.MODE_PRIVATE
                )
            }
            var lang by remember {
                mutableStateOf(prefs.getString(LocalePreferences.KEY_LANG, null) ?: DEFAULT_LANG)
            }
            DisposableEffect(prefs) {
                val listener = SharedPreferences.OnSharedPreferenceChangeListener { p, key ->
                    if (key == LocalePreferences.KEY_LANG) {
                        val newLang = p.getString(key, DEFAULT_LANG) ?: DEFAULT_LANG
                        if (newLang != lang) {
                            val locale = Locale.forLanguageTag(newLang)
                            Locale.setDefault(locale)
                            val res = resources
                            val cfg = Configuration(res.configuration).apply { setLocale(locale) }
                            @Suppress("DEPRECATION")
                            res.updateConfiguration(cfg, res.displayMetrics)
                            lang = newLang
                        }
                    }
                }
                prefs.registerOnSharedPreferenceChangeListener(listener)
                onDispose { prefs.unregisterOnSharedPreferenceChangeListener(listener) }
            }

            val localizedConfig = remember(lang) {
                Configuration(resources.configuration).apply {
                    setLocale(Locale.forLanguageTag(lang))
                }
            }

            val voiceState by voiceController.state.collectAsState()
            val voiceListening by voiceController.listening.collectAsState()
            var lastHeard by remember { mutableStateOf("") }
            var micGranted by remember {
                mutableStateOf(
                    ContextCompat.checkSelfPermission(
                        this@MainActivity,
                        Manifest.permission.RECORD_AUDIO,
                    ) == PackageManager.PERMISSION_GRANTED
                )
            }

            LaunchedEffect(voiceState) {
                when (val s = voiceState) {
                    is VoiceUiState.Done -> if (s.transcript.isNotBlank()) lastHeard = s.transcript
                    is VoiceUiState.NotUnderstood -> if (s.transcript.isNotBlank()) lastHeard = s.transcript
                    else -> Unit
                }
            }

            BYDMateTheme {
                CompositionLocalProvider(
                    LocalConfiguration provides localizedConfig,
                    LocalConsumptionThresholds provides thresholds,
                ) {
                    Box(modifier = Modifier.fillMaxSize()) {
                        AppNavigation(
                            settingsRepository = settingsRepository,
                            updateChecker = updateChecker,
                        )

                        // DiLink3 diagnostic panel: intentionally always visible in this debug APK.
                        // It makes the ASR state observable even when the normal floating overlay
                        // cannot be shown by this DiLink generation.
                        Surface(
                            tonalElevation = 6.dp,
                            shadowElevation = 6.dp,
                            shape = MaterialTheme.shapes.medium,
                            modifier = Modifier
                                .align(Alignment.BottomStart)
                                .padding(start = 16.dp, bottom = 72.dp)
                                .widthIn(max = 520.dp),
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text("DiLink3 Voice Debug", style = MaterialTheme.typography.titleSmall)
                                Text("Mic permission: ${if (micGranted) "GRANTED" else "DENIED"}")
                                Text("Voice lang: ${voiceController.currentLang()}")
                                Text("Listening: $voiceListening")
                                Text("State: ${voiceStateLabel(voiceState)}")
                                Text("Heard: ${lastHeard.ifBlank { "<nothing yet>" }}")
                            }
                        }

                        // DiLink3 diagnostic: manual PTT entry point. This deliberately calls the
                        // same VoiceController path as the steering-wheel PTT so microphone,
                        // GigaAM ASR, routing and TTS are exercised without relying on DiLink5
                        // steering-wheel integration.
                        Button(
                            onClick = {
                                micGranted = ContextCompat.checkSelfPermission(
                                    this@MainActivity,
                                    Manifest.permission.RECORD_AUDIO,
                                ) == PackageManager.PERMISSION_GRANTED
                                Log.i(
                                    TAG,
                                    "DiLink3 manual voice pressed: micGranted=$micGranted lang=${voiceController.currentLang()} listening=${voiceController.listening.value} state=${voiceController.state.value}",
                                )
                                if (!micGranted) {
                                    ActivityCompat.requestPermissions(
                                        this@MainActivity,
                                        arrayOf(Manifest.permission.RECORD_AUDIO),
                                        AUDIO_PERMISSION_REQUEST_CODE,
                                    )
                                } else {
                                    voiceController.onPttPressed()
                                }
                            },
                            modifier = Modifier
                                .align(Alignment.BottomEnd)
                                .padding(end = 24.dp, bottom = 72.dp),
                        ) {
                            Text(if (voiceListening) "■ Stop Voice" else "🎤 Voice")
                        }
                    }
                }
            }
        }
    }

    private fun voiceStateLabel(state: VoiceUiState): String = when (state) {
        VoiceUiState.Idle -> "IDLE"
        VoiceUiState.Listening -> "LISTENING"
        VoiceUiState.Thinking -> "THINKING"
        is VoiceUiState.Done -> "DONE: ${state.transcript}"
        is VoiceUiState.Blocked -> "BLOCKED: ${state.reason}"
        is VoiceUiState.NotUnderstood -> "NOT_UNDERSTOOD: ${state.transcript}"
        is VoiceUiState.AgentAnswer -> "AGENT: ${state.text}"
    }

    private fun requestPermissionsIfNeeded() {
        val permissions = mutableListOf<String>()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
            != PackageManager.PERMISSION_GRANTED
        ) {
            permissions.add(Manifest.permission.ACCESS_FINE_LOCATION)
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_EXTERNAL_STORAGE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            permissions.add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            permissions.add(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            permissions.add(Manifest.permission.RECORD_AUDIO)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        if (permissions.isNotEmpty()) {
            Log.d(TAG, "Requesting permissions: $permissions")
            ActivityCompat.requestPermissions(this, permissions.toTypedArray(), PERMISSION_REQUEST_CODE)
        } else {
            // Base permissions granted, check background location
            requestBackgroundLocationIfNeeded()
            startTrackingService()
        }
    }

    /**
     * On Android 10+ (API 29+), ACCESS_BACKGROUND_LOCATION must be requested
     * SEPARATELY after ACCESS_FINE_LOCATION is granted. Without it, the
     * foreground service GPS does not work when the activity is not visible.
     */
    private fun requestBackgroundLocationIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION)
            != PackageManager.PERMISSION_GRANTED
        ) {
            Log.d(TAG, "Requesting ACCESS_BACKGROUND_LOCATION separately")
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.ACCESS_BACKGROUND_LOCATION),
                BACKGROUND_LOCATION_REQUEST_CODE
            )
        }
    }

    @Suppress("DEPRECATION")
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        when (requestCode) {
            PERMISSION_REQUEST_CODE -> {
                val denied = mutableListOf<String>()
                permissions.forEachIndexed { index, permission ->
                    if (grantResults.getOrNull(index) == PackageManager.PERMISSION_GRANTED) {
                        Log.i(TAG, "Permission granted: $permission")
                    } else {
                        Log.w(TAG, "Permission denied: $permission")
                        denied.add(permission)
                    }
                }
                if (denied.isNotEmpty()) {
                    Log.w(TAG, "Starting TrackingService with denied permissions: $denied")
                }
                // Now request background location (must be after fine location)
                requestBackgroundLocationIfNeeded()
                startTrackingService()
            }
            BACKGROUND_LOCATION_REQUEST_CODE -> {
                val granted = grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED
                if (granted) {
                    Log.i(TAG, "Background location granted — GPS will work in background")
                } else {
                    Log.w(TAG, "Background location denied — GPS may not work when app is hidden")
                }
            }
            AUDIO_PERMISSION_REQUEST_CODE -> {
                val granted = grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED
                Log.i(TAG, "Manual voice RECORD_AUDIO permission result: granted=$granted")
            }
        }
    }

    private fun startTrackingService() {
        TrackingService.start(this)
    }
}
