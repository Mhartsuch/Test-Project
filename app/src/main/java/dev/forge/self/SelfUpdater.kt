package dev.forge.self

import android.content.Intent
import android.net.Uri
import android.provider.Settings as AndroidSettings
import androidx.core.content.FileProvider
import dev.forge.BuildConfig
import dev.forge.ForgeApp
import dev.forge.core.Settings
import java.io.File

/** Downloads the newest CI-built APK and hands it to the system package installer. */
class SelfUpdater(private val app: ForgeApp, private val settings: Settings, private val github: GitHubRepo) {

    suspend fun installLatest(): String {
        val rel = github.latestRelease() ?: return "No release with an APK found yet. Check self_build_status."
        val apk = File(app.paths.downloads, rel.apkName)
        github.downloadAsset(rel.apiAssetUrl, apk)
        if (!app.packageManager.canRequestPackageInstalls()) {
            app.startActivity(Intent(AndroidSettings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${app.packageName}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return "Downloaded ${rel.tag} (${apk.length() / 1024} KB) but Forge isn't allowed to install apps yet. I opened the setting — enable 'Allow from this source', then call self_install_update again."
        }
        val uri = FileProvider.getUriForFile(app, "${app.packageName}.fileprovider", apk)
        app.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION))
        return "Installer opened for ${rel.tag} (current ${BuildConfig.FORGE_VERSION}). After it finishes, reopen Forge."
    }
}
