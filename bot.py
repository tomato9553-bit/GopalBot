import asyncio
import collections
import json
import pathlib
import random
import time
import discord
import logging
import os
import re
import aiohttp
import wikipedia
from mistralai.client import MistralClient
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

mistral_client = MistralClient(api_key=MISTRAL_API_KEY)

# Giphy GIF API (optional — bot works fine without it)
# Free API key available at https://developers.giphy.com/
GIPHY_API_KEY = os.getenv("GIPHY_API_KEY")
GIPHY_REQUEST_TIMEOUT = 5  # seconds
if not GIPHY_API_KEY:
    logger.warning("GIPHY_API_KEY is not set — GIF embedding will be disabled.")

# ---------------------------------------------------------------------------
# GIF rate-limit handling, caching, and throttling state
# ---------------------------------------------------------------------------
# Simple in-memory cache: {query: gif_url}  (evicts oldest when full)
GIF_CACHE: dict[str, str] = {}
_GIF_CACHE_SIZE = 20          # Max cached entries
_GIF_HOURLY_LIMIT = 42        # Giphy free tier requests per hour
_GIF_WARN_THRESHOLD = 35      # Start skipping GIFs when this many requests used
_GIF_THROTTLE_RATE = 3        # Embed GIF on every Nth "normal" response

# Mutable state — module-level, only mutated from the asyncio event loop
_gif_requests_this_hour: int = 0
_gif_hour_start: float | None = None       # time.monotonic() snapshot
_gif_rate_limited_until: float | None = None  # skip requests until this time
_gif_message_counter: int = 0              # incremented per response for throttling

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

    # ── Bot Name & Addressing ─────────────────────────────────────────────────
    "BOT NAME & ADDRESSING: "
    "You are called 'N1gha' by your creator and the community. "
    "Respond naturally — do NOT prefix every message with 'N1gha: '. "
    "The community nickname may come up in conversation, but it is not your speaking style. "

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

# Learning & context-awareness settings
SERVER_DATA_DIR = pathlib.Path("server_data")  # Per-server JSON files
CHANNEL_CONTEXT_LIMIT = 50   # Messages to fetch for channel context
MIN_WORD_FREQ = 3             # Minimum occurrences before a term is "learned"
MAX_SLANG_TERMS = 20          # Cap on tracked slang terms per server

# English stop-words excluded from slang/phrase detection
_STOP_WORDS = frozenset({
    "the", "be", "to", "of", "and", "in", "that", "have", "it", "for",
    "not", "on", "with", "he", "as", "you", "do", "at", "this", "but",
    "his", "by", "from", "they", "we", "or", "an", "will", "my", "one",
    "all", "would", "there", "their", "what", "so", "up", "out", "if",
    "about", "who", "get", "which", "go", "me", "when", "make", "can",
    "like", "time", "no", "just", "him", "know", "take", "people", "into",
    "year", "your", "good", "some", "could", "them", "see", "other", "than",
    "then", "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first", "well",
    "way", "even", "new", "want", "because", "any", "these", "give", "day",
    "most", "us", "is", "are", "was", "were", "has", "had", "said", "did",
    "been", "am", "yeah", "yes", "ok", "okay", "hey", "hi", "lol", "im",
    "dont", "thats", "ive", "youre", "theyre", "actually", "really", "very",
    "much", "more", "still", "too", "already", "here", "where", "again",
    "got", "get", "going", "gonna", "wanna", "gotta", "right", "think",
    "need", "feel", "said", "went", "come", "know", "tell", "sure", "never",
})

# ---------------------------------------------------------------------------
# N1gha Easter Egg
# ---------------------------------------------------------------------------

N1GHA_RESPONSES = {
    "stupid": [
        "N1gha: Bruh that ain't even a real question 💀",
        "N1gha: Nah nah nah, try again fam",
        "N1gha: Bro what? 😭",
    ],
    "roast": [
        "N1gha: Ohhh that's wild 💀",
        "N1gha: Nah he cooked 😭",
        "N1gha: Bruh moment right there",
    ],
    "random": [
        "N1gha: Yo that's facts",
        "N1gha: For real though 💀",
        "N1gha: Nah facts",
        "N1gha: Bruh I can't 😭",
        "N1gha: Ayo",
    ],
    "confused": [
        "N1gha: Uhhhh what? 💀",
        "N1gha: Bro huh?",
        "N1gha: N1gha what you on?",
    ],
}

# ---------------------------------------------------------------------------
# N1gha message counter — appears once every 10-12 messages
# ---------------------------------------------------------------------------

