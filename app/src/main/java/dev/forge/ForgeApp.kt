package dev.forge

import android.app.Application
import dev.forge.core.Agent
import dev.forge.core.OpenRouterClient
import dev.forge.core.Settings
import dev.forge.memory.ConversationStore
import dev.forge.memory.MemoryFiles
import dev.forge.memory.TaskBoard
import dev.forge.self.GitHubRepo
import dev.forge.self.SelfUpdater
import dev.forge.self.SkillStore
import dev.forge.tools.JsToolRuntime
import dev.forge.tools.ToolRegistry
import java.io.File

/**
 * Process-wide singletons. Forge deliberately avoids a DI framework so that the
 * agent can reason about (and modify) the wiring in one file.
 */
class ForgeApp : Application() {

    lateinit var paths: Paths; private set
    lateinit var settings: Settings; private set
    lateinit var memory: MemoryFiles; private set
    lateinit var tasks: TaskBoard; private set
    lateinit var conversations: ConversationStore; private set
    lateinit var skills: SkillStore; private set
    lateinit var github: GitHubRepo; private set
    lateinit var updater: SelfUpdater; private set
    lateinit var jsRuntime: JsToolRuntime; private set
    lateinit var tools: ToolRegistry; private set
    lateinit var client: OpenRouterClient; private set
    lateinit var agent: Agent; private set

    override fun onCreate() {
        super.onCreate()
        instance = this
        paths = Paths(filesDir).also { it.ensure() }
        settings = Settings(this)
        memory = MemoryFiles(paths.memory)
        tasks = TaskBoard(paths.tasks)
        conversations = ConversationStore(paths.conversations)
        skills = SkillStore(paths.skills)
        github = GitHubRepo(settings)
        updater = SelfUpdater(this, settings, github)
        jsRuntime = JsToolRuntime(this)
        client = OpenRouterClient(settings)
        tools = ToolRegistry(this)
        agent = Agent(this)
        memory.bootstrapIfEmpty()
        skills.bootstrapIfEmpty()
    }

    /** Every on-disk location Forge owns. The agent is allowed to write anywhere under [root]. */
    class Paths(val root: File) {
        val workspace = File(root, "workspace")        // user projects + a clone of Forge's own source
        val selfSource = File(workspace, "forge-src")  // Forge's own Kotlin source, edited by the agent
        val memory = File(root, "memory")              // markdown memory files (profile.md, areas/, topics/ ...)
        val skills = File(root, "skills")              // SKILL.md + optional tool.js hot-loaded tools
        val tasks = File(root, "tasks")                // long-horizon task board (json)
        val conversations = File(root, "conversations")// jsonl transcripts
        val logs = File(root, "logs")
        val downloads = File(root, "downloads")        // self-update APKs land here
        fun ensure() = listOf(workspace, selfSource, memory, skills, tasks, conversations, logs, downloads).forEach { it.mkdirs() }
    }

    companion object {
        lateinit var instance: ForgeApp; private set
    }
}
