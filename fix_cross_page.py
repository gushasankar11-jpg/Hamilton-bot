import ast

# We will patch perfect_extractor.py (and extract_all.py) to handle cross-page questions
path = "perfect_extractor.py"
content = open(path).read()

old_crop_logic = '''            for i, (y_str, q_num) in enumerate(q_matches):
                q_num = int(q_num)
                if q_num not in q_texts: continue
                q_text = q_texts[q_num]
                
                year_match = re.search(r'(20[2-9]\\d)', q_text[:200])
                year = int(year_match.group(1)) if year_match else 0
                if year != 0 and year < MIN_YEAR: continue # Skip old
                
                y_min = float(y_str)
                y_max = float(q_matches[i+1][0]) if i+1 < len(q_matches) else foot_y - 10
                
                crop_top = max(0, (y_min * scale) - 20)
                crop_bottom = min(h, (y_max * scale))
                
                if crop_bottom <= crop_top: continue
                
                q_filename = os.path.join(out_dir, f"q{q_num}.png")
                img.crop((0, int(crop_top), w, int(crop_bottom))).save(q_filename)'''

new_crop_logic = '''            # 1. First, map all valid question numbers to their exact coordinates
            page_qs = []
            for i, (y_str, q_num) in enumerate(q_matches):
                qn = int(q_num)
                if qn not in q_texts: continue
                y_min = float(y_str)
                # If it's the last question on the page, crop to the footer
                y_max = float(q_matches[i+1][0]) if i+1 < len(q_matches) else foot_y - 10
                page_qs.append((qn, y_min, y_max))

            # 2. Crop each question (checking for cross-page continuation)
            for idx_in_page, (qn, y_min, y_max) in enumerate(page_qs):
                q_text = q_texts[qn]
                year_match = re.search(r'(20[2-9]\\d)', q_text[:200])
                year = int(year_match.group(1)) if year_match else 0
                if year != 0 and year < MIN_YEAR: continue
                
                crop_top = max(0, (y_min * scale) - 20)
                crop_bottom = min(h, (y_max * scale))
                
                if crop_bottom <= crop_top: continue
                
                q_filename = os.path.join(out_dir, f"q{qn}.png")
                main_img = img.crop((0, int(crop_top), w, int(crop_bottom)))
                
                # CROSS-PAGE CHECK: If this is the last question on the page, and it doesn't have options (A) (B)...
                # It probably continues on the next page.
                is_last_on_page = (idx_in_page == len(page_qs) - 1)
                lacks_options = not re.search(r'\\(A\\)|A\\)', q_text)
                
                if is_last_on_page and lacks_options and page < total_pages:
                    # Crop the top of the next page up to the first question
                    next_img_base = os.path.join(out_dir, f"tmp_page_{page+1}")
                    subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page+1), "-l", str(page+1), "-singlefile", pdf_path, next_img_base], check=True, stdout=subprocess.DEVNULL)
                    next_img_path = next_img_base + ".png"
                    
                    if os.path.exists(next_img_path):
                        next_img = Image.open(next_img_path)
                        next_xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page+1), "-l", str(page+1), pdf_path, "-"], capture_output=True, text=True).stdout
                        next_q_matches = re.findall(r'<word xMin="[\\d\\.]+" yMin="([\\d\\.]+)"[^>]*>Q?(\\d+)[\\.\\)\\s]*</word>', next_xml)
                        
                        # Find where the NEXT question starts on the next page (or use top margin)
                        next_y_max = float(next_q_matches[0][0]) if next_q_matches else 200
                        next_crop_bottom = min(next_img.size[1], next_y_max * scale)
                        
                        top_part = next_img.crop((0, 0, next_img.size[0], int(next_crop_bottom)))
                        
                        # STITCH THEM TOGETHER
                        combined = Image.new('RGB', (w, main_img.size[1] + top_part.size[1]), 'white')
                        combined.paste(main_img, (0, 0))
                        combined.paste(top_part, (0, main_img.size[1]))
                        combined.save(q_filename)
                        
                        next_img.close()
                        os.remove(next_img_path)
                    else:
                        main_img.save(q_filename)
                else:
                    main_img.save(q_filename)'''

if old_crop_logic in content:
    content = content.replace(old_crop_logic, new_crop_logic)
    open(path, "w").write(content)
    print("✅ perfect_extractor.py patched for cross-page stitching.")
else:
    print("⚠️ Pattern not found. The file might have changed.")

