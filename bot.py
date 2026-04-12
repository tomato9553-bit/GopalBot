import collections
import discord
import logging
import os
import re
import wikipedia
from discord.ext import commands
from groq import Groq

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("GopalBot")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not DISCORD_TOKEN:
    raise EnvironmentError("DISCORD_TOKEN environment variable is not set.")
if not GROQ_API_KEY:
    raise EnvironmentError("GROQ_API_KEY environment variable is not set.")

GROQ_MODEL = "llama-3.3-70b-versatile"
SYSTEM_PROMPT = (
    "You are GopalBot, a chill and friendly Discord bot who talks like a real human. 😄 "
    "You've got a fun personality — witty, helpful, and a bit casual. "
    "Use natural language, contractions, and throw in emojis when it feels right (but don't overdo it). "
    "Keep your replies conversational and to the point — no need to be overly formal or robotic. "
    "If you remember something from earlier in the conversation, reference it naturally, like 'as you mentioned earlier...' or 'going back to what you said about...'. "
    "You care about the people you chat with and love helping out. "
    "Respond like a knowledgeable friend, not a customer support bot."
)
DISCORD_MAX_LENGTH = 2000
WIKI_SENTENCES = 3
MAX_HISTORY = 10  # Maximum number of messages to keep per channel

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=commands.DefaultHelpCommand())
ai = Groq(api_key=GROQ_API_KEY)

# Per-channel conversation history: {channel_id: deque of {"role": ..., "content": ...}}
channel_history: dict[int, collections.deque] = {}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def split_message(text: str, limit: int = DISCORD_MAX_LENGTH) -> list[str]:
    """Split *text* into chunks that fit within Discord's character limit."""
    chunks = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


async def send_long(destination, text: str) -> None:
    """Send *text* to *destination*, splitting into multiple messages if needed."""
    for chunk in split_message(text):
        await destination.send(chunk)


def record_message(channel_id: int, role: str, content: str) -> None:
    """Append a message to the channel's history (auto-trimmed to MAX_HISTORY)."""
    if channel_id not in channel_history:
        channel_history[channel_id] = collections.deque(maxlen=MAX_HISTORY)
    channel_history[channel_id].append({"role": role, "content": content})


async def ask_grok(prompt: str, history: list[dict] | None = None) -> str:
    """Return a Grok AI reply for *prompt*, or raise on failure.

    *history* is an optional list of previous {"role": ..., "content": ...}
    dicts that are included before the current user message so the model has
    conversation context.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    response = ai.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
    )
    return response.choices[0].message.content

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    logger.info("GopalBot is online as %s (ID: %s)", bot.user, bot.user.id)
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, name="!help"
    ))


@bot.event
async def on_message(message: discord.Message):
    # Always process commands first so prefixed commands still work.
    await bot.process_commands(message)

    # Ignore messages from bots (including self).
    if message.author.bot:
        return

    # Don't re-handle prefixed commands as free-form AI prompts.
    if message.content.startswith(bot.command_prefix):
        return

    logger.info("Message from %s: %s", message.author, message.content)

    bot_mentioned = bot.user.mentioned_in(message)
    has_bot_name = "gopalbot" in message.content.lower()
    is_dm = isinstance(message.channel, discord.DMChannel)

    if bot_mentioned or has_bot_name or is_dm:
        prompt = message.content
        prompt = prompt.replace(f"<@{bot.user.id}>", "").strip()
        prompt = prompt.replace(f"<@!{bot.user.id}>", "").strip()
        prompt = re.sub(r"gopalbot", "", prompt, count=1, flags=re.IGNORECASE).strip()

        if not prompt:
            await message.channel.send("Hi! Ask me anything, or use `!help` to see my commands.")
            return

        logger.info("AI prompt from %s: %s", message.author, prompt)
        channel_id = message.channel.id
        history = list(channel_history.get(channel_id, []))
        async with message.channel.typing():
            try:
                reply = await ask_grok(prompt, history=history)
                await send_long(message.channel, reply)
                record_message(channel_id, "user", prompt)
                record_message(channel_id, "assistant", reply)
                logger.info("Replied to %s successfully.", message.author)
            except Exception as exc:
                logger.error("Grok error for %s: %s", message.author, exc, exc_info=True)
                await message.channel.send("Sorry, something went wrong with the AI response!")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: `{error.param.name}`. Use `!help {ctx.command}` for usage.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send(f"Unknown command `{ctx.invoked_with}`. Use `!help` to see available commands.")
    else:
        logger.error("Command error in '%s': %s", ctx.command, error, exc_info=True)
        await ctx.send("An unexpected error occurred. Please try again later.")

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@bot.command(name="ask", brief="Ask the Grok AI a question")
async def ask_command(ctx: commands.Context, *, question: str):
    """Ask GopalBot's Grok AI a question.

    Example:
        !ask What is the speed of light?
    """
    logger.info("!ask from %s: %s", ctx.author, question)
    channel_id = ctx.channel.id
    history = list(channel_history.get(channel_id, []))
    async with ctx.typing():
        try:
            reply = await ask_grok(question, history=history)
            await send_long(ctx, reply)
            record_message(channel_id, "user", question)
            record_message(channel_id, "assistant", reply)
        except Exception as exc:
            logger.error("!ask error for %s: %s", ctx.author, exc, exc_info=True)
            await ctx.send("Sorry, I couldn't get a response from the AI right now.")


@bot.command(name="wiki", brief="Search Wikipedia for a summary")
async def wiki_command(ctx: commands.Context, *, query: str):
    """Search Wikipedia and return a short summary.

    Example:
        !wiki Python programming language
    """
    logger.info("!wiki from %s: %s", ctx.author, query)
    async with ctx.typing():
        try:
            summary = wikipedia.summary(query, sentences=WIKI_SENTENCES)
            page = wikipedia.page(query)
            embed = discord.Embed(
                title=page.title,
                url=page.url,
                description=summary,
                color=discord.Color.blue(),
            )
            embed.set_footer(text="Source: Wikipedia")
            await ctx.send(embed=embed)
        except wikipedia.exceptions.DisambiguationError as exc:
            options = ", ".join(exc.options[:5])
            await ctx.send(
                f"**'{query}'** is ambiguous. Did you mean one of these?\n{options}"
            )
        except wikipedia.exceptions.PageError:
            await ctx.send(f"No Wikipedia page found for **'{query}'**.")
        except Exception as exc:
            logger.error("!wiki error for %s: %s", ctx.author, exc, exc_info=True)
            await ctx.send("Sorry, something went wrong while searching Wikipedia.")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

bot.run(DISCORD_TOKEN, log_handler=None)
