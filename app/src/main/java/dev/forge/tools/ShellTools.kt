package dev.forge.tools

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

object ShellTools {
    fun all(): List<Tool> = listOf(shell, http, logcat)

    /** Runs a command via the platform shell. This is a real, unprivileged Android shell (toybox). */
    suspend fun exec(cmd: String, cwd: java.io.File, timeoutSec: Int = 60): String = withContext(Dispatchers.IO) {
        val pb = ProcessBuilder("/system/bin/sh", "-c", cmd).directory(cwd).redirectErrorStream(true)
        pb.environment()["HOME"] = cwd.path
        val p = pb.start()
        val out = StringBuilder()
        val reader = Thread { p.inputStream.bufferedReader().forEachLine { if (out.length < 200_000) out.append(it).append('\n') } }
        reader.start()
        val finished = p.waitFor(timeoutSec.toLong(), TimeUnit.SECONDS)
        if (!finished) { p.destroyForcibly(); out.append("\n[killed after ${timeoutSec}s]") }
        reader.join(2000)
        out.append("[exit ${if (finished) p.exitValue() else -1}]")
        out.toString()
    }

    private val shell = object : Tool("shell",
        "Run a shell command with /system/bin/sh in the workspace (or cwd). Available: toybox utils (ls, cat, grep, sed, find, du, ps, top, getprop, dumpsys, am, pm, curl on some devices). No root.",
        Schema.obj("cmd" to Schema.str("Command"), "cwd" to Schema.str("Working dir (default workspace)"), "timeout" to Schema.int("Seconds (default 60)"), required = listOf("cmd"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val cwd = if (args.has("cwd")) Sandbox.resolve(ctx.app, args.getString("cwd")) else ctx.app.paths.workspace
            return exec(args.getString("cmd"), cwd, args.optInt("timeout", 60))
        }
    }

    private val http = object : Tool("http",
        "Make an HTTP request. Returns status, headers (short) and body (truncated to 50k). Use for APIs, docs, downloads (set save_to to write body to a file).",
        Schema.obj("method" to Schema.str("GET/POST/PUT/DELETE"), "url" to Schema.str("URL"), "headers" to Schema.str("JSON object of headers"), "body" to Schema.str("Request body"), "save_to" to Schema.str("Optional file path to save the body"), required = listOf("url"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String = withContext(Dispatchers.IO) {
            val b = Request.Builder().url(args.getString("url"))
            args.optString("headers", "").takeIf { it.isNotBlank() }?.let { h -> val o = JSONObject(h); o.keys().forEach { b.header(it, o.getString(it)) } }
            val method = args.optString("method", "GET").uppercase()
            val body = args.optString("body", "").takeIf { method != "GET" && method != "HEAD" }?.toRequestBody("application/json".toMediaType())
            b.method(method, body)
            ctx.app.client.http.newCall(b.build()).execute().use { r ->
                val save = args.optString("save_to", "")
                if (save.isNotBlank()) {
                    val f = Sandbox.resolve(ctx.app, save); Sandbox.assertWritable(ctx.app, f); f.parentFile?.mkdirs()
                    f.outputStream().use { r.body!!.byteStream().copyTo(it) }
                    return@withContext "HTTP ${r.code}; saved ${f.length()} bytes to $f"
                }
                val text = r.body?.string().orEmpty()
                "HTTP ${r.code} ${r.headers["content-type"] ?: ""}\n" + (if (text.length > 50_000) text.take(50_000) + "\n…[truncated]" else text)
            }
        }
    }

    private val logcat = object : Tool("logcat",
        "Read recent logcat lines from this app's process (for debugging Forge itself or JS tools). Optional grep filter.",
        Schema.obj("filter" to Schema.str("Substring/regex filter"), "lines" to Schema.int("Max lines (default 200)"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val n = args.optInt("lines", 200)
            val raw = exec("logcat -d -v time --pid=${android.os.Process.myPid()} -t ${n * 3}", ctx.app.paths.root, 20)
            val f = args.optString("filter", "")
            val lines = raw.lines().let { l -> if (f.isBlank()) l else l.filter { Regex(f, RegexOption.IGNORE_CASE).containsMatchIn(it) } }
            return lines.takeLast(n).joinToString("\n").ifBlank { "(no log lines; on some devices logcat needs `adb shell pm grant dev.forge android.permission.READ_LOGS`)" }
        }
    }
}
