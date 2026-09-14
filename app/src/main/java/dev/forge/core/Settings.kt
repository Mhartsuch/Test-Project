package dev.forge.core

import android.content.Context
import android.content.SharedPreferences

class Settings(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("forge", Context.MODE_PRIVATE)

    var openRouterKey: String by str("openrouter_key", "")
    var model: String by str("model", "anthropic/claude-sonnet-4.5")
    var summaryModel: String by str("summary_model", "")          // blank = same as model
    var githubToken: String by str("github_token", "")
    var githubRepo: String by str("github_repo", "")               // owner/repo that holds Forge's own source
    var githubBranch: String by str("github_branch", "main")
    var maxContextTokens: Int by int("max_context_tokens", 120_000)
    var compactAtTokens: Int by int("compact_at_tokens", 90_000)
    var maxToolRounds: Int by int("max_tool_rounds", 200)
    var temperature: Float by flt("temperature", 0.3f)
    var reasoningEffort: String by str("reasoning_effort", "medium") // none|low|medium|high
    var autoApproveTools: Boolean by bool("auto_approve", true)
    var darkMode: String by str("dark_mode", "system")             // system|light|dark
    var userName: String by str("user_name", "")
    var lastConversationId: String by str("last_conv", "")

    val isConfigured get() = openRouterKey.isNotBlank()
    val effectiveSummaryModel get() = summaryModel.ifBlank { model }

    fun snapshot(): Map<String, Any> = mapOf(
        "model" to model, "summaryModel" to effectiveSummaryModel, "githubRepo" to githubRepo,
        "githubBranch" to githubBranch, "maxContextTokens" to maxContextTokens,
        "compactAtTokens" to compactAtTokens, "maxToolRounds" to maxToolRounds,
        "temperature" to temperature, "reasoningEffort" to reasoningEffort,
        "autoApproveTools" to autoApproveTools
    )

    private fun str(key: String, def: String) = object : kotlin.properties.ReadWriteProperty<Any?, String> {
        override fun getValue(thisRef: Any?, property: kotlin.reflect.KProperty<*>) = prefs.getString(key, def) ?: def
        override fun setValue(thisRef: Any?, property: kotlin.reflect.KProperty<*>, value: String) { prefs.edit().putString(key, value).apply() }
    }
    private fun int(key: String, def: Int) = object : kotlin.properties.ReadWriteProperty<Any?, Int> {
        override fun getValue(thisRef: Any?, property: kotlin.reflect.KProperty<*>) = prefs.getInt(key, def)
        override fun setValue(thisRef: Any?, property: kotlin.reflect.KProperty<*>, value: Int) { prefs.edit().putInt(key, value).apply() }
    }
    private fun flt(key: String, def: Float) = object : kotlin.properties.ReadWriteProperty<Any?, Float> {
        override fun getValue(thisRef: Any?, property: kotlin.reflect.KProperty<*>) = prefs.getFloat(key, def)
        override fun setValue(thisRef: Any?, property: kotlin.reflect.KProperty<*>, value: Float) { prefs.edit().putFloat(key, value).apply() }
    }
    private fun bool(key: String, def: Boolean) = object : kotlin.properties.ReadWriteProperty<Any?, Boolean> {
        override fun getValue(thisRef: Any?, property: kotlin.reflect.KProperty<*>) = prefs.getBoolean(key, def)
        override fun setValue(thisRef: Any?, property: kotlin.reflect.KProperty<*>, value: Boolean) { prefs.edit().putBoolean(key, value).apply() }
    }
}
