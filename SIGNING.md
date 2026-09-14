# Signing

Forge installs its own updates, so every build must be signed with the **same** key — an APK
signed with a different key cannot install over the previous one. That key is therefore stable,
but it is not stored in this repository.

Credentials are resolved in this order:

1. Environment variables — how CI passes GitHub secrets in.
2. `keystore.properties` in the repo root — for local builds. It is gitignored.

| Variable | `keystore.properties` key | Default |
|---|---|---|
| `FORGE_KEYSTORE_FILE` | `storeFile` | `app/forge.jks` |
| `FORGE_KEYSTORE_PASSWORD` | `storePassword` | — (required) |
| `FORGE_KEY_ALIAS` | `keyAlias` | `forge` |
| `FORGE_KEY_PASSWORD` | `keyPassword` | same as the store password |

If nothing is configured, `assembleRelease` falls back to the debug key and logs a warning, so a
fresh clone still builds. CI does not allow that fallback: it fails if the secrets are missing,
because a debug-signed release would silently break self-updates.

## Setting up CI

Add two repository secrets under **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `FORGE_KEYSTORE_BASE64` | the keystore, base64-encoded on a single line |
| `FORGE_KEYSTORE_PASSWORD` | the keystore password |

`FORGE_KEY_ALIAS` is optional and defaults to `forge`.

The workflow decodes the keystore into the runner's temp directory, builds, and deletes it again.
Secrets are masked in logs, and GitHub does not expose them to workflow runs from forks.

## Generating a key

```sh
keytool -genkeypair -v \
  -keystore forge.jks -storetype PKCS12 \
  -alias forge -keyalg RSA -keysize 4096 -validity 10000 \
  -dname "CN=Forge, OU=Personal, O=Forge, L=Unknown, ST=Unknown, C=US" \
  -storepass "$(openssl rand -base64 30)"   # print it and save it first
```

Then, for the `FORGE_KEYSTORE_BASE64` secret:

```sh
base64 -w0 forge.jks    # macOS: base64 -i forge.jks
```

Keep `forge.jks` and its password somewhere durable and outside the repo. Losing them means the
next build cannot install over an existing Forge — you would have to uninstall the app first.

## Local builds

```sh
cat > keystore.properties <<'PROPS'
storeFile=/absolute/path/to/forge.jks
storePassword=…
keyAlias=forge
keyPassword=…
PROPS
./gradlew assembleRelease
```

## Rotating the key

Generate a new keystore, replace both secrets, and **uninstall Forge from the phone** before
installing the next build — Android refuses an update signed by a different key.