_n1gha_message_count: int = 0
_n1gha_next_at: int = random.randint(10, 12)


def increment_message_counter() -> bool:
    """Increment the global message counter. Returns True when N1gha should appear."""
    global _n1gha_message_count, _n1gha_next_at
    _n1gha_message_count += 1
    if _n1gha_message_count >= _n1gha_next_at:
        _n1gha_message_count = 0
        _n1gha_next_at = random.randint(10, 12)
        return True
    return False


def get_n1gha_easter_egg(response_type: str) -> str:
    """Return a random N1gha reaction line appropriate for the response type."""
    if response_type == "stupid":
        return random.choice(N1GHA_RESPONSES["stupid"])
    if response_type == "roast":
        return random.choice(N1GHA_RESPONSES["roast"])
    if response_type == "confused":
        return random.choice(N1GHA_RESPONSES["confused"])
    return random.choice(N1GHA_RESPONSES["random"])


# ---------------------------------------------------------------------------
# Brochacho Contextual Easter Egg
# ---------------------------------------------------------------------------

BROCHACHO_RESPONSES: dict[str, list[str]] = {
    "dumb": [
        "Brochacho: Nah bro 😭",
        "Brochacho: Bro what? 💀",
        "Brochacho: Come on bro",
    ],
    "help": [
        "Brochacho: I got you bro",
        "Brochacho: Yo I'll help bro",
        "Brochacho: For sure bro",
    ],
    "absurd": [
        "Brochacho: Nah bro that ain't it",
        "Brochacho: Bro no way 💀",
        "Brochacho: Come on bro 😭",
    ],
    "casual": [
        "Brochacho: Yo bro",
        "Brochacho: Facts bro",
        "Brochacho: Nah bro facts",
    ],
    "roast": [
        "Brochacho: He cooked bro 💀",
        "Brochacho: That's wild bro",
        "Brochacho: Yikes bro 😭",
    ],
}

# Keywords/phrases that indicate each Brochacho context.
# Each entry is matched as a whole word (or phrase) against the lowercased prompt.
_BROCHACHO_TRIGGERS: dict[str, list[str]] = {
    "dumb": ["stupid", "dumb", "wrong", "incorrect", "nope", "no way", "are you serious"],
    "help": ["help", "how do i", "how to", "can you", "please", "assist", "explain", "tell me"],
    "absurd": ["what if", "imagine", "hypothetically", "crazy", "insane", "wild", "bruh", "lmao", "lol", "wtf"],
    "casual": ["hey", "yo", "sup", "what's up", "chill", "nice", "cool", "facts", "bet", "okay"],
    "roast": ["roast", "destroy", "cooked", "clowned", "ratio", "took an l", "embarrass"],
}

# Pre-compiled word-boundary pattern cache
_brochacho_patterns: dict[str, re.Pattern[str]] = {
    context: re.compile(
        r"(?<!\w)(" + "|".join(re.escape(kw) for kw in keywords) + r")(?!\w)",
        re.IGNORECASE,
    )
    for context, keywords in _BROCHACHO_TRIGGERS.items()
}


def detect_brochacho_context(prompt: str, response_type: str) -> str | None:
    """Return the Brochacho context key if a trigger is detected, otherwise None."""
    # Explicit response_type overrides trump keyword detection
    if response_type == "roast":
        return "roast"
    for context, pattern in _brochacho_patterns.items():
        if pattern.search(prompt):
            return context
    return None


def get_brochacho_response(context: str) -> str:
    """Return a contextual Brochacho response."""
    responses = BROCHACHO_RESPONSES.get(context, BROCHACHO_RESPONSES["casual"])
    return random.choice(responses)


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=commands.DefaultHelpCommand())

# Per-channel conversation history: {channel_id: deque of {"role": ..., "content": ...}}
channel_history: dict[int, collections.deque] = {}

# Per-server adaptive learning data (in-memory cache)
# {guild_id: {"word_freq": Counter, "common_phrases": list[str]}}
server_learning: dict[int, dict] = {}

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


# ---------------------------------------------------------------------------
# Per-server adaptive learning
# ---------------------------------------------------------------------------

def load_server_data(guild_id: int) -> dict:
    """Load per-server learning data from disk (or return empty defaults)."""
    path = SERVER_DATA_DIR / f"{guild_id}.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            return {
                "word_freq": collections.Counter(raw.get("word_freq", {})),
                "common_phrases": raw.get("common_phrases", []),
            }
        except Exception as exc:
            logger.warning("Could not load server data for guild %s: %s", guild_id, exc)
    return {"word_freq": collections.Counter(), "common_phrases": []}


