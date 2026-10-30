import telebot, base64, urllib.request, json, os, subprocess

GROQ_KEYS = [
    "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",
    "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",
    "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",
    "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"
]
groq_idx = 0

def get_vision_solution(img_path):
    """Takes an image path, sends it to Groq Vision, returns the 5-part solution."""
    global groq_idx
    if not os.path.exists(img_path):
        return "❌ Image not found."
        
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')
        
    url = "https://api.groq.com/openai/v1/chat/completions"
    prompt = """You are Hamilton, an elite JEE tutor. Solve this question from the image.
    Return ONLY this exact 5-part format:
    **1. General Process:** (Standard steps)
    **2. Different Angle:** (Visualizing the data)
    **3. Shortcut:** (Fast elimination or trick)
    **4. Generalization:** (How it applies to similar models)
    **5. Formula:** (Core formula used)"""
    
    while True:
        if groq_idx >= len(GROQ_KEYS): 
            return "❌ All API keys exhausted. Please try again later."
            
        headers = {
            "Authorization": f"Bearer {GROQ_KEYS[groq_idx]}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }],
            "temperature": 0.1
        }
        
        cmd = ["curl", "-s", "-X", "POST", url, "-H", f"Authorization: Bearer {GROQ_KEYS[groq_idx]}", "-H", "Content-Type: application/json", "-d", json.dumps(data)]
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            result = json.loads(res.stdout)
            if "error" in result:
                print(f"Vision API Error: {result['error']}")
                groq_idx += 1
                continue
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Curl Error: {e}")
            groq_idx += 1

# Handle user sending photo directly to bot
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.chat.id
    msg = bot.reply_to(message, "📸 Analyzing your image...")
    
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    temp_path = f"temp_{uid}.jpg"
    with open(temp_path, 'wb') as new_file:
        new_file.write(downloaded_file)
        
    sol = get_vision_solution(temp_path)
    os.remove(temp_path)
    
    if "REJECT" in sol or "not related" in sol.lower():
        bot.edit_message_text("🚫 Please upload a study-related question.", chat_id=uid, message_id=msg.message_id)
    else:
        bot.edit_message_text(sol, chat_id=uid, message_id=msg.message_id, parse_mode="Markdown")
        
print("✅ c40_vision_ai: Vision Doubt Solver loaded.")
