package dev.forge

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.speech.RecognizerIntent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import dev.forge.tools.SpeechInput
import dev.forge.ui.ChatViewModel
import dev.forge.ui.screens.ChatScreen
import dev.forge.ui.screens.SettingsScreen
import dev.forge.ui.theme.ForgeTheme

class MainActivity : ComponentActivity() {
    private val vm: ChatViewModel by viewModels()
    private var onSpeech: ((String) -> Unit)? = null
    private var sharedText by mutableStateOf<String?>(null)
    private var themeMode by mutableStateOf("system")

    private val speech = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        val text = r.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()
        onSpeech?.invoke(text ?: ""); onSpeech = null
        SpeechInput.deliver(text)
    }
    private val perms = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {}

    private fun launchSpeech() {
        runCatching {
            speech.launch(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_PROMPT, "Talk to Forge"))
        }.onFailure { SpeechInput.deliver(null) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        themeMode = ForgeApp.instance.settings.darkMode
        handleShare(intent)
        SpeechInput.launcher = { runOnUiThread { launchSpeech() } }
        val wanted = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= 33) wanted += Manifest.permission.POST_NOTIFICATIONS
        perms.launch(wanted.toTypedArray())

        setContent {
            ForgeTheme(themeMode) {
                val nav = rememberNavController()
                NavHost(nav, startDestination = "chat") {
                    composable("chat") {
                        ChatScreen(vm, onOpenSettings = { nav.navigate("settings") },
                            onMic = { cb -> onSpeech = cb; launchSpeech() }, sharedText = sharedText)
                    }
                    composable("settings") { SettingsScreen(onBack = { nav.popBackStack() }, onThemeChanged = { themeMode = it }) }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); handleShare(intent) }

    private fun handleShare(intent: Intent?) {
        if (intent?.action != Intent.ACTION_SEND) return
        val text = intent.getStringExtra(Intent.EXTRA_TEXT)
        val uri = intent.getParcelableExtra<android.net.Uri>(Intent.EXTRA_STREAM)
        if (uri != null) {
            // copy shared file into the workspace so tools can reach it
            runCatching {
                val name = uri.lastPathSegment?.substringAfterLast('/') ?: "shared_${System.currentTimeMillis()}"
                val dest = java.io.File(ForgeApp.instance.paths.workspace, "shared/$name").apply { parentFile?.mkdirs() }
                contentResolver.openInputStream(uri)?.use { it.copyTo(dest.outputStream()) }
                sharedText = "I shared a file: ${dest.path}\n${text ?: ""}".trim()
            }
        } else if (text != null) sharedText = text
    }

    override fun onDestroy() { super.onDestroy(); SpeechInput.launcher = null }
}
