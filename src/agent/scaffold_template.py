from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.agent.preprocessor import ArchitectureIR


GAME_COMPONENT_PY = '''"""GameComponent domain entity managing gameplay lifecycle and state."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid


class Game:
    def __init__(self, game_id: str | None = None, score: int = 0) -> None:
        self.id: str = game_id or str(uuid.uuid4())[:8]
        self.score: int = score
        self.state: str = "Playing"
        self.current_question_idx: int = 0
        self.streak: int = 0

    def play(self) -> None:
        self.state = "Playing"

    def viewScore(self) -> int:
        return self.score

    def pause(self) -> None:
        if self.state == "Playing":
            self.state = "Paused"

    def resume(self) -> None:
        if self.state == "Paused":
            self.state = "Playing"

    def gameOver(self) -> None:
        self.state = "GameOver"

    def add_score(self, points: int) -> None:
        self.streak += 1
        bonus = self.streak * 10
        self.score += points + bonus

    def reset_streak(self) -> None:
        self.streak = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "score": self.score,
            "state": self.state,
            "streak": self.streak,
            "current_question_idx": self.current_question_idx,
        }

    def save_to_db(self, db_path: Path | str) -> None:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_state JSON NOT NULL
            )
            """
        )
        cursor.execute(
            "INSERT INTO games (game_state) VALUES (?)",
            (json.dumps(self.to_dict()),),
        )
        conn.commit()
        conn.close()
'''

QUESTION_COMPONENT_PY = '''"""QuestionComponent domain entity managing educational fraction questions."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any


class Question:
    def __init__(
        self,
        question_id: str,
        prompt: str,
        options: list[str],
        correct_option: int,
        visual_type: str = "pie",
        fraction_val: tuple[int, int] = (1, 2),
    ) -> None:
        self.id: str = question_id
        self.prompt: str = prompt
        self.options: list[str] = options
        self.correct_option: int = correct_option
        self.visual_type: str = visual_type
        self.fraction_val: tuple[int, int] = fraction_val

    def getPrompt(self) -> str:
        return self.prompt

    def getOptions(self) -> list[str]:
        return list(self.options)

    def check_answer(self, option_index: int) -> bool:
        return option_index == self.correct_option

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "options": self.options,
            "correct_option": self.correct_option,
            "visual_type": self.visual_type,
            "fraction_val": list(self.fraction_val),
        }

    @classmethod
    def load_defaults(cls) -> list[Question]:
        return [
            cls("q1", "What fraction of the spaceship energy core is charged?", ["1/4", "1/2", "3/4", "2/3"], 1, "pie", (1, 2)),
            cls("q2", "Simplify the warp drive fuel ratio: 4/8", ["1/4", "2/3", "1/2", "3/8"], 2, "bar", (4, 8)),
            cls("q3", "Add planetary distance coordinates: 1/5 + 2/5 = ?", ["3/5", "3/10", "2/25", "4/5"], 0, "pie", (3, 5)),
            cls("q4", "Which fraction represents the shaded asteroid shields?", ["2/6", "3/6 (or 1/2)", "4/6", "5/6"], 1, "pie", (3, 6)),
            cls("q5", "Solve satellite signal balance: 5/6 - 2/6 = ?", ["1/6", "3/6 (or 1/2)", "7/6", "2/3"], 1, "bar", (3, 6)),
            cls("q6", "Compare energy levels: Is 2/3 greater than 3/6?", ["Yes (2/3 > 1/2)", "No (2/3 < 1/2)", "They are equal", "Cannot determine"], 0, "bar", (2, 3)),
        ]

    @classmethod
    def init_db(cls, db_path: Path | str) -> None:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                options JSON NOT NULL,
                correct_option INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute("SELECT COUNT(*) FROM questions")
        count = cursor.fetchone()[0]
        if count == 0:
            for q in cls.load_defaults():
                cursor.execute(
                    "INSERT INTO questions (prompt, options, correct_option) VALUES (?, ?, ?)",
                    (q.prompt, json.dumps(q.options), q.correct_option),
                )
        conn.commit()
        conn.close()
'''

