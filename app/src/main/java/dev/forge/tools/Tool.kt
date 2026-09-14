package dev.forge.tools

import dev.forge.ForgeApp
import dev.forge.core.Conversation
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

class ToolContext(val app: ForgeApp, val conversation: Conversation, val progress: suspend (String) -> Unit = {})

/** A callable tool. `parameters` is a JSON-schema object. */
abstract class Tool(val name: String, val description: String, val parameters: JSONObject) {
    abstract suspend fun run(args: JSONObject, ctx: ToolContext): String
    /** Tools that change state outside the sandbox can require approval when auto-approve is off. */
    open val needsApproval: Boolean = false

    fun schema(): JSONObject = JSONObject().put("type", "function").put("function",
        JSONObject().put("name", name).put("description", description).put("parameters", parameters))
}

/** Tiny JSON-schema builder. */
object Schema {
    fun obj(vararg props: Pair<String, JSONObject>, required: List<String> = emptyList()): JSONObject {
        val p = JSONObject(); props.forEach { p.put(it.first, it.second) }
        return JSONObject().put("type", "object").put("properties", p).put("required", JSONArray(required))
    }
    fun str(desc: String, enum: List<String>? = null) = JSONObject().put("type", "string").put("description", desc).also { o -> enum?.let { o.put("enum", JSONArray(it)) } }
    fun int(desc: String) = JSONObject().put("type", "integer").put("description", desc)
    fun bool(desc: String) = JSONObject().put("type", "boolean").put("description", desc)
    fun arr(desc: String, items: JSONObject = JSONObject().put("type", "string")) = JSONObject().put("type", "array").put("description", desc).put("items", items)
}

/** Path sandbox: Forge may read most of the device but only writes under its own root. */
object Sandbox {
    fun resolve(app: ForgeApp, path: String): File {
        val f = if (path.startsWith("/")) File(path) else File(app.paths.workspace, path)
        return f.absoluteFile.normalize()
    }
    fun assertWritable(app: ForgeApp, f: File) {
        val root = app.paths.root.canonicalPath
        val c = runCatching { f.canonicalPath }.getOrElse { f.absolutePath }
        require(c.startsWith(root)) { "Write denied: $c is outside Forge root ($root). Copy it into the workspace first." }
    }
}

class ToolRegistry(private val app: ForgeApp) {
    private val builtin = mutableListOf<Tool>()
    private var dynamic: List<Tool> = emptyList()

    init {
        builtin += FileTools.all()
        builtin += ShellTools.all()
        builtin += MemoryTools.all()
        builtin += SkillTools.all()
        builtin += SelfTools.all()
        builtin += AndroidTools.all()
        reloadDynamic()
    }

    fun reloadDynamic() { dynamic = app.jsRuntime.loadSkills(app.skills) }
    fun setDynamic(tools: List<Tool>) { dynamic = tools }

    fun all(): List<Tool> = builtin + dynamic
    fun get(name: String): Tool? = all().firstOrNull { it.name == name }
    fun schemas(): JSONArray = JSONArray().apply { all().forEach { put(it.schema()) } }
    fun names(): List<String> = all().map { it.name }
}
