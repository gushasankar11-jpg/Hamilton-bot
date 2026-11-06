import ast, re

path = "bot_chunks/c09.py"
content = open(path).read()

# Find the doubt handler (whatever form it's in)
# We look for any block that handles "waiting_for_doubt"
doubt_start = content.find('if st.get("waiting_for_doubt"):')
if doubt_start == -1:
    doubt_start = content.find('if st.get("waiting_for_doubt")')
if doubt_start == -1:
    print("❌ Doubt handler not found")
    exit(1)

# Find the next top-level statement after the doubt block
# Look for next `return` followed by blank line + same indent, or next `if st.get`
indent_match = re.search(r'(\n\s+)if st\.get\("waiting_for_doubt"\)', content[doubt_start-100:doubt_start+200])
if indent_match:
    indent = indent_match.group(1)
    indent_str = indent[1:]  # remove leading \n
else:
    indent_str = "    "

# Find end: next `    if st.get(` at same level OR next top-level function
after = content[doubt_start + 30:]
end_match = re.search(r'\n' + re.escape(indent_str) + r'if st\.get\(', after)
if not end_match:
    end_match = re.search(r'\n\n    # ---', after)
if not end_match:
    end_match = re.search(r'\n\ndef ', after)

if end_match:
    end_pos = doubt_start + 30 + end_match.start()
else:
    end_pos = doubt_start + 2000  # fallback

I1 = indent_str
I2 = I1 + "    "
I3 = I2 + "    "

new_handler = f'''
{I1}if st.get("waiting_for_doubt"):
{I2}st["waiting_for_doubt"] = False
{I2}q = st.get("q", {{}})
{I2}doubt_text = (message.text or "").strip()
{I2}
{I2}if not doubt_text:
{I2}    safe_send(uid, "⚠️ Please type your doubt.")
{I2}    return
{I2}
{I2}q_text = q.get("q_text", "")
{I2}subtopic = q.get("subtopic", "")
{I2}chapter = st.get("chapter", "")
{I2}subject = st.get("subj", "")
{I2}correct_idx = q.get("correct_index", 0)
{I2}correct_letter = chr(65 + correct_idx) if isinstance(correct_idx, int) else "?"
{I2}
{I2}msg = _b().send_message(uid, "🧠 <i>Thinking about your doubt...</i>")
{I2}
{I2}prompt = f"""You are Hamilton, an elite JEE tutor. The student is looking at this specific question:

SUBJECT: {{subject}}
CHAPTER: {{chapter}}
SUBTOPIC: {{subtopic}}
QUESTION: {{q_text}}

CORRECT ANSWER: Option {{correct_letter}}

The student's doubt is:
"{{doubt_text}}"

Answer their doubt directly. Rules:
1. Stay strictly on this question's topic ({{subtopic}})
2. If they ask about predicting/guessing the answer without calculation, give concrete tricks
3. Be specific to THIS problem, not generic advice
4. Keep answer under 150 words
5. Do NOT mention unrelated subjects or topics"""
{I2}
{I2}try:
{I3}import ai_client
{I3}reply = ai_client.ask_ai(prompt)
{I3}if not reply or len(reply) < 5:
{I3}    reply = "❌ AI returned empty response. Please try again."
{I3}_b().edit_message_text(f"💬 <b>Answer to your doubt:</b>\\n\\n{{reply}}", chat_id=uid, message_id=msg.message_id, parse_mode="Markdown")
{I2}except Exception as e:
{I3}_b().edit_message_text(f"❌ AI Error: {{e}}", chat_id=uid, message_id=msg.message_id)
{I2}return
'''

# Replace
content = content[:doubt_start] + new_handler + "\n" + content[end_pos:]
print("✅ Doubt handler rewritten (with full question context)")

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ c09.py syntax OK")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR: {e}")
