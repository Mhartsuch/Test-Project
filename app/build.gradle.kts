plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

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

    // A stable self-signed key checked into the repo so that self-updates built on CI install
    // over the previous version. Personal-use key only; replace it (and the passwords) if you ever distribute.
    signingConfigs {
        create("forge") {
            storeFile = file("forge.jks")
            storePassword = "forgeforge"
            keyAlias = "forge"
            keyPassword = "forgeforge"
        }
    }
    buildTypes {
        debug { signingConfig = signingConfigs.getByName("forge") }
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("forge")
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
