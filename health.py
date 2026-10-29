# ==========================================================
# health.py — Hamilton Study AI
#
# HEALTH HIERARCHY (bottom-up):
#   1. Subtopic health   ← increments happen HERE (+0.5 to +2.5)
#   2. Chapter health    = average of subtopics in that chapter
#   3. Subject health    = average of chapters in that subject
#   4. Overall health    = average of the 3 subjects
# ==========================================================

import json
import os
from datetime import datetime

from config import DATA_DIR, PROFILE_DIR

os.makedirs(PROFILE_DIR, exist_ok=True)

SUBJECT_FILES = {
    "Maths": {
        "JEE_ADV":  "jee_adv_maths.json",
        "JEE_MAIN": "jee_main_maths.json",
        "EAMCET":   "eamcet_maths.json",
    },
    "Physics": {
        "JEE_ADV":  "jee_adv_physics.json",
        "JEE_MAIN": "jee_main_physics.json",
        "EAMCET":   "eamcet_physics.json",
    },
    "Chemistry": {
        "JEE_ADV":  "jee_adv_chemistry.json",
        "JEE_MAIN": "jee_main_chemistry.json",
        "EAMCET":   "eamcet_chemistry.json",
    },
}

_DB_CACHE = {}

HEALTH_BASELINE = 5.0


# ==========================================================
# DATA LOADING
# ==========================================================
def load_subject_data(subject, exam):
    key = f"{subject}::{exam}"
    if key in _DB_CACHE:
        return _DB_CACHE[key]
    subj_map = SUBJECT_FILES.get(subject)
    if not subj_map:
        _DB_CACHE[key] = None
        return None
    filename = subj_map.get(exam)
    if not filename:
        _DB_CACHE[key] = None
        return None
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        _DB_CACHE[key] = None
        return None
    with open(path) as f:
        data = json.load(f)
    _DB_CACHE[key] = data
    return data


def available_subjects():
    return list(SUBJECT_FILES.keys())


def exam_of(profile):
    if profile.get("priority"):
        return profile["priority"]
    exams = profile.get("exams", [])
    if exams:
        return exams[0]
    return None


