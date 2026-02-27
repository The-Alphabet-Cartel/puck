---
title: "Puck - Planning"
description: "Planning for Puck stream monitor bot"
category: Planning
tags:
  - planning
  - puck
  - stream-monitor
  - twitch
  - youtube
author: "PapaBearDoes"
version: "v1.0.0"
last_updated: "2026-02-26"
---
# Puck: Planning

============================================================================
**Puck**: Stream monitor bot — detects Twitch/YouTube live streams and toggles
a configurable "Live" role on Fluxer for community members who are streaming.
**Community**: [The Alphabet Cartel](https://fluxer.gg/yGJfJH5C) | [alphabetcartel.net](https://alphabetcartel.org)
============================================================================

**Document Version**: v1.0.0
**Created**: 2026-02-26
**Phase**: Code Complete
**Status**: ✅ Code Complete — Ready for Docker Build & Test
**Last Updated**: 2026-02-26

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Current State](#2-current-state)
3. [Architecture Decisions](#3-architecture-decisions)
4. [Configuration Design](#4-configuration-design)
5. [File Structure](#5-file-structure)
6. [Core Flow](#6-core-flow)
7. [YouTube Quota Strategy](#7-youtube-quota-strategy)
8. [Future Enhancements](#8-future-enhancements)
9. [Known Issues & Decisions Log](#9-known-issues--decisions-log)
10. [Milestones & Progress](#10-milestones--progress)
11. [Open Questions](#11-open-questions)
12. [Next Steps](#12-next-steps)

---

## 1. Project Overview

**Puck** is a stream monitor bot for The Alphabet Cartel's Fluxer community. Named for
Shakespeare's mischievous fairy herald from A Midsummer Night's Dream, Puck watches
community members' Twitch and YouTube live channels and announces their presence by
toggling a configurable "Live" role.

**Core v1.0 Functionality:**
- Poll Twitch Helix API and YouTube Data API v3 for tracked users' live status
- Add a configurable "Live" role when a member goes live
- Remove the "Live" role when the stream ends
- Persistent state tracking to survive restarts
- RSS pre-check for YouTube to conserve API quota

**Future Enhancements (hooks designed in v1.0, not implemented):**
- Embedded stream announcement in a configurable channel
- Auto-updating stream screenshot every 5 minutes
- Auto-delete announcement when stream ends

**Naming & Theming:**
- Puck — the fairy herald from A Midsummer Night's Dream
- Pairs with Portia (Merchant of Venice) in the Shakespeare naming thread
- Profile pic: Enchanted lantern broadcasting rainbow light, fairy hand, ornate pride border

---

## 2. Current State

| Milestone | Status | Date |
|-----------|--------|------|
| Design discussion | ✅ Complete | 2026-02-26 |
| Planning doc created | ✅ Complete | 2026-02-26 |
| Project scaffolding | ✅ Complete | 2026-02-26 |
| Logging manager | ✅ Complete | 2026-02-26 |
| Config manager | ✅ Complete | 2026-02-26 |
| Twitch manager | ✅ Complete | 2026-02-26 |
| YouTube manager | ✅ Complete | 2026-02-26 |
| Stream state manager | ✅ Complete | 2026-02-26 |
| Stream monitor handler | ✅ Complete | 2026-02-26 |
| Embed announcer stub | ✅ Complete | 2026-02-26 |
| Main dispatcher + polling loop | ✅ Complete | 2026-02-26 |
| Docker build & test | ⬜ Not Started | — |
| Deployment to Bragi | ⬜ Not Started | — |

---

## 3. Architecture Decisions

### Detection Method: Polling
- Polling both Twitch and YouTube APIs on a configurable interval (default 90 seconds)
- Simpler than webhooks, no inbound endpoint required, works for both platforms
- Twitch EventSub could be added later for faster detection but adds complexity

### Handler-Based Architecture (No Cogs)
- fluxer-py's Cog system is broken as of v0.3.1
- Single `@bot.event` dispatcher in main.py routes to handler classes
- Consistent with Prism and Portia patterns

### Separate Stream List File
- `tracked_streams.json` maintained manually by admin (Bubba)
- Separate from `puck_config.json` for cleaner editing
- Bot commands (`!addstream`, `!removestream`) deferred to future enhancement

### Factory Functions + Dependency Injection
- All managers use `create_*()` factory functions (Charter Rule #1)
- ConfigManager is always the first dependency (Charter Rule #2)
- No direct constructor calls in production code

### Persistent State via JSON
- `stream_state.json` in `/app/data/` tracks current live status
- Survives container restarts
- Reconciliation sweep on startup compares state to live API data

---

## 4. Configuration Design

### Three-Layer Stack (Charter Rules #4 + #7)

**Layer 1 — `puck_config.json`** (committed, structural defaults):
- Poll interval, YouTube multiplier, role/channel IDs with env var references
- Validation rules for each setting

**Layer 2 — `.env`** (not committed, runtime overrides):
- `PUCK_LOG_LEVEL`, `PUCK_GUILD_ID`, `PUCK_LIVE_ROLE_ID`, etc.
- Documented in `.env.template` (committed)

**Layer 3 — Docker Secrets** (sensitive, never committed):
- `puck_fluxer_token` — Fluxer bot token
- `twitch_client_id` — Twitch app client ID
- `twitch_client_secret` — Twitch app client secret
- `youtube_api_key` — Google/YouTube Data API key

### Tracked Streams Config
- Separate `tracked_streams.json` with array of stream mappings
- Each entry: `fluxer_user_id`, `display_name`, `twitch_username` (nullable), `youtube_channel_id` (nullable)

---

## 5. File Structure

```
Y:\git\bragi\puck\
├── .dockerignore
├── .env.template
├── .github/workflows/build.yml
├── .gitignore
├── docker-compose.yml
├── docker-entrypoint.py
├── Dockerfile
├── images/
│   └── Puck.png
├── LICENSE
├── README.md
├── requirements.txt
├── secrets/
│   └── README.md
├── docs/
│   └── planning.md              ← This document
└── src/
    ├── __init__.py
    ├── main.py
    ├── config/
    │   ├── puck_config.json
    │   └── tracked_streams.json
    ├── handlers/
    │   ├── __init__.py
    │   ├── stream_monitor.py
    │   └── embed_announcer.py   ← Stubbed for future
    ├── managers/
    │   ├── __init__.py
    │   ├── config_manager.py
    │   ├── logging_config_manager.py
    │   ├── twitch_manager.py
    │   ├── youtube_manager.py
    │   └── stream_state_manager.py
    └── models/
        ├── __init__.py
        └── stream_status.py
```

---

## 6. Core Flow

```
main.py boots up:
  1. Load config (three-layer stack)
  2. Create managers via factory functions
  3. Authenticate Twitch (client credentials → app access token)
  4. Register on_ready event
  5. Start background polling task (asyncio)

Polling loop (every PUCK_POLL_INTERVAL seconds):
  1. Load tracked users from tracked_streams.json
  2. TwitchManager.check_streams(twitch_usernames)
     → GET /helix/streams?user_login=a&user_login=b (batched, up to 100)
  3. YouTubeManager.check_streams(youtube_channel_ids)
     → RSS pre-check first (free)
     → Only call YouTube API if RSS shows recent activity
     → Runs every N * poll_interval (quota conservation)
  4. StreamStateManager.compare(current vs previous state)
     → WENT_LIVE: member.add_role(live_role_id, guild_id=guild_id)
     → WENT_OFFLINE: member.remove_role(live_role_id, guild_id=guild_id)
     → STILL_LIVE: no-op (future: update embed)
  5. StreamStateManager.persist() → write stream_state.json

Startup reconciliation:
  - On first poll after boot, compare persisted state to API
  - Clean up stale "live" roles if stream ended while bot was down
  - Add missing "live" roles if stream started while bot was down
```

---

## 7. YouTube Quota Strategy

YouTube Data API v3 quota: 10,000 units/day. `search.list` costs 100 units/call.

**Strategy: RSS Pre-Check + Higher Multiplier**
1. Check YouTube RSS feed first (free, no auth, no quota)
   - URL: `https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID`
   - If no video published in last 24 hours → skip API call
2. Only call `search.list` if RSS shows recent activity
3. YouTube poll frequency = base_interval × poll_multiplier (default 3x)
   - Base: 90s → YouTube: every ~4.5 minutes
4. This reduces unnecessary API calls dramatically

**Worst case:** 5 YouTube users, all with recent videos, checked every 4.5 min
= ~320 calls/day = 32,000 units (over budget)

**Realistic case:** RSS filters out most checks, actual API calls ~50-100/day
= 5,000-10,000 units (within budget)

**Safety valve:** If quota exhaustion is detected (403 response), back off to
RSS-only mode for the remainder of the day.

---

## 8. Future Enhancements

### v1.1 — Embed Announcements
- Post an embed to a configurable announcement channel when a member goes live
- Include stream title, game/category, thumbnail, and link
- Auto-update thumbnail every 5 minutes while live
- Auto-delete embed when stream ends
- Twitch provides `thumbnail_url` in streams API (free, auto-updated by Twitch)
- YouTube provides thumbnail via video resource

### v1.2 — Bot Commands
- `!addstream @user twitch:username` — Add a user to tracked streams
- `!removestream @user` — Remove a user from tracked streams
- `!streams` — List all tracked streams and their current status
- Admin-only commands (role-gated)

### v1.3 — Additional Platforms
- Kick.com support
- Other streaming platforms as requested by community

---

## 9. Known Issues & Decisions Log

| Date | Decision/Issue | Resolution |
|------|---------------|------------|
| 2026-02-26 | Detection method | Polling (both platforms), simpler than webhooks |
| 2026-02-26 | YouTube quota | RSS pre-check + higher multiplier to conserve quota |
| 2026-02-26 | Stream list management | Config file only for v1.0, bot commands in v1.2 |
| 2026-02-26 | Submodule path | Top-level (`puck/`) consistent with Portia and Prism |
| 2026-02-26 | Bot name | Puck — Shakespeare's fairy herald, pairs with Portia |
| 2026-02-26 | Embed feature | Hooks designed in v1.0, implementation deferred to v1.1 |

---

## 10. Milestones & Progress

### Phase 1: Scaffolding ✅
- [x] Planning doc
- [x] Project structure (directories, gitignore, dockerignore)
- [x] Dockerfile + docker-compose.yml
- [x] docker-entrypoint.py
- [x] .env.template
- [x] requirements.txt
- [x] Config JSON files
- [x] GitHub Actions workflow
- [x] README.md
- [x] secrets/README.md

### Phase 2: Core Managers ✅
- [x] logging_config_manager.py
- [x] config_manager.py
- [x] twitch_manager.py (auth + stream checking)
- [x] youtube_manager.py (RSS pre-check + API)
- [x] stream_state_manager.py (persist + compare)

### Phase 3: Handlers & Main ✅
- [x] stream_status.py (data models)
- [x] stream_monitor.py (polling loop + role toggle)
- [x] embed_announcer.py (stub with interface)
- [x] main.py (dispatcher + background task)

### Phase 4: Testing & Deployment
- [ ] Local Docker build
- [ ] Test with real Twitch/YouTube accounts
- [ ] Deploy to Bragi (10.20.30.242)
- [ ] Verify role toggle in Fluxer

---

## 11. Open Questions

- What is the Fluxer role ID for the "Live" role? (Need to create it in Fluxer first)
- Which community members should be in the initial `tracked_streams.json`?
- Do we need a Twitch Developer Application yet, or does one already exist?
- Does a Google Cloud project with YouTube Data API v3 enabled exist?

---

## 12. Next Steps

1. ~~Create planning doc~~ ✅
2. Scaffold project structure
3. Build core managers (config, logging, twitch, youtube, state)
4. Build stream monitor handler
5. Build main.py with polling loop
6. Docker build and test
7. Deploy to Bragi

---

**Built with care for chosen family** 🏳️‍🌈