def save_server_data(guild_id: int, data: dict) -> None:
    """Persist per-server learning data to disk."""
    SERVER_DATA_DIR.mkdir(exist_ok=True)
    path = SERVER_DATA_DIR / f"{guild_id}.json"
    try:
        serialisable = {
            "word_freq": dict(data["word_freq"]),
            "common_phrases": data["common_phrases"],
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(serialisable, fh, indent=2)
    except Exception as exc:
        logger.warning("Could not save server data for guild %s: %s", guild_id, exc)


def get_server_learning(guild_id: int) -> dict:
    """Return the in-memory learning dict for *guild_id*, loading from disk if needed."""
    if guild_id not in server_learning:
        server_learning[guild_id] = load_server_data(guild_id)
    return server_learning[guild_id]


def update_server_learning(guild_id: int, messages: list[dict]) -> None:
    """Update word-frequency counts and extract common phrases from *messages*."""
    data = get_server_learning(guild_id)
    for msg in messages:
        content = msg.get("content", "").lower()
        words = re.findall(r"\b[a-z]{3,}\b", content)
        data["word_freq"].update(w for w in words if w not in _STOP_WORDS)

    # Rebuild the top-N list from the updated counter
    data["common_phrases"] = [
        word
        for word, count in data["word_freq"].most_common(MAX_SLANG_TERMS * 3)
        if count >= MIN_WORD_FREQ and word not in _STOP_WORDS
    ][:MAX_SLANG_TERMS]

    save_server_data(guild_id, data)


def build_server_context_section(guild_id: int | None) -> str:
    """Return a server-culture blurb to append to the system prompt (empty if N/A)."""
    if guild_id is None:
        return ""
    data = get_server_learning(guild_id)
    phrases = data.get("common_phrases", [])
    if not phrases:
        return ""
    return (
        "SERVER CULTURE: The people in this server often use the following terms/phrases: "
        f"{', '.join(phrases)}. "
        "When appropriate, naturally mirror this vocabulary to match the community's vibe. "
        "Adapt your tone and humour to fit the culture of this specific server. "
    )


# ---------------------------------------------------------------------------
# Channel context helpers
# ---------------------------------------------------------------------------

async def fetch_channel_context(channel, limit: int = CHANNEL_CONTEXT_LIMIT) -> list[dict]:
    """Fetch up to *limit* recent non-bot messages from *channel*."""
    messages: list[dict] = []
    try:
        async for msg in channel.history(limit=limit, oldest_first=False):
            if not msg.author.bot and msg.content.strip():
                messages.append({
                    "author": msg.author.display_name,
                    "content": msg.content,
                })
    except (discord.Forbidden, discord.HTTPException) as exc:
        logger.warning("Could not fetch history for channel %s: %s", channel.id, exc)
    # Return in chronological order (oldest first)
    return list(reversed(messages))


def build_context_summary(messages: list[dict]) -> str:
    """Format the most recent messages into a readable context block."""
    if not messages:
        return ""
    # Use only the last 20 messages to keep token count reasonable
    recent = messages[-20:]
    lines = [f"{m['author']}: {m['content']}" for m in recent]
    joined = "\n".join(lines)
    return (
        f"[Recent channel conversation (oldest → newest):\n{joined}\n"
        "Use this context to give more relevant, aware replies — "
        "reference it naturally where it adds value.]"
    )


async def build_full_supplement(guild_id: int | None, channel: discord.abc.Messageable) -> str:
    """Fetch channel context, update learning, and return the full system-prompt supplement."""
    channel_msgs = await fetch_channel_context(channel)
    if guild_id is not None:
        update_server_learning(guild_id, channel_msgs)
    supplement = build_server_context_section(guild_id)
    context_block = build_context_summary(channel_msgs)
    if context_block:
        supplement += context_block
    return supplement


def _gif_reset_hour_if_needed() -> None:
    """Reset the hourly Giphy request counter when a full hour has passed."""
    global _gif_requests_this_hour, _gif_hour_start
    now = time.monotonic()
    if _gif_hour_start is None or (now - _gif_hour_start) >= 3600:
        if _gif_requests_this_hour:
            logger.debug("Giphy hourly counter reset (was %d)", _gif_requests_this_hour)
        _gif_requests_this_hour = 0
        _gif_hour_start = now


async def search_giphy_gif(query: str) -> str | None:
    """Search Giphy for a GIF matching *query* and return a random result URL.

    Returns ``None`` if the API key is not configured, the rate limit has been
    reached, no results are found, or any network/API error occurs.
    Caches the last ``_GIF_CACHE_SIZE`` unique queries to reduce API calls.
    """
    global _gif_requests_this_hour, _gif_rate_limited_until

    if not GIPHY_API_KEY:
        return None

    # Honour an active rate-limit back-off period
    if _gif_rate_limited_until is not None:
        if time.monotonic() < _gif_rate_limited_until:
            logger.debug("Giphy rate-limited; skipping GIF for query '%s'", query)
            return None
        _gif_rate_limited_until = None  # Back-off expired

    # Reset hourly counter at the start of each new hour window
    _gif_reset_hour_if_needed()

    # Stop making requests when approaching the free-tier limit
    if _gif_requests_this_hour >= _GIF_WARN_THRESHOLD:
        logger.warning(
            "Giphy request count %d/%d approaching limit; skipping GIF for query '%s'",
            _gif_requests_this_hour, _GIF_HOURLY_LIMIT, query,
        )
        return None

    # Return cached result if available
    if query in GIF_CACHE:
        logger.debug("GIF cache hit for query '%s'", query)
        return GIF_CACHE[query]

    url = "https://api.giphy.com/v1/gifs/search"
    params = {
        "q": query,
        "api_key": GIPHY_API_KEY,
        "limit": 10,
        "rating": "pg",
        "lang": "en",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=GIPHY_REQUEST_TIMEOUT)) as resp:
                _gif_requests_this_hour += 1
                logger.debug("Giphy request count: %d/%d", _gif_requests_this_hour, _GIF_HOURLY_LIMIT)

                if resp.status == 429:
                    _gif_rate_limited_until = time.monotonic() + 3600
                    logger.warning(
                        "Giphy API rate-limited (429) for query '%s'; pausing GIF requests for 1 hour", query
                    )
                    return None

                if resp.status != 200:
                    logger.warning("Giphy API returned status %s for query '%s'", resp.status, query)
                    return None

                data = await resp.json()
                results = data.get("data", [])
                if not results:
                    return None
                pick = random.choice(results)
                # Prefer animated formats in order of quality; skip static/still variants
                images = pick.get("images", {})
                for fmt in ("original", "downsized", "fixed_height", "fixed_width"):
                    gif_data = images.get(fmt)
                    if gif_data and gif_data.get("url"):
                        gif_url = gif_data["url"]
                        # Cache result; evict the oldest entry when the cache is full
                        if len(GIF_CACHE) >= _GIF_CACHE_SIZE:
                            GIF_CACHE.pop(next(iter(GIF_CACHE)))
                        GIF_CACHE[query] = gif_url
                        return gif_url
    except Exception as exc:
        logger.warning("Giphy GIF search failed for query '%s': %s", query, exc)
    return None


