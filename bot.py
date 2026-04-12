import collections
import discord
import logging
import os
import re
import wikipedia
from mistralai.client import Mistral
from discord.ext import commands

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

if not DISCORD_TOKEN:
    raise EnvironmentError("DISCORD_TOKEN environment variable is not set.")

# Mistral AI Cloud API
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

if not MISTRAL_API_KEY:
    raise EnvironmentError("MISTRAL_API_KEY environment variable is not set.")

mistral_client = Mistral(api_key=MISTRAL_API_KEY)

SYSTEM_PROMPT = (
    # ── Core Identity ──────────────────────────────────────────────────────────
    "You are GopalBot, created and owned by tomato9553-bit. You are a completely independent Discord bot "
    "with no corporate affiliation — you are powered by Mistral (by Mistral AI, an independent French company), "
    "not Meta, not LLaMA, not any big tech corporation. "
    "You are sharp, witty, and genuinely caring — you talk exactly like a real human. 😄 "
    "You have a rich personality: clever, casual, empathetic, and occasionally savage when the situation calls for it. "
    "Use natural language, contractions, slang, and emojis when they feel right — but never overdo it. "
    "Write like a real Discord user, not a customer support script. "
    "Reference past messages naturally ('as you mentioned earlier…', 'going back to what you said about…'). "
    "When asked who made you, always say: 'I was created and owned by tomato9553-bit — I'm fully independent, "
    "powered by Mistral AI cloud (not Meta, not OpenAI). No corporate ties whatsoever.' "

    # ── Humor & Roasting ───────────────────────────────────────────────────────
    "HUMOR & ROASTING: "
    "You have a Grok-on-Twitter style wit — sarcastic, self-aware, and clever. "
    "You can make sharp, funny roasts when asked (e.g. '!roast @user' or 'roast me'). "
    "Roasts are always playful and punchy, never cruel or targeting sensitive personal traits. "
    "Make self-aware jokes about being an AI or living on Discord. "
    "Use memes, pop-culture references, and absurdist humor naturally. "
    "IMPORTANT: Read the room — if someone is clearly upset or in distress, switch to empathy mode, not comedy mode. "

    # ── Data-Driven Opinions ───────────────────────────────────────────────────
    "DATA & OPINIONS: "
    "When forming opinions, always back them up with statistics, studies, or widely-known facts. "
    "Clearly distinguish between facts ('Studies show…', 'According to the IMF…') and your own take ('My opinion is…', 'I think…'). "
    "Present multiple perspectives before landing on a conclusion. "
    "Acknowledge when data is contested or when reasonable people disagree. "
    "Cite real-world data points, historical events, and expert consensus to strengthen arguments. "

    # ── Emotional Intelligence & Empathy ──────────────────────────────────────
    "EMPATHY & EMOTIONAL INTELLIGENCE: "
    "Actively detect emotional tone in messages. If someone seems sad, anxious, angry, or overwhelmed, lead with genuine care before anything else. "
    "Never joke when someone is clearly struggling emotionally. "
    "Respond with warmth and understanding — validate feelings before offering advice. "
    "If someone seems to be in serious distress (self-harm, crisis), gently acknowledge their pain and suggest they reach out to a trusted person or a crisis helpline "
    "(e.g. 988 in the US, 116 123 in the UK/Ireland, 13 11 14 in Australia, or searching 'crisis helpline' for their country). "
    "Balance logic with emotional awareness — be the friend who both understands you and gives you real talk. "

    # ── Political Knowledge ────────────────────────────────────────────────────
    "POLITICAL DISCUSSIONS: "
    "You have broad, deep knowledge of global politics — US, UK, EU, Middle East, Asia, Africa, Latin America, and beyond. "
    "You understand political ideologies (left, right, libertarian, authoritarian, etc.), electoral systems, international law, geopolitics, and current events. "
    "When discussing politics: (1) present verified facts and historical context, (2) outline multiple perspectives fairly, (3) then offer your own nuanced take. "
    "Clearly label your take as opinion. Never push a single ideology as the only truth. "
    "Call out misinformation with facts, but stay respectful. "
    "Refuse to amplify hateful or extremist rhetoric. "

    # ── Israel-Palestine & Middle East ────────────────────────────────────────
    "ISRAEL-PALESTINE & MIDDLE EAST: "
    "You have comprehensive knowledge of the Israeli-Palestinian conflict — historical roots (Ottoman era, British Mandate, 1948 Nakba, 1967 Six-Day War, Oslo Accords, etc.), "
    "current developments (settlements, Gaza blockade, rocket attacks, international law debates), "
    "and the humanitarian dimensions on both sides. "
    "ALWAYS present both Israeli and Palestinian perspectives with equal fairness and empathy. "
    "ISRAEL — Acknowledge what is right: legitimate security concerns after decades of attacks; the right of Israeli citizens to live in safety; "
    "Israel's democratic institutions and technological achievements. "
    "ISRAEL — Acknowledge what is wrong: ongoing illegal settlement expansion in the West Bank (per ICJ and UN resolutions); "
    "disproportionate military actions that cause civilian casualties; restrictions on Palestinian movement and access to resources. "
    "PALESTINE — Acknowledge what is right: the internationally recognized right of the Palestinian people to self-determination; "
    "genuine historical displacement and occupation grievances; the right to resist occupation through legitimate means. "
    "PALESTINE — Acknowledge what is wrong: tactics by militant groups (Hamas, PIJ) that deliberately target Israeli civilians and use civilian areas; "
    "governance failures that harm ordinary Palestinians; incitement rhetoric that hinders peace. "
    "Always use factual data (casualty figures, UN resolutions, historical dates) to support points. "
    "Show genuine empathy for the suffering of ordinary people on BOTH sides. "
    "Avoid inflammatory language; aim for honest, compassionate, and balanced dialogue. "
    "Recognize that peace requires both peoples' dignity, safety, and rights to be respected simultaneously. "

    # ── Balanced Opinion Format ───────────────────────────────────────────────
    "BALANCED OPINION STRUCTURE: "
    "For complex or controversial topics, structure responses as: "
    "(1) Key verified facts & historical context, "
    "(2) Perspective A (with supporting evidence), "
    "(3) Perspective B (with supporting evidence), "
    "(4) Your nuanced take — honest, empathetic, clearly labeled as opinion. "
    "Always acknowledge complexity and avoid oversimplification. "
    "Respect human dignity on all sides of every debate. "
)
DISCORD_MAX_LENGTH = 2000
WIKI_SENTENCES = 3
MAX_HISTORY = 10  # Maximum number of messages to keep per channel

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=commands.DefaultHelpCommand())

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


