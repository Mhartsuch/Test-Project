package dev.forge.tools

import org.json.JSONObject

object SkillTools {
    fun all(): List<Tool> = listOf(write, reload, list, read)

    private val write = object : Tool("skill_write",
        "Create or update a hot-loadable skill. Provide SKILL.md (frontmatter: name, description, triggers; body = playbook the model follows) and optionally tool.js exporting functions declared with forge.declare(). Call skills_reload afterwards.",
        Schema.obj("name" to Schema.str("Skill folder name (kebab-case)"), "skill_md" to Schema.str("SKILL.md content"), "tool_js" to Schema.str("tool.js content (optional)"), required = listOf("name", "skill_md"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val name = args.getString("name").lowercase().replace(Regex("[^a-z0-9-]"), "-")
            ctx.app.skills.write(name, args.getString("skill_md"), args.optString("tool_js", "").ifEmpty { null })
            return "skill '$name' written. Run skills_reload to activate tools."
        }
    }
    private val reload = object : Tool("skills_reload", "Reload all skills and their JS tools. Returns the tool names now available and any JS load errors.", Schema.obj()) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            ctx.app.tools.reloadDynamic()
            val errs = ctx.app.jsRuntime.lastErrors
            return "tools: ${ctx.app.tools.names().joinToString(", ")}" + (if (errs.isNotEmpty()) "\nERRORS:\n" + errs.joinToString("\n") else "")
        }
    }
    private val list = object : Tool("skill_list", "List installed skills with descriptions.", Schema.obj()) {
        override suspend fun run(args: JSONObject, ctx: ToolContext) = ctx.app.skills.renderIndex().ifEmpty { "no skills" }
    }
    private val read = object : Tool("skill_read", "Read a skill's SKILL.md and tool.js.", Schema.obj("name" to Schema.str("Skill name"), required = listOf("name"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val s = ctx.app.skills.get(args.getString("name")) ?: return "not found"
            return "### SKILL.md\n${s.markdown}\n\n### tool.js\n${s.js ?: "(none)"}"
        }
    }
}
