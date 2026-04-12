"""Local API server for GopalBot — runs on the owner's Victus PC (RTX 3050).

This server acts as a bridge between the Railway-hosted Discord bot and a local
Ollama instance running Phi 2.7B (optimized for RTX 3050).

Start it before using the Discord bot so that GopalBot can serve AI responses 
from your own hardware with full privacy.

Usage
-----
    python local_api_server.py

The server listens on http://0.0.0.0:8000 by default.
"""

from flask import Flask, request, jsonify
import requests
import logging
import os

# Configure logging with timestamps and levels
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LocalAPIServer")

app = Flask(__name__)

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
PHI_MODEL = "phi"
TIMEOUT_SECONDS = 120  # Increased from 60 to 120 for RTX 3050 performance

DEFAULT_SYSTEM_PROMPT = (
    "You are GopalBot, created and owned by tomato9553-bit. "
    "You are completely independent with no corporate affiliation. "
    "You use Phi — an independent model by Microsoft (not Meta/Mistral). "
    "Be witty, unfiltered, adapt to server culture, show empathy, handle politics nuancely. "
    "Talk naturally (short messages unless asked for paragraphs). "
    "You run on the creator's Victus PC with RTX 3050 for complete privacy."
)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint to verify API is running and Ollama is accessible."""
    try:
        ollama_health = requests.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=5
        )
        if ollama_health.status_code == 200:
            return jsonify({
                "status": "ok",
                "model": PHI_MODEL,
                "ollama": "connected",
                "timeout": TIMEOUT_SECONDS
            }), 200
        else:
            return jsonify({
                "status": "warning",
                "message": "Ollama not responding properly",
                "ollama_status": ollama_health.status_code
            }), 503
    except Exception as e:
        logger.warning(f"Health check failed: {e}")
        return jsonify({
            "status": "error",
            "message": "Ollama is offline",
            "error": str(e)
        }), 503


@app.route("/api/generate", methods=["POST"])
def generate():
    """
    Receive a prompt from the Railway Discord bot, call Ollama with Phi model,
    return the AI-generated reply.
    
    Expected JSON input:
    {
        "prompt": "your question here",
        "system": "optional custom system prompt"
    }
    """
    try:
        # Parse incoming request
        data = request.get_json(force=True) or {}
        prompt = data.get("prompt", "").strip()
        system_prompt = data.get("system", DEFAULT_SYSTEM_PROMPT)

        # Validate prompt
        if not prompt:
            logger.warning("Empty prompt received")
            return jsonify({
                "status": "error",
                "message": "No prompt provided"
            }), 400

        logger.info(f"Received prompt ({len(prompt)} chars): {prompt[:80]}...")

        # Call Ollama with Phi model
        logger.info(f"Calling Ollama at {OLLAMA_URL} with model={PHI_MODEL}, timeout={TIMEOUT_SECONDS}s")
        
        ollama_response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": PHI_MODEL,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "temperature": 0.7,  # Balanced creativity
                "top_p": 0.9,        # Sampling parameter
                "top_k": 40,         # Sampling parameter
            },
            timeout=TIMEOUT_SECONDS,  # 120 seconds for RTX 3050
        )

        # Handle Ollama response
        if ollama_response.status_code == 200:
            response_data = ollama_response.json()
            reply = response_data.get("response", "").strip()
            
            if not reply:
                logger.warning("Ollama returned empty response")
                return jsonify({
                    "status": "error",
                    "message": "Model returned empty response"
                }), 500
            
            logger.info(f"✓ Ollama replied successfully ({len(reply)} chars)")
            return jsonify({
                "response": reply,
                "status": "success",
                "model": PHI_MODEL,
                "tokens": response_data.get("eval_count", 0)
            }), 200
        else:
            logger.error(f"Ollama error: HTTP {ollama_response.status_code}")
            logger.error(f"Response: {ollama_response.text[:200]}")
            return jsonify({
                "status": "error",
                "message": f"Ollama returned HTTP {ollama_response.status_code}"
            }), 502

    except requests.exceptions.Timeout:
        logger.error(f"Ollama request timed out after {TIMEOUT_SECONDS}s")
        logger.error("Possible causes: Phi model is still loading, RTX 3050 is busy, or prompt is too long")
        return jsonify({
            "status": "error",
            "message": f"Ollama timed out after {TIMEOUT_SECONDS}s. Phi might still be warming up on RTX 3050.",
            "timeout": TIMEOUT_SECONDS
        }), 504

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot connect to Ollama at {OLLAMA_URL}")
        logger.error("Make sure Ollama is running: 'ollama serve'")
        return jsonify({
            "status": "error",
            "message": "Cannot reach Ollama. Is it running?",
            "ollama_url": OLLAMA_URL
        }), 503

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {type(e).__name__}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Request failed: {str(e)}"
        }), 500

    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "error": str(e)
        }), 500


@app.route("/api/models", methods=["GET"])
def get_models():
    """List available models in Ollama."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Could not fetch models from Ollama"
            }), 502
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 503


if __name__ == "__main__":
    print("=" * 70)
    print("  GopalBot Local API Server (RTX 3050 Optimized)")
    print("=" * 70)
    print(f"  API Server       : http://0.0.0.0:8000")
    print(f"  Ollama Target    : {OLLAMA_URL}")
    print(f"  Model            : {PHI_MODEL}")
    print(f"  Request Timeout  : {TIMEOUT_SECONDS} seconds")
    print(f"  Owner            : tomato9553-bit")
    print(f"  Status           : INDEPENDENT (No Meta/Corporate Ties)")
    print("=" * 70)
    print("")
    print("  ✓ Make sure Ollama is running:")
    print("    ollama serve")
    print("")
    print("  ✓ First-time setup only:")
    print("    ollama pull phi")
    print("")
    print("  ✓ Health check:")
    print("    curl http://localhost:8000/health")
    print("")
    print("=" * 70)
    
    app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)