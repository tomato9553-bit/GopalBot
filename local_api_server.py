"""Local API server for GopalBot — runs on the owner's Victus PC (RTX 3050).

This server acts as a bridge between the Railway-hosted Discord bot and a local
Ollama instance running Mistral 7B.  Start it before using the Discord bot so
that GopalBot can serve AI responses from your own hardware with full privacy.

Usage
-----
    python local_api_server.py

The server listens on http://0.0.0.0:8000 by default.
"""

from flask import Flask, request, jsonify
import requests
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LocalAPIServer")

app = Flask(__name__)

OLLAMA_URL = "http://localhost:11434"
MISTRAL_MODEL = "mistral"
DEFAULT_SYSTEM_PROMPT = (
    "You are GopalBot, created and owned by tomato9553-bit. "
    "You are completely independent with no corporate affiliation. "
    "You use Mistral — an independent model by Mistral AI (not Meta). "
    "Be witty, unfiltered, adapt to server culture, show empathy, handle politics nuancely. "
    "Talk naturally (short messages unless asked for paragraphs)."
)


@app.route("/api/generate", methods=["POST"])
def generate():
    """Receive a prompt from the Railway bot, call Ollama, return the reply."""
    try:
        data = request.get_json(force=True) or {}
        prompt = data.get("prompt", "")
        system_prompt = data.get("system", DEFAULT_SYSTEM_PROMPT)

        if not prompt:
            return jsonify({"status": "error", "message": "No prompt provided"}), 400

        logger.info("Received prompt (first 80 chars): %s", prompt[:80])

        ollama_response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MISTRAL_MODEL,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
            },
            timeout=60,
        )

        if ollama_response.status_code == 200:
            reply = ollama_response.json().get("response", "")
            logger.info("Ollama replied successfully.")
            return jsonify({"response": reply, "status": "success"})
        else:
            logger.error("Ollama returned status %s", ollama_response.status_code)
            return jsonify({"status": "error", "message": "Ollama error"}), 500

    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Ollama at %s — is it running?", OLLAMA_URL)
        return jsonify({"status": "error", "message": "Ollama is not running"}), 503
    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out.")
        return jsonify({"status": "error", "message": "Ollama timed out"}), 504
    except Exception as exc:
        logger.error("Unexpected error: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@app.route("/health", methods=["GET"])
def health():
    """Simple health-check endpoint."""
    return jsonify({"status": "ok", "model": MISTRAL_MODEL})


if __name__ == "__main__":
    print("=" * 60)
    print("GopalBot Local API Server")
    print("=" * 60)
    print(f"Listening on  : http://0.0.0.0:8000")
    print(f"Ollama target : {OLLAMA_URL}")
    print(f"Model         : {MISTRAL_MODEL}")
    print("=" * 60)
    print("Make sure Ollama is running before starting this server.")
    print("  ollama serve   (if not already running as a service)")
    print("  ollama pull mistral   (first-time setup only)")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8000, debug=False)