USER_COMPONENT_PY = '''"""UserComponent representing student players."""
from __future__ import annotations

from components.game_component import Game


class User:
    def __init__(self, user_id: str = "cadet-1", username: str = "AstroCadet") -> None:
        self.id: str = user_id
        self.username: str = username

    def playGame(self, game: Game) -> None:
        game.play()

    def viewScore(self, game: Game) -> int:
        return game.viewScore()
'''

ADMIN_COMPONENT_PY = '''"""AdminComponent representing instructors and game administrators."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from components.question_component import Question


class Admin:
    def __init__(self, admin_id: str = "admin-1", username: str = "FlightInstructor") -> None:
        self.id: str = admin_id
        self.username: str = username

    def updateQuestions(self, questions: list[Question], db_path: Path | str | None = None) -> bool:
        if not db_path:
            return True
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                options JSON NOT NULL,
                correct_option INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for q in questions:
            cursor.execute(
                "INSERT INTO questions (prompt, options, correct_option) VALUES (?, ?, ?)",
                (q.prompt, json.dumps(q.options), q.correct_option),
            )
        conn.commit()
        conn.close()
        return True
'''

SPACE_FRACTIONS_MAIN_PY = '''"""Space Fractions - Standalone Desktop Educational Math Application.
Adheres to 4+1 Architectural Views and Architecture_Documentation.md.
"""
from __future__ import annotations

import math
from pathlib import Path
import random
import sqlite3
import sys
import tkinter as tk
from tkinter import messagebox, ttk

app_dir = Path(__file__).resolve().parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from components.admin_component import Admin
from components.game_component import Game
from components.question_component import Question
from components.user_component import User

DB_PATH = Path("spacefractions.db").resolve()


class SpaceFractionsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Space Fractions - Interstellar Math Odyssey")
        self.root.geometry("860x640")
        self.root.minsize(800, 600)
        self.root.configure(bg="#0B0E14")

        Question.init_db(DB_PATH)
        self.user = User("cadet-01", "AstroCadet")
        self.admin = Admin("admin-01", "Commander")
        self.game = Game()
        self.questions = Question.load_defaults()

        self.current_q_idx = 0
        self.correct_answers_count = 0
        self.star_particles: list[dict[str, float]] = []

        self.main_container = tk.Frame(self.root, bg="#0B0E14")
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self.show_intro_movie()

    def clear_scene(self) -> None:
        for widget in self.main_container.winfo_children():
            widget.destroy()

    def show_intro_movie(self) -> None:
        self.clear_scene()

        canvas = tk.Canvas(self.main_container, bg="#05070B", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        self.star_particles = [
            {"x": random.randint(0, 860), "y": random.randint(0, 640), "speed": random.uniform(1.5, 4.5), "radius": random.uniform(1, 2.5)}
            for _ in range(70)
        ]

        title_id = canvas.create_text(430, 160, text="SPACE FRACTIONS", font=("Helvetica", 32, "bold"), fill="#00E5FF")
        sub_id = canvas.create_text(430, 220, text="Interstellar Math Flight Academy", font=("Helvetica", 14), fill="#8BE9FD")

        briefing_text = (
            "Cadet Alert: Warp drive gates ahead require precise fraction calculations.\\n"
            "Align planetary energy ratios, simplify core harmonics, and navigate to safety!"
        )
        brief_id = canvas.create_text(430, 310, text=briefing_text, font=("Consolas", 12), fill="#F8F8F2", justify=tk.CENTER)

        skip_btn = tk.Button(
            self.main_container,
            text="Skip Intro / Enter Flight Deck",
            font=("Helvetica", 11, "bold"),
            bg="#BD93F9",
            fg="#05070B",
            activebackground="#FF79C6",
            command=self.show_main_menu,
            padx=16,
            pady=8,
            relief=tk.FLAT,
        )
        skip_btn.place(relx=0.5, rely=0.76, anchor=tk.CENTER)

        ship_y = 440.0
        ship_coords = [430, ship_y, 410, ship_y + 35, 450, ship_y + 35]
        ship_id = canvas.create_polygon(ship_coords, fill="#50FA7B", outline="#F8F8F2", width=2)

        def animate_frame():
            nonlocal ship_y
            if not canvas.winfo_exists():
                return

            canvas.delete("star")
            w = canvas.winfo_width() or 860
            h = canvas.winfo_height() or 640

            for s in self.star_particles:
                s["y"] += s["speed"]
                if s["y"] > h:
                    s["y"] = 0
                    s["x"] = random.randint(0, w)
                r = s["radius"]
                canvas.create_oval(s["x"] - r, s["y"] - r, s["x"] + r, s["y"] + r, fill="#FFFFFF", outline="", tags="star")

            ship_y -= 0.6
            if ship_y < 350:
                ship_y = 440.0
            canvas.coords(ship_id, 430, ship_y, 410, ship_y + 35, 450, ship_y + 35)

            self.root.after(30, animate_frame)

        animate_frame()

    def show_main_menu(self) -> None:
        self.clear_scene()

        menu_frame = tk.Frame(self.main_container, bg="#0B0E14")
        menu_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        lbl_title = tk.Label(menu_frame, text="SPACE FRACTIONS", font=("Helvetica", 28, "bold"), fg="#00E5FF", bg="#0B0E14")
        lbl_title.pack(pady=(0, 6))

        lbl_sub = tk.Label(menu_frame, text="Mission Command - 6th Grade Math Operations", font=("Helvetica", 12), fg="#6272A4", bg="#0B0E14")
        lbl_sub.pack(pady=(0, 24))

        buttons = [
            ("Play Game", "#50FA7B", self.start_game),
            ("View Score & Records", "#8BE9FD", self.show_high_scores),
            ("View Help & Guide", "#F1FA8C", self.show_help_guide),
            ("Update Questions (Admin)", "#FFB86C", self.show_admin_panel),
        ]

        for text, color, cmd in buttons:
            btn = tk.Button(
                menu_frame,
                text=text,
                font=("Helvetica", 12, "bold"),
                bg=color,
                fg="#0B0E14",
                activebackground="#FFFFFF",
                width=26,
                pady=8,
                relief=tk.FLAT,
                command=cmd,
            )
            btn.pack(pady=7)

    def start_game(self) -> None:
        self.game = Game()
        self.user.playGame(self.game)
        self.current_q_idx = 0
        self.correct_answers_count = 0
        self.show_question_scene()

    def show_question_scene(self) -> None:
        self.clear_scene()

        if self.current_q_idx >= len(self.questions):
            self.show_ending_scene()
            return

        q = self.questions[self.current_q_idx]

        top_bar = tk.Frame(self.main_container, bg="#191A21", height=50)
        top_bar.pack(fill=tk.X, side=tk.TOP)

        lbl_progress = tk.Label(
            top_bar,
            text=f"Mission Step: {self.current_q_idx + 1} / {len(self.questions)}",
            font=("Consolas", 11, "bold"),
            fg="#8BE9FD",
            bg="#191A21",
        )
        lbl_progress.pack(side=tk.LEFT, padx=16, pady=10)

        lbl_score = tk.Label(
            top_bar,
            text=f"Score: {self.game.viewScore()} | Streak: {self.game.streak}",
            font=("Consolas", 11, "bold"),
            fg="#50FA7B",
            bg="#191A21",
        )
        lbl_score.pack(side=tk.LEFT, padx=20, pady=10)

        btn_pause = tk.Button(
            top_bar,
            text="Pause [State: Playing]",
            font=("Consolas", 10, "bold"),
            bg="#FF5555",
            fg="#FFFFFF",
            relief=tk.FLAT,
            command=self.pause_game_modal,
        )
        btn_pause.pack(side=tk.RIGHT, padx=16, pady=8)

        body = tk.Frame(self.main_container, bg="#0B0E14")
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=16)

        lbl_prompt = tk.Label(
            body,
            text=q.getPrompt(),
            font=("Helvetica", 15, "bold"),
            fg="#F8F8F2",
            bg="#0B0E14",
            wraplength=760,
        )
        lbl_prompt.pack(pady=(10, 16))

        canvas = tk.Canvas(body, width=320, height=180, bg="#12151D", highlightthickness=1, highlightbackground="#44475A")
        canvas.pack(pady=8)
        self._render_fraction_graphic(canvas, q)

        opts_frame = tk.Frame(body, bg="#0B0E14")
        opts_frame.pack(fill=tk.X, pady=16)

        for i, opt in enumerate(q.getOptions()):
            btn = tk.Button(
                opts_frame,
                text=f"({chr(65 + i)}) {opt}",
                font=("Helvetica", 11, "bold"),
                bg="#282A36",
                fg="#F8F8F2",
                activebackground="#6272A4",
                activeforeground="#FFFFFF",
                relief=tk.FLAT,
                padx=14,
                pady=10,
                command=lambda opt_idx=i: self._submit_answer(opt_idx),
            )
            btn.pack(fill=tk.X, pady=4, padx=40)

    def _render_fraction_graphic(self, canvas: tk.Canvas, question: Question) -> None:
        num, den = question.fraction_val
        if den <= 0:
            den = 1

        if question.visual_type == "pie":
            cx, cy, r = 160, 90, 70
            start_angle = 0.0
            angle_step = 360.0 / den

            for slice_i in range(den):
                fill_color = "#50FA7B" if slice_i < num else "#44475A"
                canvas.create_arc(
                    cx - r, cy - r, cx + r, cy + r,
                    start=start_angle,
                    extent=angle_step,
                    fill=fill_color,
                    outline="#0B0E14",
                    width=2,
                    style=tk.PIESLICE,
                )
                start_angle += angle_step

            canvas.create_text(cx, cy, text=f"{num}/{den}", font=("Consolas", 12, "bold"), fill="#0B0E14")

        else:
            x0, y0, total_w, total_h = 40, 65, 240, 50
            cell_w = total_w / den

            for col in range(den):
                fill_color = "#00E5FF" if col < num else "#282A36"
                canvas.create_rectangle(
                    x0 + col * cell_w, y0,
                    x0 + (col + 1) * cell_w, y0 + total_h,
                    fill=fill_color,
                    outline="#F8F8F2",
                    width=1,
                )

            canvas.create_text(160, 140, text=f"Fuel Ratio: {num}/{den}", font=("Consolas", 11), fill="#8BE9FD")

    def _submit_answer(self, option_index: int) -> None:
        q = self.questions[self.current_q_idx]
        is_correct = q.check_answer(option_index)

        if is_correct:
            self.correct_answers_count += 1
            self.game.add_score(100)
            messagebox.showinfo("Trajectory Correct!", "Coordinate confirmed. +100 Points with Warp Boost!")
        else:
            self.game.reset_streak()
            messagebox.showwarning("Navigation Warning", f"Incorrect calculation. Correct option was: {q.getOptions()[q.correct_option]}")

        self.current_q_idx += 1
        self.show_question_scene()

    def pause_game_modal(self) -> None:
        self.game.pause()

        modal = tk.Toplevel(self.root)
        modal.title("Game Paused")
        modal.geometry("340x220")
        modal.configure(bg="#1E1F29")
        modal.transient(self.root)
        modal.grab_set()

        lbl = tk.Label(modal, text="MISSION PAUSED", font=("Helvetica", 14, "bold"), fg="#FF5555", bg="#1E1F29")
        lbl.pack(pady=20)

        def do_resume():
            self.game.resume()
            modal.destroy()

        def do_quit():
            self.game.gameOver()
            modal.destroy()
            self.show_main_menu()

        tk.Button(modal, text="Resume Mission", font=("Helvetica", 11, "bold"), bg="#50FA7B", fg="#0B0E14", width=18, pady=6, relief=tk.FLAT, command=do_resume).pack(pady=6)
        tk.Button(modal, text="Abort to Main Menu", font=("Helvetica", 11), bg="#6272A4", fg="#FFFFFF", width=18, pady=6, relief=tk.FLAT, command=do_quit).pack(pady=6)

    def show_ending_scene(self) -> None:
        self.game.gameOver()
        self.game.save_to_db(DB_PATH)
        self.clear_scene()

        frame = tk.Frame(self.main_container, bg="#0B0E14")
        frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        total_q = len(self.questions)
        pct = (self.correct_answers_count / total_q) * 100 if total_q else 0

        title_color = "#50FA7B" if pct >= 60 else "#FFB86C"
        lbl_title = tk.Label(frame, text="MISSION COMPLETE", font=("Helvetica", 24, "bold"), fg=title_color, bg="#0B0E14")
        lbl_title.pack(pady=(0, 10))

        score_text = (
            f"Final Flight Score: {self.game.viewScore()} Points\\n"
            f"Accuracy: {self.correct_answers_count}/{total_q} ({pct:.1f}%)\\n\\n"
        )
        if pct >= 80:
            score_text += "Rank: Master Space Navigator! Superb fraction operations."
        elif pct >= 50:
            score_text += "Rank: Astro Pilot. Solid coordinates; keep refining fraction addition."
        else:
            score_text += "Rank: Cadet in Training. Review basic fractions and retry flight."

        lbl_score = tk.Label(frame, text=score_text, font=("Consolas", 12), fg="#F8F8F2", bg="#0B0E14", justify=tk.CENTER)
        lbl_score.pack(pady=10)

        btn_again = tk.Button(frame, text="Play Again", font=("Helvetica", 11, "bold"), bg="#50FA7B", fg="#0B0E14", width=20, pady=6, relief=tk.FLAT, command=self.start_game)
        btn_again.pack(pady=6)

        btn_menu = tk.Button(frame, text="Return to Main Menu", font=("Helvetica", 11), bg="#8BE9FD", fg="#0B0E14", width=20, pady=6, relief=tk.FLAT, command=self.show_main_menu)
        btn_menu.pack(pady=6)

    def show_high_scores(self) -> None:
        self.clear_scene()

        frame = tk.Frame(self.main_container, bg="#0B0E14")
        frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=30)

        lbl = tk.Label(frame, text="Mission Records (SQLite Persistence)", font=("Helvetica", 18, "bold"), fg="#8BE9FD", bg="#0B0E14")
        lbl.pack(pady=(0, 16))

        box = tk.Listbox(frame, bg="#191A21", fg="#F8F8F2", font=("Consolas", 11), width=65, height=14, relief=tk.FLAT)
        box.pack(pady=8)

        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS games (id INTEGER PRIMARY KEY AUTOINCREMENT, game_state JSON NOT NULL)")
        cursor.execute("SELECT id, game_state FROM games ORDER BY id DESC LIMIT 15")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            box.insert(tk.END, "No saved flight logs found yet.")
        else:
            for r_id, raw_state in rows:
                try:
                    state_obj = json.loads(raw_state)
                    score = state_obj.get("score", 0)
                    streak = state_obj.get("streak", 0)
                    box.insert(tk.END, f"Flight #{r_id:03d} | Score: {score:4d} | Max Streak: {streak:2d} | Status: Recorded")
                except Exception:
                    box.insert(tk.END, f"Flight #{r_id:03d} | Raw: {raw_state[:50]}")

        tk.Button(frame, text="Back to Main Menu", font=("Helvetica", 11), bg="#6272A4", fg="#FFFFFF", relief=tk.FLAT, command=self.show_main_menu).pack(pady=12)

    def show_help_guide(self) -> None:
        self.clear_scene()

        frame = tk.Frame(self.main_container, bg="#0B0E14")
        frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=30)

        lbl = tk.Label(frame, text="Astro-Nav Guide: 6th Grade Fraction Rules", font=("Helvetica", 18, "bold"), fg="#F1FA8C", bg="#0B0E14")
        lbl.pack(pady=(0, 16))

        guide = (
            "1. Parts of a Fraction: The Numerator (top) represents active parts.\\n"
            "   The Denominator (bottom) represents total equal divisions in the core.\\n\\n"
            "2. Adding with Like Denominators: Add numerators directly: 1/5 + 2/5 = 3/5.\\n\\n"
            "3. Simplifying Ratios: Divide numerator and denominator by their greatest\\n"
            "   common divisor: 4/8 = 1/2.\\n\\n"
            "4. Streaks: Answer questions in succession without errors to unlock speed bonuses!"
        )

        lbl_guide = tk.Label(frame, text=guide, font=("Consolas", 11), fg="#F8F8F2", bg="#191A21", justify=tk.LEFT, padx=16, pady=16)
        lbl_guide.pack(fill=tk.X, pady=8)

        tk.Button(frame, text="Back to Main Menu", font=("Helvetica", 11), bg="#6272A4", fg="#FFFFFF", relief=tk.FLAT, command=self.show_main_menu).pack(pady=16)

    def show_admin_panel(self) -> None:
        self.clear_scene()

        frame = tk.Frame(self.main_container, bg="#0B0E14")
        frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=30)

        lbl = tk.Label(frame, text="Admin Question Pool Editor (SequenceDiagram2)", font=("Helvetica", 18, "bold"), fg="#FFB86C", bg="#0B0E14")
        lbl.pack(pady=(0, 16))

        form = tk.Frame(frame, bg="#191A21", padx=16, pady=16)
        form.pack(fill=tk.X)

        tk.Label(form, text="Question Prompt:", fg="#F8F8F2", bg="#191A21").grid(row=0, column=0, sticky=tk.W, pady=4)
        entry_prompt = tk.Entry(form, width=50)
        entry_prompt.insert(0, "Calculate sector fuel: 2/7 + 3/7 = ?")
        entry_prompt.grid(row=0, column=1, sticky=tk.W, pady=4)

        tk.Label(form, text="Options (comma separated):", fg="#F8F8F2", bg="#191A21").grid(row=1, column=0, sticky=tk.W, pady=4)
        entry_opts = tk.Entry(form, width=50)
        entry_opts.insert(0, "5/7, 5/14, 6/7, 1/7")
        entry_opts.grid(row=1, column=1, sticky=tk.W, pady=4)

        tk.Label(form, text="Correct Index (0-3):", fg="#F8F8F2", bg="#191A21").grid(row=2, column=0, sticky=tk.W, pady=4)
        entry_correct = tk.Entry(form, width=10)
        entry_correct.insert(0, "0")
        entry_correct.grid(row=2, column=1, sticky=tk.W, pady=4)

        def save_q():
            p = entry_prompt.get().strip()
            opts = [o.strip() for o in entry_opts.get().split(",")]
            try:
                c = int(entry_correct.get().strip())
            except ValueError:
                c = 0

            new_q = Question(f"admin-{len(self.questions) + 1}", p, opts, c, "bar", (1, 2))
            self.admin.updateQuestions([new_q], DB_PATH)
            self.questions.append(new_q)
            messagebox.showinfo("Admin Update", "New question successfully persisted to SQLite database!")

        tk.Button(form, text="Save to Question Pool", font=("Helvetica", 10, "bold"), bg="#50FA7B", fg="#0B0E14", command=save_q).grid(row=3, column=1, sticky=tk.W, pady=12)
        tk.Button(frame, text="Back to Main Menu", font=("Helvetica", 11), bg="#6272A4", fg="#FFFFFF", relief=tk.FLAT, command=self.show_main_menu).pack(pady=16)


def main() -> None:
    root = tk.Tk()
    app = SpaceFractionsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
'''

