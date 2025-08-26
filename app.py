import os, re
from flask import Flask, request, render_template, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# In-memory demo "database"
KB = {"demo": []}
USAGE = {"conversations": 0}

# Optional OpenAI (works if OPENAI_API_KEY is set; otherwise we fallback)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = None
use_new_sdk = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        use_new_sdk = True
    except Exception:
        try:
            import openai
            openai.api_key = OPENAI_API_KEY
            use_new_sdk = False
        except Exception:
            client = None
            use_new_sdk = None

def strip_html(x: str) -> str:
    return re.sub(r"<[^>]+>", " ", x or "")

@app.route("/")
def home():
    return render_template("index.html")

@app.post("/api/kb/add_text")
def kb_add_text():
    text = (request.form.get("text") or "").strip()
    if not text:
        return jsonify(ok=False, error="No text"), 400
    KB["demo"].append(text)
    return jsonify(ok=True, chunks=len(KB["demo"]))

@app.post("/api/kb/add_url")
def kb_add_url():
    import requests
    url = (request.form.get("url") or "").strip()
    if not url:
        return jsonify(ok=False, error="No URL"), 400
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        content = strip_html(r.text)
        for i in range(0, len(content), 800):
            KB["demo"].append(content[i:i+800])
        return jsonify(ok=True, chunks=len(KB["demo"]))
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400

@app.post("/api/chat")
def chat():
    data = request.get_json(force=True)
    msg  = (data.get("message") or "").strip()
    lang = (data.get("lang") or "EN").upper()
    if not msg:
        return jsonify(ok=False, error="Empty message"), 400

    USAGE["conversations"] += 1
    context = "\n".join(KB["demo"][-3:]) if KB["demo"] else "(no knowledge yet)"

    # Use OpenAI if available
    if OPENAI_API_KEY and client is not None:
        try:
            prompt = f"You are ALEX AI. Answer briefly in {lang}. Use ONLY this context if relevant:\n\n{context}\n\nUser: {msg}"
            if use_new_sdk is True:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role":"system","content":"You are concise and helpful."},
                        {"role":"user","content": prompt}
                    ],
                    temperature=0.4,
                    max_tokens=300
                )
                answer = resp.choices[0].message.content.strip()
            else:
                import openai
                resp = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role":"system","content":"You are concise and helpful."},
                        {"role":"user","content": prompt}
                    ],
                    temperature=0.4,
                    max_tokens=300
                )
                answer = resp["choices"][0]["message"]["content"].strip()
            return jsonify(ok=True, answer=answer, used_openai=True, usage=USAGE)
        except Exception:
            pass  # fall through to demo reply

    # Fallback demo reply (no key needed)
    answer = f"(demo) [{lang}] You said: {msg}. Context: {context[:200]}..."
    return jsonify(ok=True, answer=answer, used_openai=False, usage=USAGE)

# Render/Heroku/any WSGI will run this via gunicorn; no __main__ needed.
