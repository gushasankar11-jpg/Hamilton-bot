import subprocess, re, json, os

PDF = "pyq_pdfs/jee_main/practice/Physics/JEE Main Heat and Thermodynamics Previous Year Questions with Answer Key.pdf"
OUT = "data/temp_answers.json"

# Read pages 130 to 139 (captures both MCQ and Numerical keys)
cmd = ["pdftotext", "-f", "130", "-l", "139", PDF, "-"]
text = subprocess.run(cmd, capture_output=True, text=True).stdout

# Match patterns like "1. B" or "12. C"
matches = re.findall(r'(\d+)\.\s*([A-D])', text)
answers = {int(num): letter for num, letter in matches}

print(f"✅ Found {len(answers)} answers")
print("Sample:", dict(list(answers.items())[:5]))

with open(OUT, "w") as f:
    json.dump(answers, f, indent=2)
print(f"Saved to {OUT}")

# Quick verification of specific questions
for q in [17, 18, 19]:
    print(f"Q{q}: {answers.get(q, 'NOT FOUND')}")
