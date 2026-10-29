# ==========================================================
# build_physics_files.py
# Reads jee_adv_physics.json + removals_physics.json
# Generates jee_main_physics.json + eamcet_physics.json
# ==========================================================

import json
import os

DATA = "data"

def load(path):
    with open(path) as f:
        return json.load(f)

def save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def filter_syllabus(adv, remove_set):
    result = {}
    for chapter, subs in adv.items():
        new_subs = {}
        for sub, data in subs.items():
            concepts = data.get("adv", []) if isinstance(data, dict) else data
            kept = []
            for c in concepts:
                path = f"{chapter}::{sub}::{c}"
                if path not in remove_set:
                    kept.append(c)
            if kept:
                new_subs[sub] = {"adv": kept}
        if new_subs:
            result[chapter] = new_subs
    return result

def count(tree):
    chapters = len(tree)
    subs = sum(len(v) for v in tree.values())
    concepts = sum(len(s.get("adv", [])) for ch in tree.values() for s in ch.values())
    return chapters, subs, concepts

def main():
    print("📖 Loading Advanced Physics...")
    adv = load(f"{DATA}/jee_adv_physics.json")

    print("📖 Loading Physics removals...")
    rem = load(f"{DATA}/removals_physics.json")
    mains_rm = set(rem.get("for_mains_remove_physics", []))
    eamcet_rm_extra = set(rem.get("for_eamcet_remove_physics", []))

    print("🔨 Building Mains Physics...")
    mains = filter_syllabus(adv, mains_rm)
    save(f"{DATA}/jee_main_physics.json", mains)

    print("🔨 Building EAMCET Physics...")
    eamcet_rm = mains_rm | eamcet_rm_extra
    eamcet = filter_syllabus(adv, eamcet_rm)
    save(f"{DATA}/eamcet_physics.json", eamcet)

    print("\n✅ Files written:")
    for name, tree in [("Advanced", adv), ("Mains", mains), ("EAMCET", eamcet)]:
        c, s, k = count(tree)
        print(f"   {name:<10} → {c} chapters · {s} subtopics · {k} concepts")

if __name__ == "__main__":
    main()
