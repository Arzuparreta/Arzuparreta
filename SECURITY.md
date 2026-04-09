# Security

## Access tokens (Expo / EAS)

- **Never** commit `EXPO_TOKEN`, API keys, or keystore passwords to git.
- Store **`EXPO_TOKEN`** only as a GitHub Actions **secret** (Repository → *Settings* → *Secrets and variables* → *Actions*).
- If a token was pasted in chat, a ticket, or committed by mistake: **revoke it immediately** in [Expo access tokens](https://expo.dev) and create a **new** token.

## GitHub Releases

Preview APKs attached to Releases are **public** for public repositories. Treat them as test builds, not a substitute for Play-signed distribution if you need confidentiality.
