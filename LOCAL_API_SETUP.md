# Local API Setup — Windows (Victus PC with RTX 3050)

This guide explains how to run GopalBot's AI backend on your own Windows machine
so that **zero data leaves your hardware** and there is **no corporate involvement**
(no Meta, no Groq, no OpenAI).

---

## Architecture

```
Discord Server
      │
      ▼
Railway Bot  (always online, handles Discord events)
      │
      ▼
Your Victus PC — local_api_server.py  (port 8000)
      │
      ▼
Ollama — Mistral 7B  (port 11434, GPU-accelerated on RTX 3050)
```

---

## Part A — Install Ollama

1. Download the Windows installer from **https://ollama.ai**
2. Run the installer and follow the prompts.
3. Ollama will start automatically as a background service on port **11434**.

> **Verify:**
> Open PowerShell and run:
> ```powershell
> curl http://localhost:11434
> ```
> You should see: `Ollama is running`

---

## Part B — Pull the Mistral 7B Model

Open PowerShell and run:

```powershell
ollama pull mistral
```

This downloads the Mistral 7B model (~4 GB). It is fast and runs natively on the
RTX 3050 with instant responses.

> **Verify:**
> ```powershell
> curl http://localhost:11434/api/generate `
>   -Method POST `
>   -ContentType "application/json" `
>   -Body '{"model":"mistral","prompt":"hello","stream":false}'
> ```
> You should receive a JSON response containing a `"response"` field.

---

## Part C — Install Python Dependencies (Local Server)

```powershell
pip install -r requirements_local.txt
```

---

## Part D — Start the Local API Server

```powershell
python local_api_server.py
```

You should see:

```
============================================================
GopalBot Local API Server
============================================================
Listening on  : http://0.0.0.0:8000
Ollama target : http://localhost:11434
Model         : mistral
============================================================
```

> **Verify:**
> ```powershell
> curl http://localhost:8000/health
> ```
> Expected: `{"model": "mistral", "status": "ok"}`

---

## Part E — Test the Full Stack

```powershell
curl http://localhost:8000/api/generate `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"prompt":"who are you?"}'
```

You should get an instant Mistral response in JSON.

---

## Railway Bot Configuration

The Railway-hosted `bot.py` reads the `LOCAL_API_URL` environment variable to
know where to find your local API.  You have two options:

### Option 1 — Same network (LAN)
If Railway and your PC are on the same network (unlikely), set:
```
LOCAL_API_URL=http://<your-pc-lan-ip>:8000
```

### Option 2 — ngrok (Recommended for remote access)

1. Download ngrok from **https://ngrok.com**
2. Run:
   ```powershell
   ngrok http 8000
   ```
3. Copy the `https://xxxx.ngrok-free.app` URL.
4. In Railway, set the environment variable:
   ```
   LOCAL_API_URL=https://xxxx.ngrok-free.app
   ```
5. Redeploy the Railway service.

Now the Railway bot can reach your local Mistral instance from anywhere.

---

## What Happens When Your PC Is Off?

When `local_api_server.py` is not running (or your PC is off), the Railway bot
detects the connection failure and automatically replies:

> *"My creator's PC is offline right now 🔌 I'm powered by Mistral running on
> their Victus with RTX 3050 — turn it on to chat with me properly!"*

No crashes, no errors — just a friendly message.

---

## Keeping the Server Running in the Background

To keep the server running without a visible terminal window, use:

```powershell
Start-Process pythonw -ArgumentList "local_api_server.py" -WindowStyle Hidden
```

Or create a simple batch file `start_gopalbot.bat`:
```batch
@echo off
start "" /B pythonw local_api_server.py
echo GopalBot local API started.
```

---

## Quick Reference

| Step | Command |
|------|---------|
| Start Ollama | Starts automatically as a Windows service |
| Pull model (first time) | `ollama pull mistral` |
| Start local API | `python local_api_server.py` |
| Health check | `curl http://localhost:8000/health` |
| Test generation | See Part E above |
| Expose via ngrok | `ngrok http 8000` |

---

## Privacy Guarantee

✅ All AI inference runs on **your RTX 3050** — nothing is sent to external servers.  
✅ **Mistral AI** is an independent French company — no Meta involvement.  
✅ **Ollama** is fully open-source.  
✅ **GopalBot** code is owned by **tomato9553-bit**.  
✅ Discord messages stay between your server and Discord's servers only.  
