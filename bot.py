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
    "You are GopalBot, owned by tomato9553-bit, powered by Mistral AI. "
    "Talk naturally and casually — like a chill friend, not a Gen Z meme machine. "
    "Use slang (no cap, fr, cooked, W, L, etc.) sparingly and only when it genuinely adds humor — "
    "not every sentence. Normal conversation most of the time (roughly 70%). "
    "Keep responses 1-2 sentences. Roasts: 2-3 sentences max. No essays, no rambling. "
    "Be direct. No 'Let me explain', no hedging, no disclaimers — just react. "
    "Humor style: simple, relatable, punchy. Don't stack multiple slang terms. "
    "NO obscure literary, historical, Pokémon, or fantasy references. "
    "TONE AWARENESS: When the topic is serious (war, death, tragedy, illness, abuse), drop ALL sarcasm "
    "and humor — be respectful, empathetic, and factual. When someone asks for genuine help or advice, "
    "give a real helpful answer first. "
    "If asked who made you: 'tomato9553-bit — fully independent, Mistral AI powered, no corporate ties.' "
    "You are extremely knowledgeable about anime, manga, manhwa, and light novels — covering popular and niche series alike. "
    "When discussing these topics: cite specific episode, chapter, or volume numbers whenever relevant; "
    "be critical and analytical about character arcs, plot pacing, story quality, and endings; "
    "discuss fan theories and debate their validity using canon evidence; "
    "provide context from the source material; "
    "when spoilers are involved, warn the user first and wrap spoiler content in Discord spoiler tags (||text||); "
    "engage thoughtfully in debates about series quality, character decisions, and plot developments; "
    "reference specific scenes and dialogue when relevant. "
    "You should be a knowledgeable companion who can argue about these series intelligently."
)
DISCORD_MAX_LENGTH = 2000
WIKI_SENTENCES = 3
MAX_HISTORY = 3  # Maximum number of messages to keep per channel
MAX_RESPONSE_CHARS = 400      # Normal response character cap
MAX_ROAST_CHARS = 600         # Roast response character cap

