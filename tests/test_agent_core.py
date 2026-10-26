from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.agent.context_compressor import ContextCompressor
from src.agent.preprocessor import ArchitecturePreprocessor
from src.agent.token_ledger import BudgetExceededError, TokenLedger
from src.agent.tools import ToolExecutionError, ToolRegistry


DOC_PATH = Path("inputs/Architecture_Documentation.md")
VIEW_PATH = Path("inputs/Architecture_View.md")


class TestTokenLedger(unittest.TestCase):
    def test_cost_calculation_rates(self) -> None:
        ledger = TokenLedger(
            input_rate_per_m=0.27,
            cached_input_rate_per_m=0.07,
            output_rate_per_m=1.10,
        )

        cost = ledger.calculate_cost(prompt_tokens=1_000_000, completion_tokens=1_000_000, cached_tokens=500_000)
        expected = (0.5 * 0.27) + (0.5 * 0.07) + (1.0 * 1.10)
        self.assertAlmostEqual(cost, expected, places=4)

    def test_record_turn_and_summary(self) -> None:
        ledger = TokenLedger(budget_limit_usd=1.00)
        usage = ledger.record_turn(prompt_tokens=10_000, completion_tokens=2_000, cached_tokens=3_000)

        self.assertGreater(usage.cost_usd, 0.0)
        self.assertEqual(ledger.total_prompt_tokens, 10_000)
        self.assertEqual(ledger.total_completion_tokens, 2_000)
        self.assertEqual(ledger.total_cached_tokens, 3_000)

        summary = ledger.get_summary()
        self.assertEqual(summary["total_tokens"], 12_000)
        self.assertLess(summary["total_cost_usd"], 0.10)

    def test_budget_exceeded_watchdog(self) -> None:
        ledger = TokenLedger(budget_limit_usd=0.05)
        with self.assertRaises(BudgetExceededError):
            ledger.record_turn(prompt_tokens=1_000_000, completion_tokens=1_000_000)


class TestToolRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.tmp_dir.name)
        preprocessor = ArchitecturePreprocessor(DOC_PATH, VIEW_PATH)
        self.ir = preprocessor.process()
        self.tools = ToolRegistry(self.output_dir, self.ir)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_path_containment_guard(self) -> None:
        with self.assertRaises(ToolExecutionError):
            self.tools.write_file("../../outside.txt", "malicious payload")

    def test_scaffold_contracts_from_ir(self) -> None:
        result = self.tools.scaffold_contracts_from_ir()
        self.assertIn("Materialized", result)

        self.assertTrue((self.output_dir / "openapi.yaml").exists())
        self.assertTrue((self.output_dir / "internal.proto").exists())
        self.assertTrue((self.output_dir / "k8s/spacefractions-deployment.yaml").exists())
        self.assertTrue((self.output_dir / "sql/game_ddl.sql").exists())
        self.assertTrue((self.output_dir / "sql/question_ddl.sql").exists())
        self.assertTrue((self.output_dir / "traceability_matrix.csv").exists())
        self.assertTrue((self.output_dir / "architecture_ir.json").exists())

    def test_pre_edit_read_guard_enforcement(self) -> None:
        target = self.output_dir / "test_module.py"
        target.write_text("x = 10\n", encoding="utf-8")

        res = self.tools.edit_file("test_module.py", "x = 10", "x = 20")
        self.assertIn("Tool Safety Violation", res)
        self.assertIn("claw-code pre-edit read policy", res)

        read_res = self.tools.read_file("test_module.py")
        self.assertEqual(read_res, "x = 10\n")

        edit_res = self.tools.edit_file("test_module.py", "x = 10", "x = 20")
        self.assertIn("Successfully replaced", edit_res)
        self.assertEqual(target.read_text(encoding="utf-8"), "x = 20\n")

    def test_inprocess_verification(self) -> None:
        verif1 = self.tools.run_verification()
        self.assertIn("[FAIL]", verif1)
        self.assertIn("Missing required deliverable files", verif1)

        self.tools.scaffold_contracts_from_ir()
        self.tools.write_file("main.py", "def run():\n    return 'running'\n")
        self.tools.write_file("requirements.txt", "# standard\n")
        self.tools.write_file("Dockerfile", "FROM python:3.11-slim\n")
        self.tools.write_file("README.md", "# Space Fractions\n")

        test_code = (
            "import sys\n"
            "from pathlib import Path\n"
            "root = Path(__file__).resolve().parent.parent\n"
            "if str(root) not in sys.path: sys.path.insert(0, str(root))\n"
            "import unittest\n"
            "from main import run\n\n"
            "class TestGame(unittest.TestCase):\n"
            "    def test_run(self):\n"
            "        self.assertEqual(run(), 'running')\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        self.tools.write_file("tests/test_space_fractions.py", test_code)

        verif2 = self.tools.run_verification()
        self.assertIn("[PASS] All required architectural deliverables present", verif2)
        self.assertIn("[PASS] AST syntax compiled cleanly", verif2)
        self.assertTrue(
            "[PASS] In-process unit test suite passed" in verif2
            or "[PASS] Pytest suite executed and passed successfully" in verif2
        )


class TestContextCompressor(unittest.TestCase):
    def test_level1_trim_long_outputs(self) -> None:
        compressor = ContextCompressor(max_tool_output_chars=200)
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "task prompt"},
            {
                "role": "assistant",
                "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "test_fn"}}],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "A" * 500},
        ]

        compressed = compressor.compress(messages)
        tool_content = compressed[3]["content"]
        self.assertIn("truncated by context compressor", tool_content)
        self.assertLess(len(tool_content), 300)

    def test_atomic_pairing_invariants_during_folding(self) -> None:
        compressor = ContextCompressor(
            fold_threshold_messages=6,
            keep_recent_atomic_turns=1,
        )

        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "user"},
        ]

        # Generate 4 turns of parallel tool calls
        for turn_idx in range(4):
            t1 = f"call_{turn_idx}_a"
            t2 = f"call_{turn_idx}_b"
            messages.append({
                "role": "assistant",
                "tool_calls": [
                    {"id": t1, "type": "function", "function": {"name": "tool_a"}},
                    {"id": t2, "type": "function", "function": {"name": "tool_b"}},
                ],
            })
            messages.append({"role": "tool", "tool_call_id": t1, "content": f"result {t1}"})
            messages.append({"role": "tool", "tool_call_id": t2, "content": f"result {t2}"})

        compressed = compressor.compress(messages)

        # Validate message invariants: every 'tool' message must be preceded by 'assistant' or 'tool'
        ContextCompressor._validate_message_invariants(compressed)
        self.assertLess(len(compressed), len(messages))

        # Check that the most recent atomic group is preserved
        last_tool_id = compressed[-1]["tool_call_id"]
        self.assertTrue(last_tool_id.startswith("call_3"))


if __name__ == "__main__":
    unittest.main()

