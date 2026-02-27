# Puck Bot — Secrets Directory

This directory contains Docker Secret files for puck-bot. These files are
**never committed to version control** (gitignored).

## Required Secrets

| File | Description | Source |
|------|-------------|--------|
| `puck_fluxer_token` | Fluxer bot token | Fluxer Developer Portal |
| `twitch_client_id` | Twitch application Client ID | [Twitch Developer Console](https://dev.twitch.tv/console/apps) |
| `twitch_client_secret` | Twitch application Client Secret | [Twitch Developer Console](https://dev.twitch.tv/console/apps) |
| `youtube_api_key` | Google/YouTube Data API v3 key | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) |

## Setup

1. Create each file listed above in this directory
2. Paste the raw secret value (no quotes, no newline at end)
3. Set permissions: `chmod 600 *` (on the server)

## Security

- These files are referenced by `docker-compose.yml` and mounted at `/run/secrets/`
- The bot reads them via the `load_secret()` pattern
- Never commit these files — only this README is tracked

---

**Built with care for chosen family** 🏳️‍🌈
