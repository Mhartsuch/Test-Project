package dev.forge.tools

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.BatteryManager
import android.speech.tts.TextToSpeech
import androidx.core.app.NotificationCompat
import dev.forge.ForgeApp
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.util.Locale

/**
 * Device capabilities. Exposed both as the `device` tool and to JS skills via forge.android(action, args).
 * Adding a new action here (or in a JS skill) is how Forge grows device features like voice.
 */
object AndroidTools {
    fun all(): List<Tool> = listOf(device)

    private val device = object : Tool("device",
        "Device actions: info | clipboard_get | clipboard_set(text) | tts(text) | notify(title,text) | open_url(url) | share(text) | battery | vibrate(ms). Speech input is available in the chat UI mic button and to skills via forge.android('stt').",
        Schema.obj("action" to Schema.str("Action name"), "args" to Schema.str("JSON args"), required = listOf("action"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext) =
            device(ctx.app, args.getString("action"), runCatching { JSONObject(args.optString("args", "{}").ifBlank { "{}" }) }.getOrDefault(JSONObject()))
    }

    private var tts: TextToSpeech? = null
    private var ttsReady = CompletableDeferred<Boolean>()

    suspend fun device(app: ForgeApp, action: String, a: JSONObject): String = withContext(Dispatchers.Main) {
        when (action) {
            "info" -> JSONObject().put("manufacturer", android.os.Build.MANUFACTURER).put("model", android.os.Build.MODEL)
                .put("android", android.os.Build.VERSION.RELEASE).put("sdk", android.os.Build.VERSION.SDK_INT)
                .put("abi", android.os.Build.SUPPORTED_ABIS.joinToString()).put("locale", Locale.getDefault().toString())
                .put("freeStorageMB", app.filesDir.usableSpace / 1_000_000).toString(2)
            "clipboard_get" -> (app.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).primaryClip?.getItemAt(0)?.coerceToText(app)?.toString() ?: ""
            "clipboard_set" -> { (app.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("forge", a.optString("text"))); "ok" }
            "tts" -> speak(app, a.optString("text"))
            "notify" -> { notify(app, a.optString("title", "Forge"), a.optString("text", "")); "ok" }
            "open_url" -> { app.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(a.getString("url"))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); "ok" }
            "share" -> { app.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, a.optString("text")), "Share").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); "ok" }
            "battery" -> (app.getSystemService(Context.BATTERY_SERVICE) as BatteryManager).getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY).toString() + "%"
            "vibrate" -> { (app.getSystemService(Context.VIBRATOR_SERVICE) as android.os.Vibrator).vibrate(android.os.VibrationEffect.createOneShot(a.optLong("ms", 100), android.os.VibrationEffect.DEFAULT_AMPLITUDE)); "ok" }
            "stt" -> SpeechInput.listen(app)
            else -> "ERROR: unknown action '$action'"
        }
    }

    private suspend fun speak(app: ForgeApp, text: String): String {
        if (tts == null) {
            ttsReady = CompletableDeferred()
            tts = TextToSpeech(app) { status -> ttsReady.complete(status == TextToSpeech.SUCCESS) }
        }
        if (withTimeoutOrNull(5000) { ttsReady.await() } != true) return "ERROR: TTS engine unavailable"
        tts!!.speak(text, TextToSpeech.QUEUE_ADD, null, "forge-${System.nanoTime()}")
        return "speaking ${text.length} chars"
    }

    const val CHANNEL = "forge"
    fun ensureChannel(app: Context) {
        val nm = app.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(NotificationChannel(CHANNEL, "Forge", NotificationManager.IMPORTANCE_DEFAULT))
    }
    fun notify(app: Context, title: String, text: String, id: Int = (System.currentTimeMillis() % 100000).toInt()) {
        ensureChannel(app)
        val n = NotificationCompat.Builder(app, CHANNEL).setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title).setContentText(text).setStyle(NotificationCompat.BigTextStyle().bigText(text)).setAutoCancel(true).build()
        runCatching { (app.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(id, n) }
    }
}

/**
 * Speech-to-text hook. The Activity registers a listener; skills/tools call listen() and get the transcript.
 * This is intentionally minimal — the agent can extend it (e.g. continuous voice chat) as a Tier-2 change.
 */
object SpeechInput {
    @Volatile private var pending: CompletableDeferred<String>? = null
    var launcher: (() -> Unit)? = null   // set by MainActivity

    suspend fun listen(app: ForgeApp): String {
        val l = launcher ?: return "ERROR: speech input needs the Forge UI to be open"
        val d = CompletableDeferred<String>(); pending = d
        l()
        return withTimeoutOrNull(60_000) { d.await() } ?: "ERROR: no speech received"
    }
    fun deliver(text: String?) { pending?.complete(text ?: ""); pending = null }
}
