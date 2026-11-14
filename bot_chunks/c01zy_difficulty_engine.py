# c01zy_difficulty_engine.py
import json, os

# Exact mappings from your specification
TIME_MAP = {
    1: (15, 20), 2: (20, 30), 3: (35, 45), 4: (50, 60), 5: (65, 75),
    6: (80, 90), 7: (85, 90), 8: (85, 90), 9: (90, 100), 10: (110, 120)
}

STAR_MAP = {
    1: {"AP": 1, "Main": None, "Adv": None},
    2: {"AP": None, "Main": 3, "Adv": None},
    3: {"AP": 5, "Main": 3, "Adv": None},
    4: {"AP": 6, "Main": 3.5, "Adv": 1.5},
    5: {"AP": 6, "Main": 5, "Adv": 3},
    6: {"AP": 7, "Main": 6, "Adv": 4},
    7: {"AP": 7, "Main": 7, "Adv": 5},
    8: {"AP": None, "Main": 9, "Adv": 7},
    9: {"AP": 9, "Main": 8, "Adv": 6},
    10: {"AP": 15, "Main": 13, "Adv": 10}
}

def get_ideal_time(difficulty):
    """Returns ideal and max recommended time in seconds."""
    if difficulty in TIME_MAP:
        return TIME_MAP[difficulty]
    return (60, 90) # default fallback

def get_exam_stars(difficulty):
    """Returns dict of stars for AP, Main, Adv. None means needs_calibration."""
    return STAR_MAP.get(difficulty, {"AP": None, "Main": None, "Adv": None})

def generate_question_metadata(q_id, difficulty, reason, evidence_dict):
    """Builds the exact JSON schema you requested."""
    ideal_min, ideal_max = get_ideal_time(difficulty)
    stars = get_exam_stars(difficulty)
    
    return {
        "question_id": q_id,
        "difficulty": {
            "level": difficulty,
            "reason": reason,
            "verification_status": "AI_estimated",
            "verified_by": None,
            "verification_source": None
        },
        "exam_ratings": {
            "AP_EAPCET": {"stars": stars["AP"], "status": "needs_calibration" if stars["AP"] is None else "AI_estimated"},
            "JEE_Main": {"stars": stars["Main"], "status": "needs_calibration" if stars["Main"] is None else "AI_estimated"},
            "JEE_Advanced": {"stars": stars["Adv"], "status": "needs_calibration" if stars["Adv"] is None else "AI_estimated"}
        },
        "time": {
            "ideal_seconds": ideal_max, # using the max of the range as ideal target
            "maximum_recommended_seconds": ideal_max + 30,
            "actual_student_seconds": None,
            "time_verified": False
        },
        "difficulty_evidence": evidence_dict
    }
