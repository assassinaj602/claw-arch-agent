"""Unit and integration test suite for Space Fractions application."""
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