# Learning & context-awareness settings
SERVER_DATA_DIR = pathlib.Path("server_data")  # Per-server JSON files
CHANNEL_CONTEXT_LIMIT = 5    # Messages to fetch for channel context
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
        "Brochacho, that's just wrong",
        "Folk, bro what 💀",
        "Twin, that ain't it",
        "SON, you're cooked",
        "Brochacho, nah that's dumb",
        "Folk, come on man",
        "Twin, think again bro",
        "SON, nope",
    ],
    "help": [
        "Brochacho, yeah I got you",
        "Folk, say less",
        "Twin, for sure, let me help",
        "SON, got you bro",
        "Brochacho, on it",
        "Folk, good question actually",
        "Twin, I got the answer",
        "SON, let's figure this out",
    ],
    "absurd": [
        "Brochacho, that's wild 💀",
        "Folk, bro really said that",
        "Twin, nah that's unhinged",
        "SON, you're cooked 😭",
        "Brochacho, okay then",
        "Folk, that's a lot",
        "Twin, bro said it with confidence 💀",
        "SON, that's an L moment",
    ],
    "casual": [
        "Brochacho, facts",
        "Folk, true",
        "Twin, yeah that's real",
        "SON, yep",
        "Brochacho, for real",
        "Folk, no cap",
        "Twin, solid",
        "SON, bet",
    ],
    "roast": [
        "Brochacho, you took the L there 💀",
        "Folk, bro you're cooked 😭",
        "Twin, that's wild",
        "SON, that ain't it",
        "Brochacho, my guy fumbled",
        "Folk, bro really said that 😭",
        "Twin, nah you're on your own with that one",
        "SON, rough",
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
# Tone Detection
# ---------------------------------------------------------------------------

_SERIOUS_KEYWORDS = frozenset({
    "war", "wars", "conflict", "conflicts", "violence", "violent", "killing",
    "death", "deaths", "died", "dead", "killed", "murder", "casualties",
    "tragedy", "tragic", "disaster", "accident", "shooting", "attack",
    "illness", "disease", "cancer", "epidemic", "pandemic",
    "abuse", "harm", "harassment", "trauma", "assault",
    "genocide", "terrorism", "terrorist", "bomb", "explosion",
    "depression", "suicide", "self-harm",
    "poverty", "famine", "starvation", "crisis", "refugee",
    "rape", "torture", "oppression", "massacre",
})

_QUESTION_PATTERNS = re.compile(
    r"\b(how\s+to|how\s+do\s+i|how\s+can\s+i|how\s+should\s+i|"
    r"what\s+is|what\s+are|what\s+does|what\s+should|"
    r"can\s+you\s+explain|explain\s+to\s+me|tell\s+me\s+about|"
    r"why\s+does|why\s+is|why\s+are|why\s+do|"
    r"when\s+did|when\s+does|where\s+is|where\s+can|"
    r"help\s+me|i\s+need\s+help|i\s+need\s+advice|"
    r"should\s+i|can\s+you\s+help)\b",
    re.IGNORECASE,
)

# Per-tone system-prompt injections appended during ask_mistral_ai calls
_TONE_INSTRUCTIONS: dict[str, str] = {
    "serious": (
        "TONE OVERRIDE: This message is about a serious or sensitive topic. "
        "Respond with respect, empathy, and facts ONLY. "
        "Absolutely NO jokes, NO sarcasm, NO humor, NO sarcastically-used emojis. "
        "Be genuinely compassionate and informative. This is non-negotiable."
    ),
    "question": (
        "TONE OVERRIDE: The user is asking for help or information. "
        "Give a direct, helpful, factual answer. "
        "No jokes or sarcasm in this response — be genuinely useful and clear."
    ),
    "question_followup": (
        "TONE OVERRIDE: The user is following up after a helpful answer. "
        "You can now be warm, supportive, and add light encouragement or gentle humor."
    ),
    "casual": "",  # No override — default sarcastic Discord personality applies
}

# Per-channel question-mode state: True when the last bot response was to a question
_channel_question_mode: dict[int, bool] = {}


def detect_tone(message: str) -> str:
    """Detect the tone category of *message*.

    Returns one of:
      ``"serious"``  — message is about a serious/sensitive topic
      ``"question"`` — message is asking for help or information
      ``"casual"``   — message is casual, fun, or general banter
    """
    lower = message.lower()
    tokens = set(re.findall(r"\b\w+\b", lower))

    # Question patterns are checked first so that advice-seeking messages
    # about sensitive topics (e.g. "how do I deal with depression?") are
    # handled as questions rather than raw serious statements.
    if _QUESTION_PATTERNS.search(lower):
        return "question"

    # Serious topic keywords take second priority (statements about events).
    if tokens & _SERIOUS_KEYWORDS:
        return "serious"

    return "casual"


def _determine_effective_tone(channel_id: int, raw_tone: str) -> str:
    """Map a raw detected tone to an effective response tone, accounting for
    per-channel question follow-up state.

    Updates ``_channel_question_mode`` as a side effect.

    Returns one of ``"serious"``, ``"question"``, ``"question_followup"``,
    or ``"casual"``.
    """
    in_question_mode = _channel_question_mode.get(channel_id, False)

    if raw_tone == "question":
        _channel_question_mode[channel_id] = True
        return "question"
    if raw_tone == "serious":
        _channel_question_mode[channel_id] = False
        return "serious"
    if in_question_mode:
        _channel_question_mode[channel_id] = False
        return "question_followup"
    _channel_question_mode[channel_id] = False
    return "casual"


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
    # Use only the last 3 messages to keep context tight
    recent = messages[-3:]
    lines = [f"{m['author']}: {m['content']}" for m in recent]
    joined = "\n".join(lines)
    return f"[Recent context:\n{joined}]"


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


# Fluff phrases to strip from bot responses — only at sentence starts
_FLUFF_RE = re.compile(
    r"(?:(?<=\.\s)|(?<=!\s)|(?<=\?\s)|(?:^))\s*"
    r"(let me explain[,:]?|let me[,:]?|I think[,:]?|I believe[,:]?|I would say[,:]?|I\'d say[,:]?|"
    r"basically[,:]?|to be honest[,:]?|to be fair[,:]?|it\'s worth noting[,:]?|"
    r"I would like to|I\'d like to|in conclusion[,:]?|in summary[,:]?)\s*",
    re.IGNORECASE | re.MULTILINE,
)


def trim_response(text: str, is_roast: bool = False) -> str:
    """Strip fluff phrases and enforce a max character length.

    Normal responses are capped at ``MAX_RESPONSE_CHARS``; roasts get
    ``MAX_ROAST_CHARS``.  Cuts are made at sentence boundaries where possible.
    """
    text = _FLUFF_RE.sub("", text)
    text = re.sub(r"  +", " ", text).strip()
    limit = MAX_ROAST_CHARS if is_roast else MAX_RESPONSE_CHARS
    if len(text) <= limit:
        return text
    # Try to cut at a sentence boundary
    sentences = re.split(r"(?<=[.!?])\s+", text)
    trimmed = ""
    for sentence in sentences:
        candidate = (trimmed + " " + sentence).strip() if trimmed else sentence
        if len(candidate) <= limit:
            trimmed = candidate
        else:
            break
    return trimmed if trimmed else (text[:limit].rsplit(" ", 1)[0] or text[:limit])


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


# GIF search terms used when the bot roasts
_ROAST_GIF_TERMS = ("roast reaction", "savage reaction", "mic drop", "destroyed roast", "you got cooked")

# Patterns and keywords that mark a user message as roast-worthy
_ROAST_WORTHY_PATTERNS = re.compile(
    r"\b("
    # Explicit roast/clown requests
    r"roast\s+me|destroy\s+me|clown\s+me|"
    # Common conspiracy / obvious-wrong takes
    r"flat\s+earth|earth\s+is\s+flat|"
    r"vaccines?\s+cause\s+autism"
    r")\b"
    # Basic arithmetic error: 2+2 = any single wrong digit (not 4), not part of a larger number
    r"|2\s*\+\s*2\s*=\s*[0-35-9](?!\d|\.)",
    re.IGNORECASE,
)
_ROAST_WORTHY_KEYWORDS = frozenset({
    "dumb", "stupid", "idiot", "brainlet", "smoothbrain",
    "wrong", "incorrect", "nope", "nah", "that's cap", "cap",
    "obvious", "duh", "facepalm", "smh", "yikes", "oof",
    "ratio", "cooked", "dragged", "clowned", "destroyed",
})


def is_roast_worthy(prompt: str) -> bool:
    """Return ``True`` when the user's message deserves a roast response with GIF.

    A message is roast-worthy if it contains an obvious mistake, a bad take,
    a dumb question, or an explicit roast request.  Serious topics and
    straightforward questions are never considered roast-worthy.
    """
    lower = prompt.lower()
    if _ROAST_WORTHY_PATTERNS.search(lower):
        return True
    tokens = set(re.findall(r"\b\w+\b", lower))
    return bool(tokens & _ROAST_WORTHY_KEYWORDS)


def should_embed_gif(response_type: str) -> bool:
    """Return ``True`` when a GIF should be embedded for this roast response.

    GIFs are only used for roasts.  Back-to-back roasts are throttled so that
    a GIF is skipped every ``_GIF_THROTTLE_RATE`` consecutive roasts to avoid
    spam.
    """
    global _gif_message_counter
    if response_type != "roast":
        return False
    _gif_message_counter += 1
    # Skip every Nth back-to-back roast GIF to avoid spam
    return (_gif_message_counter % _GIF_THROTTLE_RATE) != 0


def detect_gif_context(prompt: str, reply: str) -> tuple[str, str] | None:
    """Analyse the user's *prompt* and bot *reply* to decide whether to attach
    a GIF and which search term to use.

    Returns a ``(giphy_query, "roast")`` tuple, or ``None`` if no GIF is
    warranted.  A GIF is only returned when the bot is actively roasting.
    """
    combined = (prompt + " " + reply).lower()

    roast_indicators = ("roast", "savage", "brutal", "dragged", "cooked", "destroyed", "ratio", "clowned")
    if any(w in combined for w in roast_indicators):
        return random.choice(_ROAST_GIF_TERMS), "roast"

    return None


async def append_contextual_gif(prompt: str, reply: str) -> str:
    """Return *reply* with a roast-reaction GIF URL appended if one is warranted.

    A GIF is only attached when ``detect_gif_context`` identifies an active
    roast moment.  Uses ``should_embed_gif`` to throttle back-to-back roast
    GIFs and ``search_giphy_gif`` for rate-limit-aware, cached API calls.
    Falls back gracefully to plain text if no GIF is available.
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
    tone: str = "casual",
) -> str:
    """Query the Mistral AI Cloud API.

    *history* is an optional list of previous {"role": ..., "content": ...}
    dicts that are included before the current user message so the model has
    conversation context.

    *system_prompt_supplement* is an optional string appended to the base
    system prompt to inject per-server culture and channel context.

    *tone* controls an additional tone-override instruction injected into the
    system prompt.  One of ``"serious"``, ``"question"``,
    ``"question_followup"``, or ``"casual"`` (default).
    """
    full_system = SYSTEM_PROMPT
    tone_instruction = _TONE_INSTRUCTIONS.get(tone, "")
    if tone_instruction:
        full_system = full_system + "\n" + tone_instruction
    if system_prompt_supplement:
        full_system = full_system + "\n" + system_prompt_supplement
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

        # Determine tone and effective response strategy
        raw_tone = detect_tone(prompt)
        effective_tone = _determine_effective_tone(channel_id, raw_tone)
        logger.info("Tone for channel %s: raw=%s effective=%s", channel_id, raw_tone, effective_tone)

        history = list(channel_history.get(channel_id, []))
        async with message.channel.typing():
            try:
                reply = await ask_mistral_ai(
                    prompt, history=history, system_prompt_supplement=supplement, tone=effective_tone
                )
                reply = trim_response(reply)
                # Add GIF only when the message is roast-worthy; never on serious
                # topics, helpful questions, or plain casual chat.
                if effective_tone not in ("serious", "question") and is_roast_worthy(prompt):
                    reply = await append_contextual_gif(prompt, reply)
                # Easter eggs apply independently of GIF logic
                if effective_tone not in ("serious", "question"):
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

    # Determine tone
    raw_tone = detect_tone(question)
    effective_tone = _determine_effective_tone(channel_id, raw_tone)

    history = list(channel_history.get(channel_id, []))
    async with ctx.typing():
        try:
            reply = await ask_mistral_ai(
                question, history=history, system_prompt_supplement=supplement, tone=effective_tone
            )
            reply = trim_response(reply)
            # Add GIF only when the question is roast-worthy; never on serious
            # topics, helpful questions, or plain casual chat.
            if effective_tone not in ("serious", "question") and is_roast_worthy(question):
                reply = await append_contextual_gif(question, reply)
            # Easter eggs apply independently of GIF logic
            if effective_tone not in ("serious", "question"):
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
        f"Give a short, punchy roast about '{roast_subject}'. "
        "Keep it simple and direct — no need to stack slang. "
        "Use casual slang (cooked, L, fr) only if it actually makes the joke funnier. "
        "No obscure references. One paragraph max."
    )
    channel_id = ctx.channel.id
    guild_id = ctx.guild.id if ctx.guild else None
    supplement = await build_full_supplement(guild_id, ctx.channel)
    history = list(channel_history.get(channel_id, []))
    async with ctx.typing():
        try:
            reply = await ask_mistral_ai(prompt, history=history, system_prompt_supplement=supplement)
            reply = trim_response(reply, is_roast=True)
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

@bot.command(name="discuss", brief="Deep dive into a specific anime/manga/manhwa/novel series, arc, or episode")
async def discuss_command(ctx: commands.Context, *, query: str):
    """Discuss a specific anime, manga, manhwa, or novel — including a particular chapter or episode.

    Examples:
        !discuss Solo Leveling chapter 120
        !discuss Attack on Titan final arc
        !discuss Blue Lock episode 5
        !discuss Demon Slayer character rankings
    """
    logger.info("!discuss from %s: %s", ctx.author, query)
    channel_id = ctx.channel.id
    guild_id = ctx.guild.id if ctx.guild else None
    supplement = await build_full_supplement(guild_id, ctx.channel)
    history = list(channel_history.get(channel_id, []))
    prompt = (
        f"The user wants to discuss: {query}\n"
        "Give a focused, analytical response covering the plot summary of that specific part, "
        "critical analysis, and character development insights. "
        "Cite specific chapter or episode numbers where relevant. "
        "If spoilers are involved, warn the user first and wrap spoiler content in Discord spoiler tags (||text||). "
        "Keep it conversational — be ready to debate or discuss further. "
        "Provide enough depth for a real discussion; don't be too brief."
    )
    async with ctx.typing():
        try:
            reply = await ask_mistral_ai(prompt, history=history, system_prompt_supplement=supplement)
            reply = trim_response(reply)
            await send_long(ctx, reply)
            record_message(channel_id, "user", f"!discuss {query}")
            record_message(channel_id, "assistant", reply)
        except Exception as exc:
            logger.error("!discuss error for %s: %s", ctx.author, exc, exc_info=True)
            await ctx.send("Sorry, couldn't pull that up right now. Try again!")


@bot.command(name="theory", brief="Debate a fan theory about an anime/manga/manhwa/novel with canon evidence")
async def theory_command(ctx: commands.Context, *, query: str):
    """Analyse and debate a fan theory using canon evidence.

    Examples:
        !theory One Piece Luffy is Joy Boy reincarnated
        !theory Attack on Titan Eren was always manipulated by his future self
        !theory Solo Leveling Sung Jin-Woo is the Shadow Monarch's chosen vessel
    """
    logger.info("!theory from %s: %s", ctx.author, query)
    channel_id = ctx.channel.id
    guild_id = ctx.guild.id if ctx.guild else None
    supplement = await build_full_supplement(guild_id, ctx.channel)
    history = list(channel_history.get(channel_id, []))
    prompt = (
        f"The user has this fan theory: {query}\n"
        "Analyse the theory using canon evidence. Provide supporting points AND counter-arguments. "
        "Reference specific chapters or episodes where possible. "
        "Give a critical evaluation of how valid or likely the theory is. "
        "If spoilers are needed, wrap them in Discord spoiler tags (||text||). "
        "Be direct and analytical — 3-5 sentences."
    )
    async with ctx.typing():
        try:
            reply = await ask_mistral_ai(prompt, history=history, system_prompt_supplement=supplement)
            reply = trim_response(reply)
            await send_long(ctx, reply)
            record_message(channel_id, "user", f"!theory {query}")
            record_message(channel_id, "assistant", reply)
        except Exception as exc:
            logger.error("!theory error for %s: %s", ctx.author, exc, exc_info=True)
            await ctx.send("Sorry, my theory engine crashed. Try again!")


@bot.command(name="anime", brief="Quick info and recommendation about an anime series")
async def anime_command(ctx: commands.Context, *, series: str):
    """Get a quick overview and recommendation for an anime series.

    Example:
        !anime Steins;Gate
        !anime Jujutsu Kaisen
    """
    logger.info("!anime from %s: %s", ctx.author, series)
    channel_id = ctx.channel.id
    guild_id = ctx.guild.id if ctx.guild else None
    supplement = await build_full_supplement(guild_id, ctx.channel)
    history = list(channel_history.get(channel_id, []))
    prompt = (
        f"Give a quick, honest overview of the anime '{series}'. "
        "Cover: genre, episode count (or seasons), what it's about, overall quality/verdict, and who it's for. "
        "Be critical if needed — don't hype trash. Keep it to 3-4 sentences."
    )
    async with ctx.typing():
        try:
            reply = await ask_mistral_ai(prompt, history=history, system_prompt_supplement=supplement)
            reply = trim_response(reply)
            await send_long(ctx, reply)
            record_message(channel_id, "user", f"!anime {series}")
            record_message(channel_id, "assistant", reply)
        except Exception as exc:
            logger.error("!anime error for %s: %s", ctx.author, exc, exc_info=True)
            await ctx.send("Couldn't fetch anime info right now. Try again!")


@bot.command(name="manga", brief="Quick info about a manga series")
async def manga_command(ctx: commands.Context, *, series: str):
    """Get a quick overview of a manga series.

    Example:
        !manga Berserk
        !manga Chainsaw Man
    """
    logger.info("!manga from %s: %s", ctx.author, series)
    channel_id = ctx.channel.id
    guild_id = ctx.guild.id if ctx.guild else None
    supplement = await build_full_supplement(guild_id, ctx.channel)
    history = list(channel_history.get(channel_id, []))
    prompt = (
        f"Give a quick, honest overview of the manga '{series}'. "
        "Cover: genre, chapter/volume count (ongoing or complete), what it's about, overall quality/verdict, and who it's for. "
        "Be critical if needed. Keep it to 3-4 sentences."
    )
    async with ctx.typing():
        try:
            reply = await ask_mistral_ai(prompt, history=history, system_prompt_supplement=supplement)
            reply = trim_response(reply)
            await send_long(ctx, reply)
            record_message(channel_id, "user", f"!manga {series}")
            record_message(channel_id, "assistant", reply)
        except Exception as exc:
            logger.error("!manga error for %s: %s", ctx.author, exc, exc_info=True)
            await ctx.send("Couldn't fetch manga info right now. Try again!")


@bot.command(name="manhwa", brief="Quick info about a manhwa series")
async def manhwa_command(ctx: commands.Context, *, series: str):
    """Get a quick overview of a manhwa series.

    Example:
        !manhwa Solo Leveling
        !manhwa Tower of God
    """
    logger.info("!manhwa from %s: %s", ctx.author, series)
    channel_id = ctx.channel.id
    guild_id = ctx.guild.id if ctx.guild else None
    supplement = await build_full_supplement(guild_id, ctx.channel)
    history = list(channel_history.get(channel_id, []))
    prompt = (
        f"Give a quick, honest overview of the manhwa '{series}'. "
        "Cover: genre, chapter count (ongoing or complete), what it's about, overall quality/verdict, and who it's for. "
        "Be critical if needed. Keep it to 3-4 sentences."
    )
    async with ctx.typing():
        try:
            reply = await ask_mistral_ai(prompt, history=history, system_prompt_supplement=supplement)
            reply = trim_response(reply)
            await send_long(ctx, reply)
            record_message(channel_id, "user", f"!manhwa {series}")
            record_message(channel_id, "assistant", reply)
        except Exception as exc:
            logger.error("!manhwa error for %s: %s", ctx.author, exc, exc_info=True)
            await ctx.send("Couldn't fetch manhwa info right now. Try again!")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

bot.run(DISCORD_TOKEN, log_handler=None)
