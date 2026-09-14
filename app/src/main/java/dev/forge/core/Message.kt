package dev.forge.core

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

enum class Role { system, user, assistant, tool }

/** One tool invocation requested by the model. */
data class ToolCall(val id: String, val name: String, val arguments: String) {
    fun toJson(): JSONObject = JSONObject()
        .put("id", id).put("type", "function")
        .put("function", JSONObject().put("name", name).put("arguments", arguments))
    companion object {
        fun fromJson(o: JSONObject) = ToolCall(
            o.getString("id"),
            o.getJSONObject("function").getString("name"),
            o.getJSONObject("function").optString("arguments", "{}")
        )
    }
}

/**
 * A chat message in OpenAI/OpenRouter wire format plus Forge metadata.
 * `reasoning` holds model thinking (never sent back), `toolCalls` are the assistant's requests,
 * `toolCallId` links a tool result back to its call.
 */
data class Message(
    val role: Role,
    var content: String = "",
    var reasoning: String = "",
    val toolCalls: MutableList<ToolCall> = mutableListOf(),
    val toolCallId: String? = null,
    val toolName: String? = null,
    val id: String = UUID.randomUUID().toString(),
    val ts: Long = System.currentTimeMillis(),
    var streaming: Boolean = false,
    /** Marks a synthetic compaction summary so the UI can style it. */
    val isSummary: Boolean = false,
    /** Marks a message that has been folded into a summary and should not be sent. */
    var compacted: Boolean = false,
    /** Rough token count, cached. */
    var tokens: Int = 0,
) {
    fun estimateTokens(): Int {
        tokens = ContextManager.estimateTokens(content) + ContextManager.estimateTokens(reasoning) +
            toolCalls.sumOf { ContextManager.estimateTokens(it.arguments) + 8 } + 4
        return tokens
    }

    /** Wire format for the API. */
    fun toWire(): JSONObject {
        val o = JSONObject().put("role", role.name)
        when (role) {
            Role.tool -> { o.put("tool_call_id", toolCallId); o.put("content", content) }
            Role.assistant -> {
                o.put("content", content.ifEmpty { JSONObject.NULL })
                if (toolCalls.isNotEmpty()) o.put("tool_calls", JSONArray().apply { toolCalls.forEach { put(it.toJson()) } })
            }
            else -> o.put("content", content)
        }
        return o
    }

    fun toStorage(): JSONObject = JSONObject()
        .put("id", id).put("role", role.name).put("content", content).put("reasoning", reasoning)
        .put("toolCalls", JSONArray().apply { toolCalls.forEach { put(it.toJson()) } })
        .put("toolCallId", toolCallId ?: JSONObject.NULL).put("toolName", toolName ?: JSONObject.NULL)
        .put("ts", ts).put("isSummary", isSummary).put("compacted", compacted)

    companion object {
        fun fromStorage(o: JSONObject): Message {
            val calls = mutableListOf<ToolCall>()
            o.optJSONArray("toolCalls")?.let { arr -> for (i in 0 until arr.length()) calls += ToolCall.fromJson(arr.getJSONObject(i)) }
            return Message(
                role = Role.valueOf(o.getString("role")),
                content = o.optString("content", ""),
                reasoning = o.optString("reasoning", ""),
                toolCalls = calls,
                toolCallId = o.optString("toolCallId", "").ifEmpty { null },
                toolName = o.optString("toolName", "").ifEmpty { null },
                id = o.optString("id", UUID.randomUUID().toString()),
                ts = o.optLong("ts", 0L),
                isSummary = o.optBoolean("isSummary", false),
                compacted = o.optBoolean("compacted", false),
            )
        }
    }
}

data class Conversation(
    val id: String = UUID.randomUUID().toString(),
    var title: String = "New chat",
    val created: Long = System.currentTimeMillis(),
    var updated: Long = System.currentTimeMillis(),
    val messages: MutableList<Message> = mutableListOf(),
    /** Id of the long-horizon task this chat is driving, if any. */
    var taskId: String? = null,
)
