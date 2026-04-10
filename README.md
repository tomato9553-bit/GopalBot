# GopalBot

A Discord bot powered by Groq's LLaMA 3.3 70B model. GopalBot responds to mentions, direct messages, and any message containing its name with concise, friendly AI-generated replies.

## Features

- Responds when mentioned (`@GopalBot`) in any channel
- Responds to direct messages (DMs)
- Responds when its name (`gopalbot`) appears in a message
- Powered by **LLaMA 3.3 70B** via the [Groq](https://groq.com/) API
- Automatically truncates long responses to fit Discord's 2000-character limit

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

## Dependencies

| Package | Purpose |
|---------|---------|
| `discord.py` | Discord API wrapper |
| `groq` | Groq API client for LLaMA inference |
