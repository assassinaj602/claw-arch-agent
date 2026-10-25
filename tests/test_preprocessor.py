from __future__ import annotations

import json
from pathlib import Path
import unittest

from src.agent.preprocessor import ArchitecturePreprocessor, ArchitectureIR, PlantUMLParser


DOC_PATH = Path("inputs/Architecture_Documentation.md")
VIEW_PATH = Path("inputs/Architecture_View.md")


class TestArchitecturePreprocessor(unittest.TestCase):
    def test_preprocessor_file_not_found(self) -> None:
        preprocessor = ArchitecturePreprocessor("non_existent_doc.md", VIEW_PATH)
        with self.assertRaises(FileNotFoundError):
            preprocessor.process()

    def test_preprocessor_full_pipeline(self) -> None:
        preprocessor = ArchitecturePreprocessor(DOC_PATH, VIEW_PATH)
        ir = preprocessor.process()

        self.assertIsInstance(ir, ArchitectureIR)
        self.assertEqual(ir.title, "Space Fractions System Architecture")
        self.assertEqual(ir.executive_summary["architectural_style"], "Microservices")
        self.assertEqual(len(ir.executive_summary["risks"]), 3)
        self.assertEqual(len(ir.executive_summary["qa_coverage"]), 3)

    def test_traceability_matrix(self) -> None:
        preprocessor = ArchitecturePreprocessor(DOC_PATH, VIEW_PATH)
        ir = preprocessor.process()

        matrix = ir.traceability_matrix
        self.assertGreaterEqual(len(matrix), 3)

        req_ids = [row["Requirement ID"] for row in matrix]
        self.assertIn("FR-1", req_ids)
        self.assertIn("NFR-1", req_ids)
        self.assertIn("ASR-1", req_ids)

        fr1 = next(row for row in matrix if row["Requirement ID"] == "FR-1")
        self.assertEqual(fr1["Component(s)"], "GameComponent")
        self.assertEqual(fr1["Artifact filename(s)"], "openapi.yaml")

    def test_plantuml_diagram_extraction(self) -> None:
        preprocessor = ArchitecturePreprocessor(DOC_PATH, VIEW_PATH)
        ir = preprocessor.process()

        # Extract all PlantUML blocks across 4+1 views
        self.assertEqual(len(ir.diagrams), 13)

        diag_names = [d.name for d in ir.diagrams]
        expected_names = [
            "UseCaseDiagram",
            "ClassDiagram",
            "ObjectDiagram",
            "StateDiagram",
            "ActivityDiagram",
            "SequenceDiagram1",
            "SequenceDiagram2",
            "CollaborationDiagram1",
            "CollaborationDiagram2",
            "PackageDiagram",
            "ComponentDiagram",
            "DeploymentDiagram",
            "ContainerDiagram",
        ]
        for name in expected_names:
            self.assertIn(name, diag_names)

    def test_state_diagram_transitions(self) -> None:
        preprocessor = ArchitecturePreprocessor(DOC_PATH, VIEW_PATH)
        ir = preprocessor.process()

        state_diag = next(d for d in ir.diagrams if d.name == "StateDiagram")
        self.assertEqual(state_diag.diagram_type, "state")
        self.assertIn("Playing", state_diag.entities)
        self.assertIn("Paused", state_diag.entities)
        self.assertIn("GameOver", state_diag.entities)

        events = [t["event"] for t in state_diag.metadata.get("transitions", [])]
        self.assertIn("pause()", events)
        self.assertIn("resume()", events)
        self.assertIn("gameOver()", events)

    def test_class_diagram_entities(self) -> None:
        preprocessor = ArchitecturePreprocessor(DOC_PATH, VIEW_PATH)
        ir = preprocessor.process()

        class_diag = next(d for d in ir.diagrams if d.name == "ClassDiagram")
        self.assertIn("Game", class_diag.entities)
        self.assertIn("Question", class_diag.entities)
        self.assertIn("User", class_diag.entities)
        self.assertIn("Admin", class_diag.entities)

    def test_deliverables_extraction(self) -> None:
        preprocessor = ArchitecturePreprocessor(DOC_PATH, VIEW_PATH)
        ir = preprocessor.process()

        deliverables = ir.deliverables
        self.assertIn("openapi.yaml", deliverables)
        self.assertIn("internal.proto", deliverables)
        self.assertIn("k8s/spacefractions-deployment.yaml", deliverables)
        self.assertIn("sql/game_ddl.sql", deliverables)
        self.assertIn("traceability_matrix.csv", deliverables)

        self.assertIn("openapi: 3.0.0", deliverables["openapi.yaml"])
        self.assertIn('package spacefractions;', deliverables["internal.proto"])
        self.assertIn("CREATE TABLE games", deliverables["sql/game_ddl.sql"])

    def test_json_roundtrip(self) -> None:
        import tempfile
        preprocessor = ArchitecturePreprocessor(DOC_PATH, VIEW_PATH)

        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "architecture_ir.json"
            exported_path = preprocessor.export_json(json_path)

            self.assertTrue(exported_path.exists())
            raw_data = json.loads(exported_path.read_text(encoding="utf-8"))

            reconstructed_ir = ArchitectureIR.from_dict(raw_data)
            self.assertEqual(reconstructed_ir.title, "Space Fractions System Architecture")
            self.assertEqual(len(reconstructed_ir.diagrams), 13)
            self.assertEqual(reconstructed_ir.executive_summary["architectural_style"], "Microservices")


if __name__ == "__main__":
    unittest.main()
