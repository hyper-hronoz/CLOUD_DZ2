from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESPONSES_FILE = DATA_DIR / "responses.csv"
CLASSMATES_FILE = DATA_DIR / "classmates.txt"
DZ1_STUDENTS_FILE = BASE_DIR.parent / "dz1" / "students.json"

QUESTIONS = {
    "q1": ("Какой инструмент выглядит как главный солист?", "Лютня"),
    "q2": ("Какой инструмент чаще всего узнают на фрагменте?", "Арфа"),
    "q3": ("Что подходит для драматичного вступления?", "Барабан"),
    "q4": ("Какой инструмент самый мемный на правой створке?", "Волынка"),
    "q5": ("Что уместнее всего для средневекового джема?", "Флейта"),
    "q6": ("Кто мог бы руководить оркестром странностей?", "Волынка"),
}


def normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).title()


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value).lower().strip())
    text = text.replace("ё", "е").replace("-", " ")
    text = re.sub(r"[^а-яa-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize_name(name: str) -> list[str]:
    return normalize_text(name).split()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def name_match_score(entered_name: str, student_name: str) -> float:
    entered_tokens = tokenize_name(entered_name)
    student_tokens = tokenize_name(student_name)

    if not entered_tokens or not student_tokens:
        return 0.0

    best_for_entered = sum(
        max(similarity(entered_token, student_token) for student_token in student_tokens)
        for entered_token in entered_tokens
    ) / len(entered_tokens)
    best_for_student = sum(
        max(similarity(student_token, entered_token) for entered_token in entered_tokens)
        for student_token in student_tokens
    ) / len(student_tokens)
    overlap = len(set(entered_tokens) & set(student_tokens))
    sorted_similarity = similarity(
        " ".join(sorted(entered_tokens)),
        " ".join(sorted(student_tokens)),
    )

    return best_for_entered * 1.2 + best_for_student * 1.2 + sorted_similarity + overlap * 0.8


def find_student(entered_name: str, students: list[str]) -> str | None:
    if not students:
        return None

    ranked = sorted(
        ((name_match_score(entered_name, student), student) for student in students),
        reverse=True,
    )
    best_score, best_student = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0

    if best_score >= 2.5 and best_score - second_score >= 0.35:
        return best_student
    return None


def load_classmates() -> list[str]:
    if CLASSMATES_FILE.exists():
        with CLASSMATES_FILE.open("r", encoding="utf-8") as file:
            local_students = [normalize_name(line) for line in file if line.strip()]
        if local_students:
            return local_students

    if DZ1_STUDENTS_FILE.exists():
        with DZ1_STUDENTS_FILE.open("r", encoding="utf-8") as file:
            raw_students = json.load(file)
        return [normalize_name(name) for name in raw_students if str(name).strip()]

    return []


def load_responses() -> list[dict[str, str]]:
    if not RESPONSES_FILE.exists():
        return []
    with RESPONSES_FILE.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def get_period(hour: int) -> str:
    if 6 <= hour < 12:
        return "Утро"
    if 12 <= hour < 18:
        return "День"
    if 18 <= hour < 24:
        return "Вечер"
    return "Ночь"


def main() -> None:
    classmates = load_classmates()
    responses = load_responses()

    if not responses:
        print("Ответов пока нет. Сначала соберите результаты опроса.")
        return

    latest_attempts: dict[str, dict[str, str]] = {}
    unmatched_names: list[str] = []

    for row in responses:
        first_name = row.get("first_name", "").strip()
        last_name = row.get("last_name", "").strip()
        raw_name = normalize_name(f"{last_name} {first_name}")
        matched_student = find_student(raw_name, classmates)

        if not matched_student:
            if raw_name:
                unmatched_names.append(raw_name)
            continue

        submitted_at = row.get("submitted_at", "")
        current = latest_attempts.get(matched_student)
        if current is None or submitted_at > current.get("submitted_at", ""):
            latest_attempts[matched_student] = row

    missing = sorted(student for student in classmates if student not in latest_attempts)
    valid_responses = list(latest_attempts.values())

    question_stats = {}
    for key, (text, correct_answer) in QUESTIONS.items():
        total = sum(1 for row in valid_responses if row.get(key))
        correct = sum(1 for row in valid_responses if row.get(key) == correct_answer)
        accuracy = correct / total if total else 0
        question_stats[key] = {
            "text": text,
            "correct": correct,
            "total": total,
            "accuracy": accuracy,
        }

    hardest_key = min(question_stats, key=lambda item: question_stats[item]["accuracy"])
    scores = [int(row["score"]) for row in valid_responses if row.get("score")]
    average_score = sum(scores) / len(scores) if scores else 0

    period_counter = Counter()
    for row in valid_responses:
        submitted_at = row.get("submitted_at", "")
        if not submitted_at:
            continue
        dt = datetime.fromisoformat(submitted_at)
        period_counter[get_period(dt.hour)] += 1

    preferred_period = "Нет данных"
    if period_counter:
        preferred_period = period_counter.most_common(1)[0][0]

    print("Анализ результатов опроса")
    print()
    if CLASSMATES_FILE.exists():
        print(f"Источник списка группы: {CLASSMATES_FILE}")
    elif DZ1_STUDENTS_FILE.exists():
        print(f"Источник списка группы: {DZ1_STUDENTS_FILE}")
    else:
        print("Источник списка группы: не найден, список непринявших участие может быть пустым.")
    print()
    print(f"Всего записей в результатах: {len(responses)}")
    print(f"Распознано участников по fuzzy-сопоставлению: {len(valid_responses)}")
    print(f"Средняя оценка: {average_score:.2f} из {len(QUESTIONS)}")
    print()

    print("Кто не проходил опрос:")
    if missing:
        for name in missing:
            print(f"- {name}")
    else:
        print("- Все из списка одногруппников прошли опрос.")
    print()

    if unmatched_names:
        print("Не удалось однозначно сопоставить имена:")
        for name in sorted(set(unmatched_names)):
            print(f"- {name}")
        print()

    hardest = question_stats[hardest_key]
    print("Самый сложный вопрос:")
    print(
        f"- {hardest['text']} "
        f"(верных ответов: {hardest['correct']} из {hardest['total']}, "
        f"точность: {hardest['accuracy']:.0%})"
    )
    print()

    print("Предпочтительное время суток:")
    print(f"- {preferred_period}")


if __name__ == "__main__":
    main()
