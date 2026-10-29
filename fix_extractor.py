import ast
path = "real_extractor.py"
content = open(path).read()

old_crop = """                crop_top, crop_bottom = max(0, y_min - 20), min(h, y_max)
                q_img = img.crop((0, int(crop_top), w, int(crop_bottom)))"""

new_crop = """                crop_top = max(0, y_min - 20)
                # SAFETY: Ensure crop_bottom is always at least 50px below crop_top
                crop_bottom = max(crop_top + 50, min(h, y_max)) 
                q_img = img.crop((0, int(crop_top), w, int(crop_bottom)))"""

if old_crop in content:
    content = content.replace(old_crop, new_crop)
    try:
        ast.parse(content)
        open(path, "w").write(content)
        print("✅ Fixed crop coordinate error!")
    except SyntaxError as e:
        print("❌ Syntax error:", e)
else:
    print("⏭️ Already patched or pattern not found.")
