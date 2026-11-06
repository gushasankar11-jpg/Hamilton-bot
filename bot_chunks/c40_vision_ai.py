import telebot, urllib.request, json, os, subprocess

GROQ_KEYS = [
    "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",
    "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",
    "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",
    "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"
]
MODEL = "openai/gpt-oss-120b"
groq_idx = 0

def _call_ai(prompt, max_tokens=600):
    global groq_idx
    for _ in range(len(GROQ_KEYS) * 2):
        if groq_idx >= len(GROQ_KEYS):
            groq_idx = 0
        key = GROQ_KEYS[groq_idx]
        url = "https://api.groq.com/openai/v1/chat/completions"
        data = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": max_tokens
        }
        cmd = ["curl", "-s", "-X", "POST", url,
               "-H", f"Authorization: Bearer {key}",
               "-H", "Content-Type: application/json",
               "-d", json.dumps(data),
               "--max-time", "25"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            result = json.loads(res.stdout)
            if "error" in result:
                print(f"[AI] Key {groq_idx+1} err: {result['error'].get('message','')[:80]}")
                groq_idx += 1
                continue
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[AI] Key {groq_idx+1} timeout: {e}")
            groq_idx += 1
    return "❌ All AI keys failed. Try again."

def get_ai_solution(q_text):
    if not q_text:
        return "❌ No question text available."
    prompt = f"""Solve this JEE Main question with a SHORTCUT-focused approach.

Question: {q_text}

Use EXACTLY this 5-part format. DO NOT use LaTeX formatting like $ or \boxed. Use Unicode (e.g. y² = 4ax) instead:

**1. General Process:** Standard textbook approach (brief, 1-2 lines)
**2. Shortcut:** Fastest trick to solve in exam (main focus)
**3. Guess & Predict:** How to eliminate wrong options or guess if stuck
**4. Skip Calculation:** Round-off / approximation tricks to skip long math
**5. Formula:** Core formula used

Emphasize shortcuts, guessing strategy, and skip-calculation tricks. Keep each part tight (1-2 sentences)."""
    return _call_ai(prompt, max_tokens=600)


def ai_scan_questions(q_list, batch_size=10):
    """Returns dict {q_num: importance_score} and sorted list of (q_num, score)."""
    scores = {}
    for i in range(0, len(q_list), batch_size):
        batch = q_list[i:i+batch_size]
        joined = "\n\n".join([f"ID:{q['q_num']} - {q.get('q_text','')[:300]}" for q in batch])
        prompt = f"""Rank these {len(batch)} JEE Main questions by importance for exam prep.
Return ONLY JSON: {{"scores": {{"123": 8, "124": 5, ...}}}}
Score 1-10 where 10 = must-do unique concept, 1 = repeated/redundant.

{joined}"""
        try:
            raw = _call_ai(prompt, max_tokens=400)
            data = json.loads(raw)
            for qid, sc in data.get("scores", {}).items():
                scores[int(qid)] = float(sc)
        except Exception as e:
            print(f"[Scan] Batch {i} failed: {e}")
    return scores

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.reply_to(message, "📸 Image solution coming soon. For now, type your question as text.")

print("✅ c40_vision_ai: AI router loaded (text mode + scanning)")