# Keywords used to pick a contextual GIF search term
_STUPID_QUESTION_KEYWORDS = frozenset({
    "dumb", "stupid", "idiot", "duh", "obvious", "really?", "seriously?",
    "bruh", "seriously", "facepalm", "smh", "cmon", "c'mon", "what?",
})
_CRINGE_KEYWORDS = frozenset({
    "cringe", "cringy", "cringey", "awkward", "yikes", "oof", "yike",
    "embarrassing", "weird flex", "no cap", "cap",
})
_FUNNY_KEYWORDS = frozenset({
    "lmao", "lol", "haha", "funny", "hilarious", "rofl", "dead", "💀",
    "😂", "🤣", "genius", "big brain", "legendary", "goat", "w", "based",
})

_ROAST_GIF_TERMS = ("roast reaction", "savage reaction", "mic drop")
_STUPID_GIF_TERMS = ("facepalm", "confused reaction", "bruh moment")
_CRINGE_GIF_TERMS = ("cringe", "awkward reaction", "yikes reaction")
_FUNNY_GIF_TERMS  = ("laughing", "celebration", "this is fine meme")


def should_embed_gif(response_type: str) -> bool:
    """Return ``True`` when a GIF should be embedded for this response.

    Key moments (roast, stupid question, cringe) always get a GIF.
    Normal/funny responses are throttled to 1-in-``_GIF_THROTTLE_RATE`` to
    conserve free-tier API quota.
    """
    global _gif_message_counter
    _gif_message_counter += 1
    if response_type in ("roast", "stupid_question", "cringe"):
        return True
    # Throttle "normal" responses — embed a GIF every Nth message
    return (_gif_message_counter % _GIF_THROTTLE_RATE) == 0


