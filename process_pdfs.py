import subprocess, re, os, json
from PIL import Image

def process_pdf_page(pdf, page_num, out_dir, start_q=17, end_q=19):
    os.makedirs(out_dir, exist_ok=True)
    img_base = os.path.join(out_dir, f"page{page_num}")
    subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(page_num), "-l", str(page_num), "-singlefile", pdf, img_base], check=True)
    img_path = img_base + ".png"
    img = Image.open(img_path)
    img_w, img_h = img.size

    xml_out = subprocess.run(["pdftotext", "-bbox", "-f", str(page_num), "-l", str(page_num), pdf, "-"], capture_output=True, text=True).stdout
    matches = re.findall(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Q(\d+)\.</word>', xml_out)
    
    # Find the footer Y-coord to stop cropping
    footer_match = re.search(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Keep</word>', xml_out)
    footer_y = float(footer_match.group(1)) if footer_match else img_h

    scale = 150.0 / 72.0 
    
    for i, (y_str, q_num) in enumerate(matches):
        q_num = int(q_num)
        if q_num < start_q or q_num > end_q: continue
        
        y_min = float(y_str) * scale
        if i + 1 < len(matches):
            y_max = float(matches[i+1][0]) * scale - 15
        else:
            y_max = footer_y * scale - 15 # Cut before the footer
            
        crop_top = max(0, y_min - 15)
        crop_bottom = min(img_h, y_max)
        
        cropped = img.crop((0, int(crop_top), img_w, int(crop_bottom)))
        cropped.save(os.path.join(out_dir, f"q{q_num}.png"))
        print(f"✂️ Cropped Q{q_num}")

if __name__ == "__main__":
    pdf = "pyq_pdfs/jee_main/practice/Physics/JEE Main Heat and Thermodynamics Previous Year Questions with Answer Key.pdf"
    process_pdf_page(pdf, 6, "pyq_images/test_crop")
