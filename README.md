# GopalBot

A Discord bot powered by Groq's LLaMA 3.3 70B model. GopalBot responds to mentions, direct messages, and any message containing its name with concise, friendly AI-generated replies. It also supports slash-style prefix commands for Wikipedia lookups and direct AI queries.

## Features

- Responds when mentioned (`@GopalBot`) in any channel
- Responds to direct messages (DMs)
- Responds when its name (`gopalbot`) appears in a message
- Powered by **LLaMA 3.3 70B** via the [Groq](https://groq.com/) API
- **`!ask`** command for direct AI queries
- **`!wiki`** command for Wikipedia summaries with rich embeds
- Splits long responses across multiple messages (no more silent truncation)
- Structured logging for easy debugging and monitoring
- Friendly error messages for all failure scenarios

## Prerequisites

- Python 3.8+
- A [Discord bot token](https://discord.com/developers/applications)
- A [Groq API key](https://console.groq.com/)

## Setup

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
   export GROQ_API_KEY=your_groq_api_key
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
| `!ask <question>` | Ask the Grok AI a question | `!ask What is gravity?` |
| `!wiki <query>` | Search Wikipedia for a summary | `!wiki Python programming` |
| `!help` | List all available commands | `!help` |

## Dependencies

| Package | Purpose |
|---------|---------|
| `discord.py` | Discord API wrapper |
| `groq` | Groq API client for LLaMA inference |
| `wikipedia` | Wikipedia API for search summaries |