TEST_SPACE_FRACTIONS_PY = '''"""Unit and integration test suite for Space Fractions application."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from components.admin_component import Admin
from components.game_component import Game
from components.question_component import Question
from components.user_component import User


class TestSpaceFractions(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_spacefractions.db"

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_game_component_state_machine(self) -> None:
        game = Game()
        self.assertEqual(game.state, "Playing")

        game.pause()
        self.assertEqual(game.state, "Paused")

        game.resume()
        self.assertEqual(game.state, "Playing")

        game.gameOver()
        self.assertEqual(game.state, "GameOver")

    def test_game_scoring_and_streaks(self) -> None:
        game = Game()
        self.assertEqual(game.viewScore(), 0)

        game.add_score(100)
        self.assertEqual(game.viewScore(), 110)
        self.assertEqual(game.streak, 1)

        game.add_score(100)
        self.assertEqual(game.viewScore(), 230)
        self.assertEqual(game.streak, 2)

        game.reset_streak()
        self.assertEqual(game.streak, 0)

    def test_game_sqlite_persistence(self) -> None:
        game = Game()
        game.add_score(200)
        game.save_to_db(self.db_path)

        self.assertTrue(self.db_path.exists())

    def test_question_component_logic(self) -> None:
        q = Question("q1", "What is 1/2 + 1/2?", ["1", "1/4", "2/4", "0"], 0)
        self.assertEqual(q.getPrompt(), "What is 1/2 + 1/2?")
        self.assertEqual(len(q.getOptions()), 4)
        self.assertTrue(q.check_answer(0))
        self.assertFalse(q.check_answer(1))

    def test_admin_update_questions(self) -> None:
        admin = Admin("adm-1", "Instructor")
        new_q = Question("q_custom", "Simplify 2/4", ["1/2", "1/4", "1", "2"], 0)
        res = admin.updateQuestions([new_q], self.db_path)
        self.assertTrue(res)

    def test_user_interaction(self) -> None:
        user = User("u1", "Cadet")
        game = Game()
        user.playGame(game)
        self.assertEqual(game.state, "Playing")
        self.assertEqual(user.viewScore(game), 0)


if __name__ == "__main__":
    unittest.main()
'''


