import telebot, base64, urllib.request, json, os

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.chat.id
    msg = bot.reply_to(message, "📸 Analyzing your image...")
    
    # Download image
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    img_b64 = base64.b64encode(downloaded_file).decode('utf-8')
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = """You are Hamilton, an elite JEE tutor. 
    1. If this image is NOT related to physics, chemistry, or maths study (e.g. selfie, meme, random object), reply EXACTLY with the word: REJECT
    2. If it IS a study question, solve it using this exact 5-part format:
       **1. General Process:** (Standard steps)
       **2. Different Angle:** (Visualizing the data)
       **3. Shortcut:** (Fast elimination or trick)
       **4. Generalization:** (How it applies to similar models)
       **5. Formula:** (Core formula used)"""
       
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
    
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
        res = urllib.request.urlopen(req, timeout=30)
        result = json.loads(res.read().decode())
        reply = result["choices"][0]["message"]["content"]
        
        if "REJECT" in reply:
            bot.edit_message_text("🚫 Please upload a study-related question. I cannot analyze random images.", chat_id=uid, message_id=msg.message_id)
        else:
            bot.edit_message_text(reply, chat_id=uid, message_id=msg.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ Vision AI Error: {e}", chat_id=uid, message_id=msg.message_id)

print("✅ c40_vision_ai: Image Doubt Solver loaded.")
