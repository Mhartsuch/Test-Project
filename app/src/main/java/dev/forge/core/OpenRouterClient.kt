package dev.forge.core

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Streaming events emitted while the model responds. */
sealed class StreamEvent {
    data class Text(val delta: String) : StreamEvent()
    data class Reasoning(val delta: String) : StreamEvent()
    data class ToolCallDelta(val index: Int, val id: String?, val name: String?, val argsDelta: String?) : StreamEvent()
    data class Usage(val prompt: Int, val completion: Int, val cost: Double?) : StreamEvent()
    data class Done(val finishReason: String?) : StreamEvent()
    data class Error(val message: String) : StreamEvent()
}

data class ModelInfo(val id: String, val name: String, val contextLength: Int, val supportsTools: Boolean, val promptPrice: Double, val completionPrice: Double)

/**
 * Minimal OpenRouter client (OpenAI-compatible /chat/completions with SSE streaming + tool calling).
 * Kept dependency-light on purpose so the agent can safely modify it.
 */
class OpenRouterClient(private val settings: Settings) {
    companion object {
        const val BASE = "https://openrouter.ai/api/v1"
        private val JSON = "application/json".toMediaType()
    }

    val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.MINUTES)
        .writeTimeout(2, TimeUnit.MINUTES)
        .build()

    private fun authed(builder: Request.Builder) = builder
        .header("Authorization", "Bearer ${settings.openRouterKey}")
        .header("HTTP-Referer", "https://github.com/forge-android")
        .header("X-Title", "Forge")

    suspend fun listModels(): List<ModelInfo> = withContext(Dispatchers.IO) {
        val req = authed(Request.Builder().url("$BASE/models")).get().build()
        http.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw IOException("models: HTTP ${resp.code}")
            val arr = JSONObject(resp.body!!.string()).getJSONArray("data")
            (0 until arr.length()).map { i ->
                val m = arr.getJSONObject(i)
                val pricing = m.optJSONObject("pricing")
                val params = m.optJSONArray("supported_parameters")
                val tools = params != null && (0 until params.length()).any { params.getString(it) == "tools" }
                ModelInfo(
                    id = m.getString("id"),
                    name = m.optString("name", m.getString("id")),
                    contextLength = m.optInt("context_length", 0),
                    supportsTools = tools,
                    promptPrice = pricing?.optString("prompt")?.toDoubleOrNull() ?: 0.0,
                    completionPrice = pricing?.optString("completion")?.toDoubleOrNull() ?: 0.0,
                )
            }.sortedBy { it.id }
        }
    }

    /**
     * Streams a chat completion. `onEvent` is invoked on the IO thread; callers should marshal to Main.
     */
    suspend fun stream(
        model: String,
        messages: List<JSONObject>,
        tools: JSONArray?,
        temperature: Float,
        reasoningEffort: String,
        maxTokens: Int = 16_000,
        onEvent: suspend (StreamEvent) -> Unit,
    ) = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("model", model)
            .put("messages", JSONArray(messages))
            .put("stream", true)
            .put("temperature", temperature.toDouble())
            .put("max_tokens", maxTokens)
            .put("usage", JSONObject().put("include", true))
        if (tools != null && tools.length() > 0) {
            body.put("tools", tools)
            body.put("tool_choice", "auto")
            body.put("parallel_tool_calls", true)
        }
        if (reasoningEffort != "none") body.put("reasoning", JSONObject().put("effort", reasoningEffort))

        val req = authed(Request.Builder().url("$BASE/chat/completions"))
            .post(body.toString().toRequestBody(JSON)).build()

        try {
            http.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) {
                    val err = resp.body?.string().orEmpty()
                    onEvent(StreamEvent.Error("HTTP ${resp.code}: ${err.take(800)}")); return@withContext
                }
                val source = resp.body!!.source()
                var finish: String? = null
                while (!source.exhausted()) {
                    val line = source.readUtf8Line() ?: break
                    if (!line.startsWith("data:")) continue
                    val data = line.removePrefix("data:").trim()
                    if (data == "[DONE]") break
                    val chunk = try { JSONObject(data) } catch (_: Exception) { continue }
                    chunk.optJSONObject("error")?.let { onEvent(StreamEvent.Error(it.optString("message", it.toString()))); return@withContext }
                    chunk.optJSONObject("usage")?.let { u ->
                        onEvent(StreamEvent.Usage(u.optInt("prompt_tokens"), u.optInt("completion_tokens"), u.optDouble("cost").takeIf { !it.isNaN() }))
                    }
                    val choices = chunk.optJSONArray("choices") ?: continue
                    if (choices.length() == 0) continue
                    val choice = choices.getJSONObject(0)
                    choice.optString("finish_reason", "").takeIf { it.isNotEmpty() && it != "null" }?.let { finish = it }
                    val delta = choice.optJSONObject("delta") ?: continue
                    delta.optString("content", "").takeIf { it.isNotEmpty() && it != "null" }?.let { onEvent(StreamEvent.Text(it)) }
                    // OpenRouter reasoning: either `reasoning` string or `reasoning_details` array
                    delta.optString("reasoning", "").takeIf { it.isNotEmpty() && it != "null" }?.let { onEvent(StreamEvent.Reasoning(it)) }
                    delta.optJSONArray("reasoning_details")?.let { rd ->
                        for (i in 0 until rd.length()) {
                            val t = rd.getJSONObject(i).optString("text", "")
                            if (t.isNotEmpty()) onEvent(StreamEvent.Reasoning(t))
                        }
                    }
                    delta.optJSONArray("tool_calls")?.let { tc ->
                        for (i in 0 until tc.length()) {
                            val c = tc.getJSONObject(i)
                            val fn = c.optJSONObject("function")
                            onEvent(StreamEvent.ToolCallDelta(
                                index = c.optInt("index", i),
                                id = c.optString("id", "").ifEmpty { null },
                                name = fn?.optString("name", "")?.ifEmpty { null },
                                argsDelta = fn?.optString("arguments", "")?.ifEmpty { null },
                            ))
                        }
                    }
                }
                onEvent(StreamEvent.Done(finish))
            }
        } catch (e: Exception) {
            onEvent(StreamEvent.Error(e.message ?: e.toString()))
        }
    }

    /** Non-streaming one-shot completion, used for summaries/titles. */
    suspend fun complete(model: String, system: String, user: String, maxTokens: Int = 4000): String = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("model", model)
            .put("messages", JSONArray().put(JSONObject().put("role", "system").put("content", system)).put(JSONObject().put("role", "user").put("content", user)))
            .put("max_tokens", maxTokens).put("temperature", 0.2)
        val req = authed(Request.Builder().url("$BASE/chat/completions")).post(body.toString().toRequestBody(JSON)).build()
        http.newCall(req).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw IOException("HTTP ${resp.code}: ${text.take(500)}")
            JSONObject(text).getJSONArray("choices").getJSONObject(0).getJSONObject("message").optString("content", "")
        }
    }
}
