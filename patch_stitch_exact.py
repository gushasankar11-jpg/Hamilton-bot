import ast

path = "extract_all.py"
content = open(path).read()

old_crop = '''        for qn in to_crop:
            c = q_coords[qn]
            top = max(0, (c["y_min"] * scale) - 20)
            bot = min(h, (c["y_max"] * scale))
            if bot <= top + 20: continue
            
            q_file = os.path.join(out_dir, f"q{qn}.png")
            img.crop((0, int(top), w, int(bot))).save(q_file)'''

new_crop = '''        for idx_in_page, qn in enumerate(to_crop):
            c = q_coords[qn]
            top = max(0, (c["y_min"] * scale) - 20)
            bot = min(h, (c["y_max"] * scale))
            if bot <= top + 20: continue
            
            q_file = os.path.join(out_dir, f"q{qn}.png")
            main_img = img.crop((0, int(top), w, int(bot)))
            
            # --- CROSS PAGE STITCHING ---
            is_last_on_page = (idx_in_page == len(to_crop) - 1)
            q_text = q_texts.get(qn, "")
            lacks_options = not re.search(r'\\(A\\)|A\\)|a\\)', q_text)
            
            if is_last_on_page and lacks_options and page < total_pages:
                next_img_base = os.path.join(out_dir, f"tmp_{page+1}")
                subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page+1), "-l", str(page+1), "-singlefile", pdf_path, next_img_base], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                next_img_path = next_img_base + ".png"
                
                if os.path.exists(next_img_path):
                    next_img = Image.open(next_img_path)
                    next_xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page+1), "-l", str(page+1), pdf_path, "-"], capture_output=True, text=True, timeout=10).stdout
                    next_q_matches = re.findall(r'<word xMin="[\\d\\.]+" yMin="([\\d\\.]+)"[^>]*>Q?(\\d+)[\\.\\)\\s]*</word>', next_xml)
                    
                    next_y_max = float(next_q_matches[0][0]) if next_q_matches else 200
                    next_crop_bottom = min(next_img.size[1], next_y_max * scale)
                    
                    top_part = next_img.crop((0, 0, next_img.size[0], int(next_crop_bottom)))
                    
                    combined = Image.new('RGB', (w, main_img.size[1] + top_part.size[1]), 'white')
                    combined.paste(main_img, (0, 0))
                    combined.paste(top_part, (0, main_img.size[1]))
                    combined.save(q_file)
                    
                    next_img.close()
                    try: os.remove(next_img_path)
                    except: pass
                else:
                    main_img.save(q_file)
            else:
                main_img.save(q_file)'''

if old_crop in content:
    content = content.replace(old_crop, new_crop)
    open(path, "w").write(content)
    print("✅ extract_all.py EXACTLY patched for cross-page stitching.")
else:
    print("⚠️ Still could not find the exact pattern.")