def synthesize_space_fractions_project(output_dir: Path | str, ir: ArchitectureIR) -> list[str]:
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    components_dir = out_dir / "components"
    components_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "components/__init__.py": "# components package\n",
        "components/game_component.py": GAME_COMPONENT_PY,
        "components/question_component.py": QUESTION_COMPONENT_PY,
        "components/user_component.py": USER_COMPONENT_PY,
        "components/admin_component.py": ADMIN_COMPONENT_PY,
        "main.py": SPACE_FRACTIONS_MAIN_PY,
        "requirements.txt": "# Standard library preferred; no external wheel compilation required\n",
        "Dockerfile": (
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY . /app\n"
            "RUN apt-get update && apt-get install -y python3-tk && rm -rf /var/lib/apt/lists/*\n"
            "CMD [\"python\", \"main.py\"]\n"
        ),
        "README.md": (
            "# Space Fractions Desktop Application\n\n"
            "Educational math software designed for sixth-grade fraction learning.\n"
            "Adheres to the 4+1 Architectural Views and Microservices specification.\n\n"
            "## Running the Application\n\n"
            "```bash\n"
            "python main.py\n"
            "```\n\n"
            "## Running Tests\n\n"
            "```bash\n"
            "python -m unittest discover tests -v\n"
            "```\n"
        ),
        "tests/__init__.py": "# tests package\n",
        "tests/test_space_fractions.py": TEST_SPACE_FRACTIONS_PY,
    }

    for rel_path, content in files.items():
        p = out_dir / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        created.append(rel_path)

    # Scaffolding contracts
    deliverables = ir.deliverables
    for fn, text in deliverables.items():
        if fn in ("manifest_list", "architecture.md"):
            continue
        p = out_dir / fn
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        created.append(fn)

    q_sql = out_dir / "sql/question_ddl.sql"
    if not q_sql.exists():
        q_sql.parent.mkdir(parents=True, exist_ok=True)
        q_sql.write_text(
            "CREATE TABLE questions (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  prompt TEXT NOT NULL,\n"
            "  options JSONB NOT NULL,\n"
            "  correct_option INTEGER NOT NULL,\n"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
            ");\n",
            encoding="utf-8",
        )
        created.append("sql/question_ddl.sql")

    matrix_path = out_dir / "traceability_matrix.csv"
    if not matrix_path.exists() and ir.traceability_matrix:
        headers = ["Requirement ID", "Short Text", "Diagram(s)", "Component(s)", "Artifact filename(s)", "Rationale"]
        csv_lines = [",".join(headers)]
        for row in ir.traceability_matrix:
            csv_lines.append(",".join(f'"{row.get(h, "")}"' for h in headers))
        matrix_path.parent.mkdir(parents=True, exist_ok=True)
        matrix_path.write_text("\n".join(csv_lines), encoding="utf-8")
        created.append("traceability_matrix.csv")

    ir_path = out_dir / "architecture_ir.json"
    ir_path.write_text(ir.to_json(), encoding="utf-8")
    created.append("architecture_ir.json")

    return created
