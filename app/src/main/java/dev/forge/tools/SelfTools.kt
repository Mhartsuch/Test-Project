package dev.forge.tools

import org.json.JSONObject

/** Tier-2 self-evolution tools: sync source, see diff, push, watch the build, install. */
object SelfTools {
    fun all(): List<Tool> = listOf(sync, changes, push, status, install, revert)

    private val sync = object : Tool("self_sync_source", "Download Forge's own source (configured GitHub repo/branch) into forge-src, replacing local files. Do this before a Tier-2 change if forge-src is empty or stale.", Schema.obj()) {
        override val needsApproval = true
        override suspend fun run(args: JSONObject, ctx: ToolContext) = ctx.app.github.syncSource(ctx.app.paths.selfSource)
    }
    private val changes = object : Tool("self_changes", "List files in forge-src that differ from the last sync/push.", Schema.obj()) {
        override suspend fun run(args: JSONObject, ctx: ToolContext) = ctx.app.github.changes(ctx.app.paths.selfSource).let { if (it.isEmpty) "no local changes" else it.toString() }
    }
    private val push = object : Tool("self_commit_and_push", "Commit every local change in forge-src and push to GitHub, which triggers the APK build. Bump the version in app/build.gradle.kts first.",
        Schema.obj("message" to Schema.str("Commit message"), required = listOf("message"))) {
        override val needsApproval = true
        override suspend fun run(args: JSONObject, ctx: ToolContext) = ctx.app.github.commitAndPush(ctx.app.paths.selfSource, args.getString("message"))
    }
    private val status = object : Tool("self_build_status", "Status of the latest GitHub Actions build for the branch. With log=true and a failed build, returns the key error lines.",
        Schema.obj("log" to Schema.bool("Include failure log"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val b = ctx.app.github.latestBuild() ?: return "no builds yet"
            val head = "run ${b.id}: status=${b.status} conclusion=${b.conclusion ?: "-"} sha=${b.sha.take(7)} \"${b.message.lines().first()}\"\n${b.url}"
            return if (args.optBoolean("log") && b.conclusion == "failure") head + "\n\n" + ctx.app.github.failedJobLog(b.id) else head
        }
    }
    private val install = object : Tool("self_install_update", "Download the newest release APK built by CI and open the Android installer. Only after self_build_status shows success.", Schema.obj()) {
        override val needsApproval = true
        override suspend fun run(args: JSONObject, ctx: ToolContext) = ctx.app.updater.installLatest()
    }
    private val revert = object : Tool("self_revert_file", "Discard local edits to one forge-src file by re-downloading it from the branch.",
        Schema.obj("path" to Schema.str("Path relative to forge-src"), required = listOf("path"))) {
        override suspend fun run(args: JSONObject, ctx: ToolContext): String {
            val s = ctx.app.settings; val rel = args.getString("path")
            val url = "https://raw.githubusercontent.com/${s.githubRepo}/${s.githubBranch}/$rel"
            val r = ctx.app.tools.get("http")!!.run(JSONObject().put("url", url).put("headers", JSONObject().put("Authorization", "Bearer ${s.githubToken}").toString()).put("save_to", java.io.File(ctx.app.paths.selfSource, rel).path), ctx)
            return "reverted $rel: $r"
        }
    }
}