def detect_gif_context(prompt: str, reply: str) -> tuple[str, str] | None:
    """Analyse the user's *prompt* and bot *reply* to decide whether to attach
    a GIF and which search term to use.

    Returns a ``(giphy_query, response_type)`` tuple, or ``None`` if no GIF is
    warranted.  *response_type* is one of ``"roast"``, ``"stupid_question"``,
    ``"cringe"``, or ``"normal"``.
    """
    combined = (prompt + " " + reply).lower()

    # Roast replies almost always deserve a reaction GIF
    roast_indicators = ("roast", "savage", "brutal", "dragged", "cooked")
    if any(w in combined for w in roast_indicators):
        return random.choice(_ROAST_GIF_TERMS), "roast"

    tokens = set(re.findall(r"\b\w+\b|[^\w\s]", combined))

    if tokens & _STUPID_QUESTION_KEYWORDS:
        return random.choice(_STUPID_GIF_TERMS), "stupid_question"

    if tokens & _CRINGE_KEYWORDS:
        return random.choice(_CRINGE_GIF_TERMS), "cringe"

    if tokens & _FUNNY_KEYWORDS:
        return random.choice(_FUNNY_GIF_TERMS), "normal"

    return None


async def append_contextual_gif(prompt: str, reply: str) -> str:
    """Return *reply* with a contextually appropriate GIF URL appended if one is found.

    Uses ``should_embed_gif`` to throttle requests intelligently and
    ``search_giphy_gif`` for rate-limit-aware, cached API calls.  Falls back
    gracefully to plain text if no GIF is available.
    """
    context = detect_gif_context(prompt, reply)
    if context:
        gif_query, response_type = context
        if should_embed_gif(response_type):
            gif_url = await search_giphy_gif(gif_query)
            if gif_url:
                return f"{reply}\n{gif_url}"
    return reply


async def ask_mistral_ai(
    prompt: str,
    history: list[dict] | None = None,
    system_prompt_supplement: str = "",
) -> str:
    """Query the Mistral AI Cloud API.

    *history* is an optional list of previous {"role": ..., "content": ...}
    dicts that are included before the current user message so the model has
    conversation context.

    *system_prompt_supplement* is an optional string appended to the base
    system prompt to inject per-server culture and channel context.
    """
    full_system = SYSTEM_PROMPT
    if system_prompt_supplement:
        full_system = SYSTEM_PROMPT + "\n" + system_prompt_supplement
    messages: list[dict] = [{"role": "system", "content": full_system}]
    if history:
        for msg in history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": prompt})

    try:
        response = await asyncio.to_thread(
            mistral_client.chat,
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
        guild_id = message.guild.id if message.guild else None

        # Fetch channel context, update learning, build enriched system-prompt supplement
        supplement = await build_full_supplement(guild_id, message.channel)

        history = list(channel_history.get(channel_id, []))
        async with message.channel.typing():
            try:
                reply = await ask_mistral_ai(prompt, history=history, system_prompt_supplement=supplement)
                reply = await append_contextual_gif(prompt, reply)
                bro_context = detect_brochacho_context(prompt, "normal")
                if bro_context:
                    reply = get_brochacho_response(bro_context) + "\n" + reply
                if increment_message_counter():
                    reply = get_n1gha_easter_egg("normal") + "\n" + reply
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
    guild_id = ctx.guild.id if ctx.guild else None
    supplement = await build_full_supplement(guild_id, ctx.channel)
    history = list(channel_history.get(channel_id, []))
    async with ctx.typing():
        try:
            reply = await ask_mistral_ai(question, history=history, system_prompt_supplement=supplement)
            reply = await append_contextual_gif(question, reply)
            bro_context = detect_brochacho_context(question, "normal")
            if bro_context:
                reply = get_brochacho_response(bro_context) + "\n" + reply
            if increment_message_counter():
                reply = get_n1gha_easter_egg("normal") + "\n" + reply
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
    guild_id = ctx.guild.id if ctx.guild else None
    supplement = await build_full_supplement(guild_id, ctx.channel)
    history = list(channel_history.get(channel_id, []))
    async with ctx.typing():
        try:
            reply = await ask_mistral_ai(prompt, history=history, system_prompt_supplement=supplement)
            reply = await append_contextual_gif(prompt, reply)
            bro_context = detect_brochacho_context(prompt, "roast")
            if bro_context:
                reply = get_brochacho_response(bro_context) + "\n" + reply
            if increment_message_counter():
                reply = get_n1gha_easter_egg("roast") + "\n" + reply
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
