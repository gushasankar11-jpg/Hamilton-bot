import ast, sys

PATH = "bot_chunks/c04_exam.py"
content = open(PATH).read()

OLD = '''        elif data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json
            with open("data/pyq_db.json") as f: db = json.load(f)
            kb = InlineKeyboardMarkup(row_width=1)
            chapters = list(db.get("practice", {}).get(subj, {}).keys())
            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
            kb.add(InlineKeyboardButton("\U0001F519 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"\U0001F4D6 <b>{subj} - PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)'''

NEW = '''        elif data.startswith("f_pyq_sub:"):
            subj = data.split(":")[1]
            state["pyq_subj"] = subj
            import json, re
            with open("data/pyq_db.json") as f: db = json.load(f)
            chapters = list(db.get("practice", {}).get(subj, {}).keys())

            # --- Syllabus-order anchor map (PDF coarse chapter -> syllabus fine chapter) ---
            _PYQ_OVERRIDES = {
                "Atoms and Nuclei": "Atomic Physics",
                "Capacitor": "Capacitor and Capacitance",
                "Center of Mass and Collision": "System of Particles and Centre of Mass",
                "Current Electricity": "Electric Current and Circuits",
                "Dual Nature of Radiation": "Dual Nature of Radiation and Matter",
                "Electrostatics": "Coulomb's Law and Electric Field",
                "Geometrical Optics": "Geometrical Optics: Part 1",
                "Heat and Thermodynamics": "Thermodynamics",
                "Laws of Motion": "Newton's Laws of Motion (Without Friction)",
                "Magnetic Effect of Current": "Magnetic Field and Magnetic Forces",
            }

            _syl_list = []
            try:
                _syl = json.load(open(f"data/jee_main_{subj.lower()}.json"))
                _syl_list = list(_syl.keys())
            except Exception:
                _syl_list = []

            def _pyq_pos(ch):
                if not _syl_list: return (2, 9999)
                if ch in _syl_list: return (0, _syl_list.index(ch))
                mapped = _PYQ_OVERRIDES.get(ch)
                if mapped and mapped in _syl_list: return (1, _syl_list.index(mapped))
                words = [w.lower() for w in re.findall(r"[A-Za-z]+", ch) if len(w) > 4]
                best_score, best_pos = 0, 9999
                for i, sc in enumerate(_syl_list):
                    s = sum(1 for w in words if w in sc.lower())
                    if s > best_score or (s == best_score and s > 0 and i < best_pos):
                        best_score, best_pos = s, i
                return (1, best_pos) if best_score > 0 else (2, 9999)

            chapters.sort(key=_pyq_pos)

            kb = InlineKeyboardMarkup(row_width=1)
            for ch in chapters:
                kb.add(InlineKeyboardButton(ch[:30], callback_data=f"f_pyq_ch:{ch}"))
            kb.add(InlineKeyboardButton("\U0001F519 Back", callback_data="f_pyq:practice"))
            _b().edit_message_text(f"\U0001F4D6 <b>{subj} - PYQ Chapters</b>:", chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=kb)'''

# Exact count check
occ = content.count(OLD)
if occ != 1:
    print(f"❌ Expected exactly 1 match of OLD block, found {occ}")
    sys.exit(1)

new_content = content.replace(OLD, NEW, 1)

# Mandatory syntax check BEFORE saving
try:
    ast.parse(new_content)
    print("✅ SYNTAX OK")
except SyntaxError as e:
    print(f"❌ SYNTAX FAIL: {e}")
    sys.exit(1)

open(PATH, "w").write(new_content)
print(f"✅ Patched {PATH}")
