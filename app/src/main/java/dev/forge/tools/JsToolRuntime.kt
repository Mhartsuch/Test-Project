package dev.forge.tools

import android.annotation.SuppressLint
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import dev.forge.ForgeApp
import dev.forge.self.SkillStore
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

/**
 * Hot-loadable JavaScript tool runtime backed by a hidden WebView (present on every Android device,
 * so no extra native dependency). Each skill's tool.js is wrapped in its own module scope; functions
 * it exports become tools named `<skill>_<fn>` and can call back into Kotlin through the `forge` bridge.
 *
 * This is what lets Forge add capabilities to itself instantly, without a rebuild.
 */
class JsToolRuntime(private val app: ForgeApp) {
    private val main = Handler(Looper.getMainLooper())
    private var web: WebView? = null
    private val pending = ConcurrentHashMap<String, CompletableDeferred<Result<String>>>()
    private val declared = ConcurrentHashMap<String, MutableList<JSONObject>>() // skill -> declarations
    @Volatile var lastErrors: List<String> = emptyList(); private set
    private val errors = mutableListOf<String>()
    private val TAG = "ForgeJS"

    @SuppressLint("SetJavaScriptEnabled")
    private fun ensureWebView(): WebView {
        web?.let { return it }
        check(Looper.myLooper() == Looper.getMainLooper())
        val w = WebView(app)
        w.settings.javaScriptEnabled = true
        w.settings.allowFileAccess = false
        w.addJavascriptInterface(Bridge(), "ForgeBridge")
        w.loadDataWithBaseURL("https://forge.local/", BOOTSTRAP_HTML, "text/html", "utf-8", null)
        web = w
        return w
    }

    private suspend fun onMain(block: () -> Unit) {
        val d = CompletableDeferred<Unit>()
        main.post { runCatching(block).onFailure { d.completeExceptionally(it) }; d.complete(Unit) }
        d.await()
    }

    private suspend fun evalAwait(js: String, timeoutMs: Long = 120_000): String {
        val id = UUID.randomUUID().toString()
        val d = CompletableDeferred<Result<String>>()
        pending[id] = d
        onMain { ensureWebView().evaluateJavascript(js.replace("__ID__", id), null) }
        return try { withTimeout(timeoutMs) { d.await() }.getOrThrow() } finally { pending.remove(id) }
    }

    /** Loads every skill's tool.js and returns the tools they declare. Blocking-safe from a background thread. */
    fun loadSkills(store: SkillStore): List<Tool> {
        if (Looper.myLooper() == Looper.getMainLooper()) {
            // Called during Application.onCreate: defer the actual load, return empty for now.
            main.postDelayed({ Thread { runCatching { loadSkillsBlocking(store) }.onFailure { Log.e(TAG, "load", it) } }.start() }, 800)
            return emptyList()
        }
        return loadSkillsBlocking(store)
    }

    private fun loadSkillsBlocking(store: SkillStore): List<Tool> = runBlocking {
        errors.clear(); declared.clear()
        // wait for bootstrap
        for (attempt in 0 until 20) {
            val r = runCatching { evalAwait("ForgeBridge.complete('__ID__', typeof forge==='object' ? 'ok':'no')", 3000) }.getOrNull()
            if (r == "ok") break
            delay(300)
        }
        val tools = mutableListOf<Tool>()
        for (s in store.all()) {
            val js = s.js ?: continue
            val wrapped = transformModule(js)
            val r = runCatching { evalAwait("forge.__load('__ID__', ${JSONObject.quote(s.name)}, ${JSONObject.quote(wrapped)})") }
            r.onFailure { errors += "${s.name}: ${it.message}" }
            for (decl in declared[s.name].orEmpty()) {
                val fn = decl.getString("name")
                tools += JsTool(this@JsToolRuntime, s.name, fn, decl.optString("description", ""), decl.optJSONObject("parameters") ?: JSONObject().put("type", "object").put("properties", JSONObject()))
            }
        }
        lastErrors = errors.toList()
        // Surface the loaded tools to the registry (registry may have been created before this finished).
        app.tools.setDynamic(tools)
        tools
    }

    suspend fun call(skill: String, fn: String, args: JSONObject): String =
        evalAwait("forge.__call('__ID__', ${JSONObject.quote(skill)}, ${JSONObject.quote(fn)}, ${args})")

    /** Convert `export function x` / `export const x =` into assignments on the module's exports object. */
    private fun transformModule(js: String): String = js
        .replace(Regex("(?m)^\\s*export\\s+(async\\s+)?function\\s+(\\w+)"), "exports.$2 = $1function $2")
        .replace(Regex("(?m)^\\s*export\\s+(const|let|var)\\s+(\\w+)\\s*="), "exports.$2 =")
        .replace(Regex("(?m)^\\s*export\\s+default\\s+"), "exports.default = ")