# ==========================================================
# PROFILE I/O
# ==========================================================
def load_profile(uid):
    path = os.path.join(PROFILE_DIR, f"{uid}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def save_profile(uid, profile):
    path = os.path.join(PROFILE_DIR, f"{uid}.json")
    with open(path, "w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


# ==========================================================
# SMALL-INCREMENT HEALTH CALCULATION
# ==========================================================
def compute_health_change(correct, difficulty, time_taken, ideal_time, current_health):
    """
    Returns NEW health value for the subtopic.
    Correct answers → +0.5 to +2.5
    Wrong answers   → -0.5 to -1.5
    """
    if current_health is None:
        current_health = HEALTH_BASELINE

    if correct:
        delta = 1.0
        if time_taken < ideal_time * 0.6:
            delta += 0.3
        if time_taken < ideal_time * 0.4:
            delta += 0.3
        if difficulty == "hard":
            delta += 0.5
        elif difficulty == "easy":
            delta -= 0.3
        if delta > 2.5:
            delta = 2.5
    else:
        delta = -0.8
        if difficulty == "easy":
            delta -= 0.5
        elif difficulty == "hard":
            delta += 0.3
        if delta < -1.5:
            delta = -1.5

    new_health = current_health + delta
    new_health = max(0.0, min(100.0, new_health))
    return round(new_health, 1)


# ==========================================================
# RECORD ATTEMPT — increments SUBTOPIC health
# ==========================================================
def record_attempt(uid, subject, chapter, subtopic, concept,
                   correct, time_taken, ideal_time, difficulty="medium"):
    """
    Records one attempt.
    Health is stored at SUBTOPIC level (subject::chapter::subtopic).
    The concept name is also stored in a per-concept counter for reference.
    Returns (before_subtopic_health, after_subtopic_health).
    """
    path = os.path.join(PROFILE_DIR, f"{uid}.json")
    profile = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                profile = json.load(f)
        except Exception:
            profile = {}

    profile.setdefault("subtopic_stats", {})
    subtopic_key = f"{subject}::{chapter}::{subtopic}"

    stat = profile["subtopic_stats"].get(subtopic_key)
    if not stat:
        stat = {
            "attempts": 0,
            "correct": 0,
            "total_time": 0,
            "ideal_time": ideal_time,
            "avg_time": 0,
            "health": None,
            "concepts_seen": {},
        }

    before_health = stat.get("health")

    new_health = compute_health_change(
        correct, difficulty, time_taken, ideal_time, before_health
    )

    stat["attempts"] += 1
    if correct:
        stat["correct"] += 1
    stat["total_time"] += int(time_taken)
    stat["ideal_time"] = ideal_time
    stat["avg_time"] = round(stat["total_time"] / stat["attempts"], 1)
    stat["health"] = new_health
    stat["last_difficulty"] = difficulty

    # Track concepts visited (still per-subtopic, but keep per-concept attempts)
    if concept:
        concepts_seen = stat.setdefault("concepts_seen", {})
        cs = concepts_seen.get(concept, {"attempts": 0, "correct": 0})
        cs["attempts"] += 1
        if correct:
            cs["correct"] += 1
        concepts_seen[concept] = cs

    profile["subtopic_stats"][subtopic_key] = stat
    profile["last_updated"] = datetime.now().isoformat()

    with open(path, "w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    return before_health, new_health


# ==========================================================
# SUBTOPIC HEALTH
# ==========================================================
def subtopic_health(profile, subject, chapter, subtopic):
    key = f"{subject}::{chapter}::{subtopic}"
    stat = profile.get("subtopic_stats", {}).get(key)
    if not stat or stat.get("attempts", 0) == 0:
        return None
    h = stat.get("health")
    if h is None:
        return None
    return round(float(h), 1)


# ==========================================================
# CHAPTER HEALTH = average of subtopics in that chapter
# ==========================================================
def chapter_health_map(profile, subject, exam, only_selected=True):
    data = load_subject_data(subject, exam)
    if not data:
        return {}

    selected_set = set(profile.get("selected_chapters", {}).get(subject, []))
    result = {}

    for chapter, subs in data.items():
        if only_selected and selected_set and chapter not in selected_set:
            continue

        subtopic_healths = []
        total_subtopics = 0
        started_subtopics = 0
        total_attempts = 0

        for sub in subs.keys():
            total_subtopics += 1
            h = subtopic_health(profile, subject, chapter, sub)
            if h is not None:
                subtopic_healths.append(h)
                started_subtopics += 1
                key = f"{subject}::{chapter}::{sub}"
                total_attempts += profile.get("subtopic_stats", {}).get(key, {}).get("attempts", 0)

        ch_h = round(sum(subtopic_healths) / len(subtopic_healths), 1) if subtopic_healths else None
        result[chapter] = {
            "health": ch_h,
            "attempted": total_attempts,
            "subtopics_total": total_subtopics,
            "subtopics_started": started_subtopics,
        }
    return result


# ==========================================================
# SUBJECT HEALTH = average of chapters
# ==========================================================
def subject_health(profile, subject, exam):
    ch_map = chapter_health_map(profile, subject, exam, only_selected=True)
    if not ch_map:
        return None, 0, 0
    started = [c["health"] for c in ch_map.values() if c["health"] is not None]
    if not started:
        return None, 0, len(ch_map)
    return round(sum(started) / len(started), 1), len(started), len(ch_map)


# ==========================================================
# OVERALL HEALTH = average of the 3 subjects
# ==========================================================
def overall_health(profile):
    exam = exam_of(profile)
    if exam is None:
        return {"exam": None, "subjects": {}, "overall": None, "filtering": False}

    subjects = {}
    for subj in available_subjects():
        h, started, total = subject_health(profile, subj, exam)
        subjects[subj] = {
            "health": h,
            "chapters_started": started,
            "chapters_total": total,
        }

    started = [s["health"] for s in subjects.values() if s["health"] is not None]
    overall = round(sum(started) / len(started), 1) if started else None

    return {
        "exam": exam,
        "subjects": subjects,
        "overall": overall,
        "filtering": bool(profile.get("selected_chapters")),
    }


# ==========================================================
# ATTEMPTS SUMMARY
# ==========================================================
def attempts_summary(profile):
    stats = profile.get("subtopic_stats", {})
    total_attempts = 0
    total_correct = 0
    for k, stat in stats.items():
        total_attempts += stat.get("attempts", 0)
        total_correct += stat.get("correct", 0)
    wrong = total_attempts - total_correct
    accuracy = round(100 * total_correct / total_attempts, 1) if total_attempts else 0
    return {
        "attempted": total_attempts,
        "correct": total_correct,
        "wrong": wrong,
        "accuracy": accuracy,
    }


# ==========================================================
# RANK + PERCENTILE
# ==========================================================
def estimate_rank(profile):
    r = overall_health(profile)
    h = r.get("overall")
    if h is None:
        return 0, "Not started"
    if h >= 90:
        return h, "Top 500"
    if h >= 80:
        return h, "Top 2,000"
    if h >= 70:
        return h, "Top 8,000"
    if h >= 60:
        return h, "Top 20,000"
    if h >= 50:
        return h, "Top 50,000"
    return h, "Needs work"


def predict_percentile(h):
    if h is None:
        return 0
    if h >= 90:
        return 99.5
    if h >= 85:
        return 99.0
    if h >= 80:
        return 98.0
    if h >= 75:
        return 96.5
    if h >= 70:
        return 94.0
    if h >= 65:
        return 91.0
    if h >= 60:
        return 87.0
    if h >= 55:
        return 82.0
    if h >= 50:
        return 76.0
    if h >= 45:
        return 70.0
    return round(h * 1.5, 1)


# ==========================================================
# WEAK SUBTOPIC FINDER (for practice picker)
# ==========================================================
def weakest_subtopics(profile, subject, exam, chapter=None, limit=20):
    """
    Returns list of (health_or_0, chapter, subtopic) sorted weakest first.
    """
    data = load_subject_data(subject, exam)
    if not data:
        return []

    selected = set(profile.get("selected_chapters", {}).get(subject, []))
    candidates = []

    chapters = [chapter] if chapter else list(data.keys())
    for ch in chapters:
        if selected and ch not in selected:
            continue
        for sub in data[ch].keys():
            h = subtopic_health(profile, subject, ch, sub)
            score = h if h is not None else 0.0
            candidates.append((score, ch, sub))

    candidates.sort(key=lambda x: x[0])
    return candidates[:limit]


# ==========================================================
# SELF TEST
# ==========================================================
if __name__ == "__main__":
    print("health.py OK — subtopic-level increments")
    print("Subjects:", available_subjects())
    for subj in available_subjects():
        for exam in ["JEE_ADV", "JEE_MAIN", "EAMCET"]:
            d = load_subject_data(subj, exam)
            print(f"  {subj} {exam}: {len(d) if d else 0} chapters")

    print()
    print("Health change samples (small increments):")
    h = None
    for i in range(6):
        before = h
        h = compute_health_change(True, "medium", 60, 60, h)
        print(f"  correct #{i+1}: {before} -> {h}")

    for i in range(3):
        before = h
        h = compute_health_change(False, "medium", 90, 60, h)
        print(f"  wrong #{i+1}: {before} -> {h}")

    print()
    print("Fast correct hard:", compute_health_change(True, "hard", 30, 60, 50))
    print("Slow wrong easy:", compute_health_change(False, "easy", 120, 60, 50))
