# Puck Bot — Secrets Directory

This directory contains Docker Secret files for puck-bot. These files are
**never committed to version control** (gitignored).

## Required Secrets

| File | Description | Source |
|------|-------------|--------|
| `puck_fluxer_token` | Bot token from the Fluxer App for Puck | Fluxer App |
| `twitch_client_id` | Twitch application Client ID | [Twitch Developer Console](https://dev.twitch.tv/console/apps) |
| `twitch_client_secret` | Twitch application Client Secret | [Twitch Developer Console](https://dev.twitch.tv/console/apps) |
| `youtube_api_key` | Google/YouTube Data API v3 key | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) |

---

## Setup: Twitch API Credentials

Puck uses the Twitch Helix API with **client credentials** (app access token) to check
stream status. This requires a Twitch application with a Client ID and Client Secret.

### Prerequisites

- A Twitch account (any account works — does not need to be a streamer)
- Two-factor authentication (2FA) enabled on the Twitch account (required by Twitch
  to access the Developer Console)

### Step-by-Step

1. **Enable 2FA on your Twitch account** (if not already done)
   - Go to [twitch.tv/settings/security](https://www.twitch.tv/settings/security)
   - Under **Two-Factor Authentication**, click **Set Up Two-Factor Authentication**
   - Follow the prompts (SMS or authenticator app)

2. **Open the Twitch Developer Console**
   - Go to [dev.twitch.tv/console](https://dev.twitch.tv/console)
   - Log in with your Twitch account and authorize access

3. **Register a new application**
   - Click the **Applications** tab
   - Click **Register Your Application**
   - Fill in the fields:
     - **Name**: `Puck - Alphabet Cartel` (must be unique across all Twitch apps)
     - **OAuth Redirect URLs**: `http://localhost:3000` (required but not used by Puck)
     - **Category**: `Application Integration`
   - Click **Create**

4. **Get your Client ID**
   - After creating the app, click **Manage** next to your application
   - Copy the **Client ID** shown on the page
   - Create the secret file:
     ```
     printf "YOUR_CLIENT_ID_HERE" > ./secrets/twitch_client_id
     ```

5. **Generate a Client Secret**
   - On the same Manage page, click **New Secret**
   - Copy the **Client Secret** immediately — it will only be shown once
   - Create the secret file:
     ```
     printf "YOUR_CLIENT_SECRET_HERE" > ./secrets/twitch_client_secret
     ```

### Important Notes

- The Client Secret is only displayed **once** when generated. If you lose it, you
  must generate a new one (which invalidates the old one).
- Puck uses the **client credentials grant flow** (server-to-server). It does not
  need user authorization or scopes — it only reads public stream data.
- The app access token is automatically obtained and refreshed by Puck at runtime.
  You only need to provide the Client ID and Client Secret.
- Do **not** share Client IDs between applications. Each Twitch app must have its
  own unique Client ID.

---

## Setup: YouTube Data API v3 Key

Puck uses the YouTube Data API v3 to check if tracked YouTube channels are currently
live streaming. This requires a Google Cloud project with the API enabled and an API key.

### Prerequisites

- A Google account (any Google account works)

### Step-by-Step

1. **Open the Google Cloud Console**
   - Go to [console.cloud.google.com](https://console.cloud.google.com)
   - Log in with your Google account
   - Accept the Terms of Service if prompted

2. **Create a new project**
   - Click the project selector dropdown at the top of the page
   - Click **New Project**
   - Name it something like `Puck Stream Monitor` or `Alphabet Cartel Bots`
   - Click **Create**, then select the new project from the dropdown

3. **Enable the YouTube Data API v3**
   - In the left sidebar, go to **APIs & Services** → **Library**
   - Search for `YouTube Data API v3`
   - Click on **YouTube Data API v3** in the results
   - Click the blue **Enable** button

4. **Create an API Key**
   - In the left sidebar, go to **APIs & Services** → **Credentials**
   - Click **Create Credentials** at the top → **API Key**
   - Your new API key will be displayed — copy it
   - Create the secret file:
     ```
     printf "YOUR_API_KEY_HERE" > ./secrets/youtube_api_key
     ```

5. **Restrict the API key** (recommended)
   - Click **Edit API Key** (or click the key name in the Credentials list)
   - Under **API restrictions**, select **Restrict key**
   - From the dropdown, select **YouTube Data API v3** only
   - Click **Save**
   - This prevents the key from being used with other Google APIs if it is
     ever accidentally exposed

### Important Notes

- The YouTube Data API v3 has a default quota of **10,000 units per day**.
  Each `search.list` call (used by Puck to check live status) costs 100 units.
- Puck conserves quota by using free RSS pre-checks before making API calls,
  and by polling YouTube less frequently than Twitch (configurable via
  `PUCK_YOUTUBE_POLL_MULTIPLIER` in `.env`).
- If quota is exhausted (Puck receives a 403 response), it automatically falls
  back to RSS-only mode for the remainder of the day.
- Quota resets daily at midnight Pacific Time.
- Do **not** restrict the key by IP address unless you know Bragi's outbound IP,
  as this could prevent the bot from reaching the API.

---

## Setup: Fluxer Bot Token

1. Obtain a bot token from the Fluxer Developer Portal (or request one from
   the Fluxer team if no self-service portal exists yet)
2. Create the secret file:
   ```
   printf "YOUR_FLUXER_BOT_TOKEN_HERE" > ./secrets/puck_fluxer_token
   ```

---

## Deploying Secrets to Bragi

After creating all four secret files, set permissions:

```bash
chmod 600 /opt/bragi/secrets/puck_fluxer_token
chmod 600 /opt/bragi/secrets/twitch_client_id
chmod 600 /opt/bragi/secrets/twitch_client_secret
chmod 600 /opt/bragi/secrets/youtube_api_key
```

## Security Reminders

- These files are referenced by `docker-compose.yml` and mounted at `/run/secrets/`
- The bot reads them via the `load_secret()` pattern in `config_manager.py`
- Never commit these files — only this README is tracked
- Rotate secrets periodically and after any suspected exposure
- The `secrets/` directory is gitignored in this repository

---

**Built with care for chosen family** 🏳️‍🌈
