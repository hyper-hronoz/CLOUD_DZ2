from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESPONSES_FILE = DATA_DIR / "responses.csv"

app = Flask(__name__)


@dataclass(frozen=True)
class Question:
    key: str
    prompt: str
    options: list[str]
    correct_answer: str


QUESTIONS = [
    Question(
        key="q1",
        prompt="Какой инструмент на картине выглядит так, будто вот-вот начнет соло на весь рай и ад?",
        options=["Лютня", "Арфа", "Барабан", "Волынка"],
        correct_answer="Лютня",
    ),
    Question(
        key="q2",
        prompt="Какой инструмент чаще всего узнают на фрагменте с гигантскими музыкальными объектами?",
        options=["Треугольник", "Ноты на ягоде", "Арфа", "Флейта"],
        correct_answer="Арфа",
    ),
    Question(
        key="q3",
        prompt="Какой инструмент на картине лучше всего подходит для максимально драматичного вступления?",
        options=["Барабан", "Свирель", "Колокольчик", "Бубен"],
        correct_answer="Барабан",
    ),
    Question(
        key="q4",
        prompt="Какой инструмент ассоциируется с самым мемным образом на правой створке триптиха?",
        options=["Лютня", "Арфа", "Волынка", "Орган"],
        correct_answer="Волынка",
    ),
    Question(
        key="q5",
        prompt="Какой инструмент звучал бы наиболее уместно, если бы персонажи внезапно устроили средневековый джем?",
        options=["Флейта", "Электрогитара", "Синтезатор", "Саксофон"],
        correct_answer="Флейта",
    ),
    Question(
        key="q6",
        prompt="Если верить босховскому визуальному хаосу, какой инструмент мог бы руководить всем этим оркестром странностей?",
        options=["Арфа", "Лютня", "Волынка", "Барабан"],
        correct_answer="Волынка",
    ),
]


def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not RESPONSES_FILE.exists():
        with RESPONSES_FILE.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "submitted_at",
                    "first_name",
                    "last_name",
                    *(question.key for question in QUESTIONS),
                    "score",
                    "rating_label",
                ],
            )
            writer.writeheader()


def normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).title()


def calculate_score(answers: dict[str, str]) -> tuple[int, str]:
    score = sum(
        1 for question in QUESTIONS if answers.get(question.key) == question.correct_answer
    )

    return score, get_rating_label(score)


def get_rating_label(score: int) -> str:
    if score <= 2:
        return "Новичок в оркестре Босха"
    if score <= 4:
        return "Уверенный слушатель адского ансамбля"
    return "Маэстро босховских инструментов"


def load_recent_results(limit: int = 10) -> list[dict[str, str]]:
    ensure_storage()
    with RESPONSES_FILE.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return list(reversed(rows[-limit:]))


@app.route("/")
def index():
    return render_template("index.html", questions=QUESTIONS)


@app.route("/submit", methods=["POST"])
def submit():
    ensure_storage()

    first_name = normalize_name(request.form.get("first_name", ""))
    last_name = normalize_name(request.form.get("last_name", ""))

    if not first_name or not last_name:
        return render_template(
            "index.html",
            questions=QUESTIONS,
            error="Нужно указать имя и фамилию.",
            form_data=request.form,
        )

    answers = {}
    for question in QUESTIONS:
        value = request.form.get(question.key, "").strip()
        if not value:
            return render_template(
                "index.html",
                questions=QUESTIONS,
                error="Нужно ответить на все вопросы.",
                form_data=request.form,
            )
        answers[question.key] = value

    score, rating = calculate_score(answers)
    row = {
        "submitted_at": datetime.now().isoformat(timespec="seconds"),
        "first_name": first_name,
        "last_name": last_name,
        **answers,
        "score": score,
        "rating_label": rating,
    }

    with RESPONSES_FILE.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=row.keys())
        writer.writerow(row)

    return redirect(url_for("result", first_name=first_name, last_name=last_name, score=score))


@app.route("/result")
def result():
    first_name = request.args.get("first_name", "")
    last_name = request.args.get("last_name", "")
    score = int(request.args.get("score", "0"))
    rating = get_rating_label(score)

    return render_template(
        "result.html",
        first_name=first_name,
        last_name=last_name,
        score=score,
        total=len(QUESTIONS),
        rating=rating,
    )


@app.route("/stats")
def stats():
    recent_results = load_recent_results()
    return render_template("stats.html", results=recent_results, total=len(recent_results))


if __name__ == "__main__":
    ensure_storage()
    app.run(debug=True)
