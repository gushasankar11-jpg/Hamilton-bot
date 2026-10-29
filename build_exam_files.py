# ==========================================================
# build_exam_files.py — Generate Mains + EAMCET files
# Run once after editing removals.json
# ==========================================================

import json
import os

DATA_DIR = "data"

def load(path):
    with open(path) as f:
        return json.load(f)

def save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def filter_syllabus(adv, remove_set):
    """Returns new tree with removed concepts stripped out."""
    result = {}
    for chapter, subs in adv.items():
        new_subs = {}
        for sub, data in subs.items():
            kept = []
            for concept in data.get("adv", []):
                path = f"{chapter}::{sub}::{concept}"
                if path not in remove_set:
                    kept.append(concept)
            if kept:
                new_subs[sub] = {"adv": kept}
        if new_subs:
            result[chapter] = new_subs
    return result

def count(tree):
    chapters = len(tree)
    subtopics = 0
    concepts = 0
    for chapter, subs in tree.items():
        for sub, data in subs.items():
            subtopics += 1
            concepts += len(data.get("adv", []))
    return chapters, subtopics, concepts

def main():
    print("📖 Loading Advanced master...")
    adv = load(f"{DATA_DIR}/jee_adv_maths.json")

    print("📖 Loading removals...")
    rem = load(f"{DATA_DIR}/removals.json")
    mains_remove = set(rem.get("for_mains_remove", []))
    eamcet_extra = set(rem.get("for_eamcet_remove", []))

    print("🔨 Building Mains file...")
    mains = filter_syllabus(adv, mains_remove)
    save(f"{DATA_DIR}/jee_main_maths.json", mains)

    print("🔨 Building EAMCET file...")
    eamcet_remove = mains_remove | eamcet_extra
    eamcet = filter_syllabus(adv, eamcet_remove)
    save(f"{DATA_DIR}/eamcet_maths.json", eamcet)

    print("\n✅ Done. Files written:")
    for name, tree in [("Advanced", adv), ("Mains", mains), ("EAMCET", eamcet)]:
        c, st, con = count(tree)
        print(f"   {name:<10} → {c} chapters · {st} subtopics · {con} concepts")

if __name__ == "__main__":
    main()
