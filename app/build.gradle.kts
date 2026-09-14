import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// --- Signing credentials -------------------------------------------------------------
// keystore.properties (gitignored) is the local-build source; environment variables win
// so CI can inject GitHub secrets without a file on disk.
val keystoreProperties = Properties().apply {
    val f = rootProject.file("keystore.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

fun signingCredential(env: String, property: String): String? =
    System.getenv(env)?.takeIf { it.isNotBlank() } ?: keystoreProperties.getProperty(property)

val forgeKeystore = file(signingCredential("FORGE_KEYSTORE_FILE", "storeFile") ?: "forge.jks")
val forgeStorePassword = signingCredential("FORGE_KEYSTORE_PASSWORD", "storePassword")
val forgeKeyAlias = signingCredential("FORGE_KEY_ALIAS", "keyAlias") ?: "forge"
val forgeKeyPassword = signingCredential("FORGE_KEY_PASSWORD", "keyPassword") ?: forgeStorePassword
val forgeSigningAvailable = forgeStorePassword != null && forgeKeystore.exists()

android {
    namespace = "dev.forge"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.forge"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        // FORGE_VERSION is read at runtime to detect self-updates
        buildConfigField("String", "FORGE_VERSION", "\"0.1.0\"")
        buildConfigField("String", "BUILD_TIME", "\"${System.currentTimeMillis()}\"")
    }

    // Signing credentials are never stored in the repo. They are resolved, in order, from
    // environment variables (CI reads them from GitHub secrets) or from a gitignored
    // keystore.properties in the project root for local builds. See SIGNING.md.
    // Falls back to the debug key if nothing is configured, so a fresh clone still builds;
    // CI fails loudly instead, because a debug-signed release cannot self-update.
    signingConfigs {
        if (forgeSigningAvailable) {
            create("forge") {
                storeFile = forgeKeystore
                storePassword = forgeStorePassword
                keyAlias = forgeKeyAlias
                keyPassword = forgeKeyPassword
            }
        }
    }
    val forgeSigning = signingConfigs.findByName("forge")
    if (forgeSigning == null) {
        logger.warn(
            "Forge: no signing credentials found (FORGE_KEYSTORE_PASSWORD / keystore.properties); " +
                "signing with the debug key. Such a build cannot install over a release build."
        )
    }
    buildTypes {
        debug { forgeSigning?.let { signingConfig = it } }
        release {
            isMinifyEnabled = false
            signingConfig = forgeSigning ?: signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.navigation:navigation-compose:2.8.5")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
