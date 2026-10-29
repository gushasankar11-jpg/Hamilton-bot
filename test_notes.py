# Test notes_engine on one chapter
import json
import health
import notes_engine
import ai_client

EXAM = "JEE_MAIN"
SUBJECT = "Maths"
CHAPTER = "Matrices"

data = health.load_subject_data(SUBJECT, EXAM)
if not data or CHAPTER not in data:
    print(f"❌ Chapter '{CHAPTER}' not found")
    raise SystemExit

subs = data[CHAPTER]
subtopics = list(subs.keys())
concepts = {s: (subs[s].get("adv", []) if isinstance(subs[s], dict) else subs[s])
            for s in subtopics}

print(f"Chapter: {CHAPTER}")
print(f"Subtopics: {len(subtopics)}")
print(f"Concepts: {sum(len(v) for v in concepts.values())}")
print()
print("Stage 1 — Analyzing...")
a = notes_engine.analyze_chapter(EXAM, SUBJECT, CHAPTER, subtopics, sum(concepts.values(), []))
print(json.dumps(a, indent=2))
print()

# Test one page only to save calls
total = a["pages_required"]
group = [{"name": subtopics[0], "concepts": concepts[subtopics[0]]}]
print(f"Stage 2 — Generating page 1 of {total} (first subtopic only)...")
page = notes_engine.generate_page(EXAM, SUBJECT, CHAPTER, 1, total, group, a["chapter_type"])
if page:
    print("=" * 60)
    print(page[:1200])
    print("=" * 60)
else:
    print("❌ page generation failed")
