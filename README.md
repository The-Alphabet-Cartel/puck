<p align="center">
  <img src="images/Puck-PFP.png" alt="Puck" width="200" />
</p>

# Puck

Stream monitor bot for [The Alphabet Cartel](https://fluxer.gg/yGJfJH5C)'s Fluxer community.

Part of the [Bragi](https://github.com/the-alphabet-cartel/bragi) bot infrastructure.

---

## What Puck Does

Named for Shakespeare's mischievous fairy herald from *A Midsummer Night's Dream*, Puck watches community members' Twitch and YouTube live channels. When a member goes live, Puck adds a configurable "Live" role to highlight them in the member list. When their stream ends, the role is removed automatically.

**Twitch** streams are checked every polling cycle (default 90 seconds) via the Helix API, with batch queries supporting up to 100 users per request.

**YouTube** streams use a quota-conscious two-stage approach: a free RSS pre-check filters out inactive channels before spending YouTube Data API v3 quota on live detection. YouTube is polled less frequently (default every ~4.5 minutes) to conserve the 10,000 unit daily quota.

**Restart resilient.** Puck persists stream state to disk. On startup, it reconciles persisted state against live API data — cleaning up stale "Live" roles if a stream ended while the bot was down, and adding missing roles if a stream started.

---

## How It Works

1. Puck starts up and authenticates with Twitch (OAuth client credentials) and YouTube (API key)
2. A background polling loop runs on a configurable interval
3. Each cycle:
   - **Twitch:** Batch query all tracked usernames via `GET /helix/streams`
   - **YouTube:** RSS pre-check each channel → only call the API if recent activity detected
4. Compare results against previous state
5. For each state transition:
   - **WENT LIVE** → `member.add_role(live_role_id)` on Fluxer
   - **WENT OFFLINE** → `member.remove_role(live_role_id)` on Fluxer
6. Persist updated state to `/app/data/stream_state.json`

### YouTube Quota Strategy

YouTube Data API v3 has a hard limit of 10,000 quota units per day, and each `search.list` call costs 100 units. Puck conserves quota through:

- **RSS pre-check:** Before every API call, Puck checks the channel's free RSS feed. If no video was published in the last 24 hours, the API call is skipped entirely.
- **Poll multiplier:** YouTube is checked every N × base interval (default 3×, so every ~4.5 minutes instead of every 90 seconds).
- **Safety valve:** If a 403 quota-exhausted response is received, Puck automatically falls back to RSS-only mode for the rest of the day.

---

## Future Enhancements

Puck v1.0 focuses on role toggling. The architecture includes hooks for future features:

- **v1.1 — Stream Embeds:** Post an embedded announcement with stream title, game, thumbnail, and channel URL to a configurable channel when a member goes live. Auto-update the thumbnail every 5 minutes. Auto-delete when the stream ends.
- **v1.2 — Bot Commands:** `!addstream`, `!removestream`, `!streams` for managing tracked users at runtime.
- **v1.3 — Additional Platforms:** Kick.com and other streaming platforms as requested.

---

## Configuration

Puck uses the Bragi three-layer config stack:

```
puck_config.json      ← structural defaults (committed)
      ↓
.env                  ← runtime overrides (not committed)
      ↓
Docker Secrets        ← sensitive values (never in source)
```

### Environment Variables

Copy `.env.template` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `PUCK_LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `PUCK_LOG_FORMAT` | `human` | `human` (colorized) or `json` (structured) |
| `PUCK_LOG_CONSOLE` | `true` | Enable console logging |
| `PUCK_LOG_FILE` | — | Optional log file path |
| `PUCK_COMMAND_PREFIX` | `!` | Command prefix (future use) |
| `PUCK_GUILD_ID` | — | Fluxer guild ID (**required**) |
| `PUCK_LIVE_ROLE_ID` | — | Role ID to assign when live (**required**) |
| `PUCK_ANNOUNCE_CHANNEL_ID` | — | Announcement channel (future v1.1) |
| `PUCK_POLL_INTERVAL` | `90` | Seconds between Twitch poll cycles (30–300) |
| `PUCK_YOUTUBE_POLL_MULTIPLIER` | `3` | YouTube polls every N × poll interval (1–10) |
| `PUID` | `1000` | Container user ID |
| `PGID` | `1000` | Container group ID |

### Docker Secrets

| Secret | File | Description |
|--------|------|-------------|
| `puck_token` | `secrets/puck_fluxer_token` | Fluxer bot token |
| `twitch_client_id` | `secrets/twitch_client_id` | Twitch application Client ID |
| `twitch_client_secret` | `secrets/twitch_client_secret` | Twitch application Client Secret |
| `youtube_api_key` | `secrets/youtube_api_key` | YouTube Data API v3 key |

See [`secrets/README.md`](secrets/README.md) for step-by-step instructions on obtaining each credential.

### Tracked Streams

The list of monitored streams is maintained in `src/config/tracked_streams.json`:

```json
{
  "streams": [
    {
      "fluxer_user_id": "1234567890",
      "display_name": "ExampleUser",
      "twitch_username": "exampleuser",
      "youtube_channel_id": null
    },
    {
      "fluxer_user_id": "0987654321",
      "display_name": "AnotherUser",
      "twitch_username": null,
      "youtube_channel_id": "UC_XXXXXXXXXXXXX"
    }
  ]
}
```

Each entry maps a Fluxer user to their streaming platform accounts. Users can have Twitch, YouTube, or both. Set the unused platform to `null`.

---

## Deployment

### Prerequisites

- Docker Engine 29.x + Compose v5
- A Fluxer bot application with a token
- A Twitch Developer application ([setup guide](secrets/README.md))
- A Google Cloud project with YouTube Data API v3 enabled ([setup guide](secrets/README.md))
- The `bragi` Docker network: `docker network create bragi`
- Host directories created:
  ```
  mkdir -p /opt/bragi/bots/puck-bot/logs
  mkdir -p /opt/bragi/bots/puck-bot/data
  ```

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/the-alphabet-cartel/puck.git
cd puck

# 2. Copy and configure environment
cp .env.template .env
# Edit .env — set PUCK_GUILD_ID and PUCK_LIVE_ROLE_ID at minimum

# 3. Create secrets (see secrets/README.md for detailed instructions)
mkdir -p secrets
printf 'your-fluxer-token' > secrets/puck_fluxer_token
printf 'your-twitch-client-id' > secrets/twitch_client_id
printf 'your-twitch-client-secret' > secrets/twitch_client_secret
printf 'your-youtube-api-key' > secrets/youtube_api_key
chmod 600 secrets/*

# 4. Edit tracked streams
# Edit src/config/tracked_streams.json with your community members

# 5. Deploy
docker compose up -d
```

### Fluxer Bot Permissions

| Permission | Why |
|------------|-----|
| View Channels | Receive gateway events |
| Manage Roles | Add/remove the Live role |
| Send Messages | Future: post stream announcements |

The bot's role must be positioned **above** the Live role in the Fluxer role hierarchy, or role operations will fail with `Forbidden`.

---

## Project Structure

```
puck/
├── docker-compose.yml            ← Container orchestration
├── Dockerfile                    ← Multi-stage build (Rule #10)
├── docker-entrypoint.py          ← PUID/PGID + tini (Rule #12)
├── .env.template                 ← Config reference (committed)
├── requirements.txt              ← fluxer-py + httpx
├── images/
│   └── Puck-PFP.png             ← Bot profile picture
├── docs/
│   └── planning.md              ← Design spec and roadmap
├── secrets/
│   └── README.md                 ← Credential setup guide (committed)
└── src/
    ├── main.py                   ← Entry point, boot sequence, polling task
    ├── config/
    │   ├── puck_config.json      ← JSON defaults (Rule #4)
    │   └── tracked_streams.json  ← Stream-to-user mappings
    ├── handlers/
    │   ├── stream_monitor.py     ← Polling loop + role toggle logic
    │   └── embed_announcer.py    ← Stub for v1.1 stream embeds
    ├── managers/
    │   ├── config_manager.py     ← Three-layer config (Rule #7)
    │   ├── logging_config_manager.py  ← Colorized logging (Rule #9)
    │   ├── twitch_manager.py     ← Twitch Helix API + OAuth
    │   ├── youtube_manager.py    ← YouTube API + RSS pre-check
    │   └── stream_state_manager.py    ← Persistent state + transitions
    └── models/
        └── stream_status.py      ← StreamStatus dataclass
```

---

## Charter Compliance

| Rule | Status |
|------|--------|
| #1 Factory Functions | ✅ All managers and handlers use `create_*()` |
| #2 Dependency Injection | ✅ All managers accept deps via constructor |
| #3 Additive Development | ✅ v1.1 hooks designed without removing v1.0 function |
| #4 JSON Config + Secrets | ✅ Three-layer stack |
| #5 Resilient Validation | ✅ Fallbacks with logging, graceful quota exhaustion |
| #6 File Versioning | ✅ All files versioned |
| #7 Config Hygiene | ✅ Secrets/env/JSON separated |
| #8 Real-World Testing | ✅ Designed for live Fluxer + Twitch + YouTube testing |
| #9 LoggingConfigManager | ✅ Standard colorization |
| #10 Python 3.12 + Venv | ✅ Multi-stage Docker build |
| #11 File System Tools | ✅ |
| #12 Python Entrypoint + tini | ✅ PUID/PGID support |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| [fluxer-py](https://github.com/akarealemil/fluxer.py) | Fluxer bot library |
| [httpx](https://www.python-httpx.org/) | HTTP client for Twitch/YouTube APIs |

---

## Naming

Puck is the mischievous fairy herald from Shakespeare's *A Midsummer Night's Dream* — announcing who's "on stage" in the community. Pairs with [Portia](https://github.com/the-alphabet-cartel/portia) (voice channel manager, from *The Merchant of Venice*) and [Prism](https://github.com/the-alphabet-cartel/prism) (welcome bot) in the Bragi bot family.

---

**Built with care for chosen family** 🏳️‍🌈
