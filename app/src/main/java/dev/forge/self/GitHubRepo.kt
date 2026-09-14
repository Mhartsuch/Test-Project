package dev.forge.self

import android.util.Base64
import dev.forge.ForgeApp
import dev.forge.core.Settings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import java.util.zip.ZipInputStream

/**
 * Git without a git binary: Forge's own source is synced from GitHub as a zipball and pushed back
 * through the Git Data API (blobs → tree → commit → ref). GitHub Actions then builds the APK.
 */
class GitHubRepo(private val settings: Settings) {
    private val http = OkHttpClient.Builder().connectTimeout(30, TimeUnit.SECONDS).readTimeout(3, TimeUnit.MINUTES).followRedirects(true).build()
    private val JSON = "application/json".toMediaType()

    val isConfigured get() = settings.githubToken.isNotBlank() && settings.githubRepo.contains("/")
    private val repo get() = settings.githubRepo.trim().removePrefix("https://github.com/").removeSuffix(".git")
    private val branch get() = settings.githubBranch.ifBlank { "main" }

    private fun req(path: String, accept: String = "application/vnd.github+json") = Request.Builder()
        .url(if (path.startsWith("http")) path else "https://api.github.com/repos/$repo$path")
        .header("Authorization", "Bearer ${settings.githubToken}").header("Accept", accept)
        .header("X-GitHub-Api-Version", "2022-11-28").header("User-Agent", "Forge-Android")

    private fun call(b: Request.Builder): JSONObject = http.newCall(b.build()).execute().use { r ->
        val text = r.body?.string().orEmpty()
        if (!r.isSuccessful) throw IOException("GitHub ${r.code} ${b.build().url.encodedPath}: ${text.take(400)}")
        if (text.trim().startsWith("[")) JSONObject().put("array", JSONArray(text)) else JSONObject(text.ifBlank { "{}" })
    }

    private fun manifestFile(src: File) = File(src.parentFile, ".forge-src-manifest.json")

    /** Git blob sha1 for change detection. */
    private fun blobSha(bytes: ByteArray): String {
        val md = MessageDigest.getInstance("SHA-1")
        md.update("blob ${bytes.size}\u0000".toByteArray()); md.update(bytes)
        return md.digest().joinToString("") { "%02x".format(it) }
    }

    private fun sourceFiles(src: File): List<File> = src.walkTopDown()
        .onEnter { it.name !in setOf(".git", "build", ".gradle", ".idea") }
        .filter { it.isFile && it.name != ".forge-src-manifest.json" }.toList()

    /** Download the branch zipball into `src` (replacing it) and record the manifest. */
    suspend fun syncSource(src: File): String = withContext(Dispatchers.IO) {
        check(isConfigured) { "GitHub not configured (Settings → Self-evolution)" }
        val head = call(req("/branches/$branch")).getJSONObject("commit").getString("sha")
        val zip = File(src.parentFile, "forge-src.zip")
        http.newCall(req("/zipball/$branch").get().build()).execute().use { r ->
            if (!r.isSuccessful) throw IOException("zipball ${r.code}")
            zip.outputStream().use { r.body!!.byteStream().copyTo(it) }
        }
        src.deleteRecursively(); src.mkdirs()
        var n = 0
        ZipInputStream(zip.inputStream().buffered()).use { zin ->
            var e = zin.nextEntry
            while (e != null) {
                val rel = e.name.substringAfter('/', "")  // strip "<owner>-<repo>-<sha>/"
                if (rel.isNotEmpty() && !e.isDirectory) {
                    val out = File(src, rel).normalize(); require(out.path.startsWith(src.path))
                    out.parentFile?.mkdirs(); out.outputStream().use { zin.copyTo(it) }; n++
                }
                e = zin.nextEntry
            }
        }
        zip.delete()
        val manifest = JSONObject().put("head", head).put("files", JSONObject().apply { sourceFiles(src).forEach { put(it.relativeTo(src).path, blobSha(it.readBytes())) } })
        manifestFile(src).writeText(manifest.toString())
        "synced $n files from $repo@$branch ($head)"
    }

    data class Changes(val modified: List<String>, val added: List<String>, val deleted: List<String>) {
        val isEmpty get() = modified.isEmpty() && added.isEmpty() && deleted.isEmpty()
        override fun toString() = "modified: $modified\nadded: $added\ndeleted: $deleted"
    }

    fun changes(src: File): Changes {
        val mf = manifestFile(src).takeIf { it.exists() }?.let { JSONObject(it.readText()) } ?: return Changes(emptyList(), sourceFiles(src).map { it.relativeTo(src).path }, emptyList())
        val known = mf.getJSONObject("files")
        val current = sourceFiles(src).associate { it.relativeTo(src).path to blobSha(it.readBytes()) }
        val modified = current.filter { known.has(it.key) && known.getString(it.key) != it.value }.keys.toList()
        val added = current.filter { !known.has(it.key) }.keys.toList()
        val deleted = known.keys().asSequence().filter { !current.containsKey(it) }.toList()
        return Changes(modified, added, deleted)
    }

