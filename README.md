# GopalBot

A fully **self-hosted, independent** Discord bot owned and created by **tomato9553-bit**.  
GopalBot is powered by **Mistral 7B** (by Mistral AI — an independent French company, not Meta) running
on the owner's Victus PC with an RTX 3050.  The Discord-facing bot runs on Railway, while all AI
inference stays on the owner's hardware — **zero data leaves their machine, zero corporate involvement.**

## Architecture

```
Discord Server
      │
      ▼
Railway Bot  (always online, handles Discord events)
      │
      ▼
Owner's Victus PC — local_api_server.py  (port 8000, runs when PC is on)
      │
      ▼
Ollama — Mistral 7B  (GPU-accelerated on RTX 3050, instant responses)
```

When the owner's PC is off, the bot responds with a friendly offline message instead of crashing.

## Features

- Responds when mentioned (`@GopalBot`) in any channel
- Responds to direct messages (DMs)
- Responds when its name (`gopalbot`) appears in a message
- Powered by **Mistral 7B** via [Ollama](https://ollama.ai/) running locally (no external AI APIs)
- **Complete Privacy** — AI runs on owner's hardware, no data sent to third parties
- **No Meta/Corporate Ties** — Mistral AI is independent; no LLaMA, no Groq, no OpenAI
- **Chat History Memory** — remembers the last 10 messages per channel for context-aware replies
- **Human-Like Personality** — casual, witty, uses emojis naturally, references past messages
- **Humor & Roasting** — clever, self-aware humor; playful roasts on demand
- **Data-Driven Opinions** — backs arguments with statistics and facts, clearly labels opinion vs. fact
- **Emotional Intelligence & Empathy** — detects emotional tone, responds with care in serious situations
- **Political Knowledge** — broad knowledge of global politics with nuanced, balanced takes
- **`!ask`** command for direct AI queries
- **`!roast`** command for witty, playful roasts
- **`!wiki`** command for Wikipedia summaries with rich embeds
- Splits long responses across multiple messages (no silent truncation)
- Friendly offline message when owner's PC is unavailable

## Prerequisites

- Python 3.8+
- A [Discord bot token](https://discord.com/developers/applications)
- Owner's Windows PC with Ollama + Mistral 7B installed (see [LOCAL_API_SETUP.md](LOCAL_API_SETUP.md))

## Setup

### 1. Local API (Owner's Victus PC)

Follow [LOCAL_API_SETUP.md](LOCAL_API_SETUP.md) to:

1. Install Ollama on Windows
2. Pull the Mistral model: `ollama pull mistral`
3. Start the local API server: `python local_api_server.py`
4. (Optional) Expose it publicly via ngrok: `ngrok http 8000`

### 2. Railway Bot

1. **Clone the repository**

   ```bash
   git clone https://github.com/tomato9553-bit/GopalBot.git
   cd GopalBot
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**

   ```bash
   export DISCORD_TOKEN=your_discord_bot_token
   export LOCAL_API_URL=https://your-ngrok-url.ngrok-free.app   # or LAN IP
   ```

4. **Run the bot**

   ```bash
   python bot.py
   ```

## Usage

- **Mention the bot:** `@GopalBot What is the capital of France?`
- **Use its name:** `GopalBot tell me a joke`
- **Send a DM:** Send a message directly to the bot
- **Ask the AI directly:** `!ask Explain quantum computing`
- **Search Wikipedia:** `!wiki Albert Einstein`
- **View all commands:** `!help`

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!ask <question>` | Ask GopalBot a question | `!ask What is gravity?` |
| `!roast [target]` | Get a witty, playful roast | `!roast me` / `!roast @friend` |
| `!wiki <query>` | Search Wikipedia for a summary | `!wiki Python programming` |
| `!help` | List all available commands | `!help` |

## Files

| File | Purpose |
|------|---------|
| `bot.py` | Discord bot — runs on Railway |
| `local_api_server.py` | Local API server — runs on Victus PC |
| `requirements.txt` | Railway bot dependencies |
| `requirements_local.txt` | Local API server dependencies |
| `LOCAL_API_SETUP.md` | Step-by-step Windows setup guide |

## Dependencies

### Railway bot (`requirements.txt`)

| Package | Purpose |
|---------|---------|
| `discord.py` | Discord API wrapper |
| `requests` | HTTP client for local API calls |
| `wikipedia` | Wikipedia API for search summaries |

### Local API server (`requirements_local.txt`)

| Package | Purpose |
|---------|---------|
| `flask` | Lightweight HTTP server |
| `requests` | HTTP client for Ollama calls |

## Privacy & Independence

✅ **Owner:** tomato9553-bit  
✅ **Model:** Mistral 7B — independent French AI company, no Meta involvement  
✅ **Runtime:** Ollama (open-source) on owner's RTX 3050  
✅ **Data:** Stays on owner's hardware — never sent to external servers  
✅ **No corporate ties:** No Groq, no OpenAI, no Meta, no LLaMA  