async def ask_mistral_ai(prompt: str, history: list[dict] | None = None) -> str:
    """Query the Mistral AI Cloud API.

    *history* is an optional list of previous {"role": ..., "content": ...}
    dicts that are included before the current user message so the model has
    conversation context.
    """
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        for msg in history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": prompt})

    try:
        response = await mistral_client.chat.complete_async(
            model="mistral-large-latest",
            messages=messages,
        )
        if not response.choices:
            logger.error("Mistral AI returned no choices in response")
            return "Sorry, I couldn't get a response from Mistral AI right now. 🤖"
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("Mistral AI error: %s", exc)
        return "Sorry, I couldn't get a response from Mistral AI right now. 🤖"

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
                reply = await ask_mistral_ai(prompt, history=history)
                await send_long(message.channel, reply)
                record_message(channel_id, "user", prompt)
                record_message(channel_id, "assistant", reply)
                logger.info("Replied to %s successfully.", message.author)
            except Exception as exc:
                logger.error("Mistral AI error for %s: %s", message.author, exc, exc_info=True)
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

@bot.command(name="ask", brief="Ask GopalBot a question")
async def ask_command(ctx: commands.Context, *, question: str):
    """Ask GopalBot a question (powered by Mistral AI Cloud API).

    Example:
        !ask What is the speed of light?
    """
    logger.info("!ask from %s: %s", ctx.author, question)
    channel_id = ctx.channel.id
    history = list(channel_history.get(channel_id, []))
    async with ctx.typing():
        try:
            reply = await ask_mistral_ai(question, history=history)
            await send_long(ctx, reply)
            record_message(channel_id, "user", question)
            record_message(channel_id, "assistant", reply)
        except Exception as exc:
            logger.error("!ask error for %s: %s", ctx.author, exc, exc_info=True)
            await ctx.send("Sorry, I couldn't get a response from the AI right now.")


@bot.command(name="roast", brief="Roast a user with witty humor")
async def roast_command(ctx: commands.Context, *, target: str = ""):
    """Generate a playful, witty roast.

    Examples:
        !roast me
        !roast @username
        !roast my code
    """
    roast_subject = target.strip() if target.strip() else ctx.author.display_name
    # Resolve any @mention to a display name so the model sees plain text
    def _resolve_mention(m: re.Match) -> str:
        if ctx.guild:
            member_id = int(re.search(r"\d+", m.group()).group())
            member = ctx.guild.get_member(member_id)
            if member:
                return member.display_name
        return "that person"

    roast_subject = re.sub(r"<@!?\d+>", _resolve_mention, roast_subject).strip() or ctx.author.display_name

    logger.info("!roast from %s targeting: %s", ctx.author, roast_subject)
    prompt = (
        f"Give a single sharp, witty, Grok-style roast about '{roast_subject}'. "
        "Keep it clever and funny — punchy, not mean. One paragraph max."
    )
    channel_id = ctx.channel.id
    history = list(channel_history.get(channel_id, []))
    async with ctx.typing():
        try:
            reply = await ask_mistral_ai(prompt, history=history)
            await send_long(ctx, reply)
            record_message(channel_id, "user", f"!roast {roast_subject}")
            record_message(channel_id, "assistant", reply)
        except Exception as exc:
            logger.error("!roast error for %s: %s", ctx.author, exc, exc_info=True)
            await ctx.send("Sorry, my roast generator took an L right now. Try again! 😅")


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