    /** Commit all local changes on top of the remote head and move the branch ref. */
    suspend fun commitAndPush(src: File, message: String): String = withContext(Dispatchers.IO) {
        check(isConfigured) { "GitHub not configured" }
        val ch = changes(src)
        if (ch.isEmpty) return@withContext "nothing to commit"
        val head = call(req("/git/ref/heads/$branch")).getJSONObject("object").getString("sha")
        val baseTree = call(req("/git/commits/$head")).getJSONObject("tree").getString("sha")
        val tree = JSONArray()
        for (rel in ch.modified + ch.added) {
            val f = File(src, rel)
            val blob = call(req("/git/blobs").post(JSONObject().put("content", Base64.encodeToString(f.readBytes(), Base64.NO_WRAP)).put("encoding", "base64").toString().toRequestBody(JSON)))
            val mode = if (rel == "gradlew" || f.canExecute()) "100755" else "100644"
            tree.put(JSONObject().put("path", rel).put("mode", mode).put("type", "blob").put("sha", blob.getString("sha")))
        }
        for (rel in ch.deleted) tree.put(JSONObject().put("path", rel).put("mode", "100644").put("type", "blob").put("sha", JSONObject.NULL))
        val newTree = call(req("/git/trees").post(JSONObject().put("base_tree", baseTree).put("tree", tree).toString().toRequestBody(JSON))).getString("sha")
        val commit = call(req("/git/commits").post(JSONObject().put("message", message).put("tree", newTree).put("parents", JSONArray().put(head)).toString().toRequestBody(JSON))).getString("sha")
        call(req("/git/refs/heads/$branch").patch(JSONObject().put("sha", commit).put("force", false).toString().toRequestBody(JSON)))
        // refresh manifest
        val manifest = JSONObject().put("head", commit).put("files", JSONObject().apply { sourceFiles(src).forEach { put(it.relativeTo(src).path, blobSha(it.readBytes())) } })
        manifestFile(src).writeText(manifest.toString())
        "pushed $commit to $repo@$branch (${ch.modified.size} modified, ${ch.added.size} added, ${ch.deleted.size} deleted). GitHub Actions is building."
    }

    data class Build(val id: Long, val status: String, val conclusion: String?, val sha: String, val url: String, val message: String)

    suspend fun latestBuild(): Build? = withContext(Dispatchers.IO) {
        val runs = call(req("/actions/runs?branch=$branch&per_page=1")).getJSONArray("workflow_runs")
        if (runs.length() == 0) return@withContext null
        val r = runs.getJSONObject(0)
        Build(r.getLong("id"), r.getString("status"), r.optString("conclusion", "").ifEmpty { null }, r.getString("head_sha"), r.getString("html_url"), r.optJSONObject("head_commit")?.optString("message") ?: "")
    }

    suspend fun failedJobLog(runId: Long, tailChars: Int = 12_000): String = withContext(Dispatchers.IO) {
        val jobs = call(req("/actions/runs/$runId/jobs")).getJSONArray("jobs")
        val failed = (0 until jobs.length()).map { jobs.getJSONObject(it) }.firstOrNull { it.optString("conclusion") == "failure" } ?: return@withContext "(no failed job found)"
        http.newCall(req("/actions/jobs/${failed.getLong("id")}/logs").get().build()).execute().use { r ->
            val text = r.body?.string().orEmpty()
            // keep the lines that matter for Kotlin/Gradle failures
            val interesting = text.lines().filter { l -> listOf("e: ", "error:", "FAILED", "What went wrong", "Unresolved", "Exception", "Caused by").any { l.contains(it) } }
            (if (interesting.isNotEmpty()) "Key lines:\n" + interesting.joinToString("\n").take(tailChars) + "\n\n" else "") + "Tail:\n" + text.takeLast(tailChars / 2)
        }
    }

    data class Release(val tag: String, val apkName: String, val apkUrl: String, val apiAssetUrl: String)

    suspend fun latestRelease(): Release? = withContext(Dispatchers.IO) {
        val rel = runCatching { call(req("/releases/latest")) }.getOrNull() ?: return@withContext null
        val assets = rel.getJSONArray("assets")
        val apk = (0 until assets.length()).map { assets.getJSONObject(it) }.firstOrNull { it.getString("name").endsWith(".apk") } ?: return@withContext null
        Release(rel.getString("tag_name"), apk.getString("name"), apk.getString("browser_download_url"), apk.getString("url"))
    }

    suspend fun downloadAsset(apiAssetUrl: String, dest: File) = withContext(Dispatchers.IO) {
        http.newCall(req(apiAssetUrl, accept = "application/octet-stream").get().build()).execute().use { r ->
            if (!r.isSuccessful) throw IOException("asset ${r.code}")
            dest.outputStream().use { r.body!!.byteStream().copyTo(it) }
        }
    }
}