    private inner class Bridge {
        @JavascriptInterface fun complete(id: String, result: String) { pending[id]?.complete(Result.success(result)) }
        @JavascriptInterface fun fail(id: String, err: String) { pending[id]?.complete(Result.failure(RuntimeException(err))) }
        @JavascriptInterface fun declare(skill: String, spec: String) { declared.getOrPut(skill) { mutableListOf() }.add(JSONObject(spec)) }
        @JavascriptInterface fun log(msg: String) { Log.i(TAG, msg) }
        @JavascriptInterface fun readFile(path: String): String = runCatching { Sandbox.resolve(app, path).readText() }.getOrElse { "ERROR: ${it.message}" }
        @JavascriptInterface fun writeFile(path: String, text: String): String = runCatching {
            val f = Sandbox.resolve(app, path); Sandbox.assertWritable(app, f); f.parentFile?.mkdirs(); f.writeText(text); "ok" }.getOrElse { "ERROR: ${it.message}" }
        @JavascriptInterface fun listDir(path: String): String = runCatching {
            JSONArray(Sandbox.resolve(app, path).listFiles().orEmpty().map { if (it.isDirectory) it.name + "/" else it.name }).toString() }.getOrElse { "ERROR: ${it.message}" }
        @JavascriptInterface fun shell(cmd: String): String = runBlocking { ShellTools.exec(cmd, app.paths.workspace, 60) }
        @JavascriptInterface fun http(method: String, url: String, headersJson: String, body: String): String = runCatching {
            val b = okhttp3.Request.Builder().url(url)
            if (headersJson.isNotBlank()) JSONObject(headersJson).let { h -> h.keys().forEach { b.header(it, h.getString(it)) } }
            val m = method.uppercase()
            b.method(m, if (m == "GET" || m == "HEAD") null else body.toRequestBody("application/json".toMediaType()))
            app.client.http.newCall(b.build()).execute().use { r -> JSONObject().put("status", r.code).put("body", r.body?.string().orEmpty()).toString() }
        }.getOrElse { "ERROR: ${it.message}" }
        @JavascriptInterface fun android(action: String, argsJson: String): String = runBlocking {
            runCatching { AndroidTools.device(app, action, JSONObject(argsJson.ifBlank { "{}" })) }.getOrElse { "ERROR: ${it.message}" }
        }
    }

    companion object {
        // The JS side of the bridge. Keep in sync with Bridge above.
        val BOOTSTRAP_HTML = """<!doctype html><html><head><meta charset="utf-8"><script>
const forge = {
  __modules: {},
  __current: null,
  declare(spec) { ForgeBridge.declare(forge.__current, JSON.stringify(spec)); },
  log(m) { ForgeBridge.log(String(m)); },
  readFile(p) { return ForgeBridge.readFile(p); },
  writeFile(p, t) { return ForgeBridge.writeFile(p, String(t)); },
  listDir(p) { return JSON.parse(ForgeBridge.listDir(p)); },
  shell(c) { return ForgeBridge.shell(c); },
  http(method, url, headers, body) { const r = ForgeBridge.http(method||'GET', url, headers?JSON.stringify(headers):'', body==null?'':String(body)); try { return JSON.parse(r); } catch(e) { return {status:0, body:r}; } },
  android(action, args) { return ForgeBridge.android(action, JSON.stringify(args||{})); },
  __load(id, name, code) {
    try {
      forge.__current = name;
      const exports = {};
      new Function('forge', 'exports', code)(forge, exports);
      forge.__modules[name] = exports;
      forge.__current = null;
      ForgeBridge.complete(id, 'ok');
    } catch (e) { forge.__current = null; ForgeBridge.fail(id, (e && e.stack) ? e.stack : String(e)); }
  },
  __call(id, name, fn, args) {
    try {
      const mod = forge.__modules[name];
      if (!mod || typeof mod[fn] !== 'function') { ForgeBridge.fail(id, 'no such tool ' + name + '_' + fn); return; }
      Promise.resolve().then(() => mod[fn](args)).then(
        r => ForgeBridge.complete(id, typeof r === 'string' ? r : JSON.stringify(r)),
        e => ForgeBridge.fail(id, (e && e.stack) ? e.stack : String(e)));
    } catch (e) { ForgeBridge.fail(id, String(e)); }
  }
};
window.forge = forge;
</script></head><body></body></html>"""
    }
}

/** Adapter exposing a JS-exported function as a Tool. */
class JsTool(private val rt: JsToolRuntime, private val skill: String, private val fn: String, description: String, params: JSONObject) :
    Tool("${skill}_$fn", "[skill:$skill] $description", params) {
    override suspend fun run(args: JSONObject, ctx: ToolContext): String = rt.call(skill, fn, args)
}
