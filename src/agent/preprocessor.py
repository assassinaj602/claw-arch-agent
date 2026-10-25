from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PlantUMLDiagram:
    name: str
    view: str
    diagram_type: str
    raw_content: str
    entities: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchitectureIR:
    title: str
    executive_summary: dict[str, Any] = field(default_factory=dict)
    traceability_matrix: list[dict[str, str]] = field(default_factory=list)
    components: dict[str, Any] = field(default_factory=dict)
    operations: dict[str, Any] = field(default_factory=dict)
    security: dict[str, Any] = field(default_factory=dict)
    observability: dict[str, Any] = field(default_factory=dict)
    testing_strategy: dict[str, Any] = field(default_factory=dict)
    deliverables: dict[str, str] = field(default_factory=dict)
    diagrams: list[PlantUMLDiagram] = field(default_factory=list)
    raw_sections: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchitectureIR:
        diagrams_data = data.pop("diagrams", [])
        diagrams = [PlantUMLDiagram(**d) for d in diagrams_data]
        return cls(diagrams=diagrams, **data)


class MarkdownTableParser:
    @staticmethod
    def parse_table(table_text: str) -> list[dict[str, str]]:
        table_lines = [line.strip() for line in table_text.strip().splitlines() if line.strip().startswith("|")]
        if len(table_lines) < 2:
            return []

        headers = [h.strip() for h in table_lines[0].strip("|").split("|")]

        rows: list[dict[str, str]] = []
        for line in table_lines[2:]:
            if not line.startswith("|"):
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) != len(headers):
                continue
            rows.append(dict(zip(headers, cols)))
        return rows


class PlantUMLParser:
    _DIAGRAM_PATTERN = re.compile(
        r"@startuml\s*([a-zA-Z0-9_]*)\s*\n(.*?)@enduml",
        re.DOTALL,
    )

    @classmethod
    def parse_views(cls, content: str) -> list[PlantUMLDiagram]:
        diagrams: list[PlantUMLDiagram] = []
        current_view = "General"

        view_sections = re.split(r"(##\s+[A-Za-z0-9_]+View)", content)
        for i in range(1, len(view_sections), 2):
            view_header = view_sections[i].strip()
            view_body = view_sections[i + 1] if i + 1 < len(view_sections) else ""
            current_view = view_header.replace("##", "").strip()

            for match in cls._DIAGRAM_PATTERN.finditer(view_body):
                diag_name = match.group(1).strip()
                diag_body = match.group(2).strip()
                parsed = cls._parse_diagram_body(diag_name, current_view, diag_body)
                diagrams.append(parsed)

        if not diagrams:
            for match in cls._DIAGRAM_PATTERN.finditer(content):
                diag_name = match.group(1).strip()
                diag_body = match.group(2).strip()
                diagrams.append(cls._parse_diagram_body(diag_name, "General", diag_body))

        return diagrams

    @classmethod
    def _parse_diagram_body(
        cls,
        name: str,
        view: str,
        body: str,
    ) -> PlantUMLDiagram:
        diag_type = cls._infer_diagram_type(name, body)
        entities: list[str] = []
        relationships: list[str] = []
        metadata: dict[str, Any] = {}

        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("'"):
                continue

            cls._extract_entities_and_relations(line, diag_type, entities, relationships, metadata)

        return PlantUMLDiagram(
            name=name or f"Diagram_{len(entities)}",
            view=view,
            diagram_type=diag_type,
            raw_content=body,
            entities=sorted(list(set(entities))),
            relationships=relationships,
            metadata=metadata,
        )

    @staticmethod
    def _infer_diagram_type(name: str, body: str) -> str:
        name_lower = name.lower()
        if "usecase" in name_lower:
            return "usecase"
        if "class" in name_lower:
            return "class"
        if "object" in name_lower:
            return "object"
        if "state" in name_lower:
            return "state"
        if "activity" in name_lower:
            return "activity"
        if "sequence" in name_lower:
            return "sequence"
        if "collaboration" in name_lower:
            return "collaboration"
        if "package" in name_lower:
            return "package"
        if "component" in name_lower:
            return "component"
        if "deployment" in name_lower:
            return "deployment"
        if "container" in name_lower:
            return "container"

        if "actor" in body or "usecase" in body:
            return "usecase"
        if "class " in body:
            return "class"
        if "state " in body:
            return "state"
        if "-->" in body and ":" in body:
            return "state"
        if "->>" in body or "-> " in body:
            return "sequence"
        return "generic"

    @classmethod
    def _extract_entities_and_relations(
        cls,
        line: str,
        diag_type: str,
        entities: list[str],
        relationships: list[str],
        metadata: dict[str, Any],
    ) -> None:
        if diag_type == "class":
            cls._extract_class_info(line, entities, relationships, metadata)
            return

        if diag_type == "state":
            cls._extract_state_info(line, entities, relationships, metadata)
            return

        if diag_type == "usecase":
            cls._extract_usecase_info(line, entities, relationships, metadata)
            return

        if diag_type in ("sequence", "collaboration"):
            cls._extract_sequence_info(line, entities, relationships, metadata)
            return

        if diag_type in ("component", "container"):
            cls._extract_component_info(line, entities, relationships)
            return

        if diag_type == "deployment":
            cls._extract_deployment_info(line, entities, relationships)
            return

        if "--" in line or "->" in line:
            relationships.append(line)

    @staticmethod
    def _extract_class_info(
        line: str,
        entities: list[str],
        relationships: list[str],
        metadata: dict[str, Any],
    ) -> None:
        match = re.match(r"class\s+([A-Za-z0-9_]+)", line)
        if match:
            class_name = match.group(1)
            entities.append(class_name)
            if "classes" not in metadata:
                metadata["classes"] = {}
            if class_name not in metadata["classes"]:
                metadata["classes"][class_name] = {"methods": [], "fields": []}
            return

        if "--" in line or "*--" in line or "--*" in line or "<|--" in line:
            relationships.append(line)
            return

        method_match = re.search(r"([+-])\s*([a-zA-Z0-9_]+)\(.*\)\s*:\s*([a-zA-Z0-9_<>]+)", line)
        if method_match and entities:
            last_class = entities[-1]
            if "classes" in metadata and last_class in metadata["classes"]:
                metadata["classes"][last_class]["methods"].append(line)
            return

        field_match = re.search(r"([+-])\s*([a-zA-Z0-9_]+)\s*:\s*([a-zA-Z0-9_<>]+)", line)
        if field_match and entities:
            last_class = entities[-1]
            if "classes" in metadata and last_class in metadata["classes"]:
                metadata["classes"][last_class]["fields"].append(line)

    @staticmethod
    def _extract_state_info(
        line: str,
        entities: list[str],
        relationships: list[str],
        metadata: dict[str, Any],
    ) -> None:
        if line.startswith("state "):
            state_name = line.split()[1]
            entities.append(state_name)
            return

        if "-->" in line:
            relationships.append(line)
            parts = line.split("-->")
            src = parts[0].strip()
            dest_parts = parts[1].split(":")
            dst = dest_parts[0].strip()
            if src not in ("[*]", ""):
                entities.append(src)
            if dst not in ("[*]", ""):
                entities.append(dst)

            if "transitions" not in metadata:
                metadata["transitions"] = []
            trigger = dest_parts[1].strip() if len(dest_parts) > 1 else ""
            metadata["transitions"].append({"from": src, "to": dst, "event": trigger})

    @staticmethod
    def _extract_usecase_info(
        line: str,
        entities: list[str],
        relationships: list[str],
        metadata: dict[str, Any],
    ) -> None:
        actor_match = re.search(r"actor\s+([A-Za-z0-9_]+)", line)
        if actor_match:
            entities.append(actor_match.group(1))
            if "actors" not in metadata:
                metadata["actors"] = []
            metadata["actors"].append(actor_match.group(1))
            return

        usecase_match = re.search(r'usecase\s+"([^"]+)"\s+as\s+\(?([A-Za-z0-9_]+)\)?', line)
        if usecase_match:
            label = usecase_match.group(1)
            alias = usecase_match.group(2)
            entities.append(alias)
            if "usecases" not in metadata:
                metadata["usecases"] = []
            metadata["usecases"].append({"alias": alias, "label": label})
            return

        if "--" in line:
            relationships.append(line)

    @staticmethod
    def _extract_sequence_info(
        line: str,
        entities: list[str],
        relationships: list[str],
        metadata: dict[str, Any],
    ) -> None:
        if line.startswith("participant "):
            pname = line.split()[1]
            entities.append(pname)
            return

        seq_match = re.search(r"([A-Za-z0-9_]+)\s*(?:->>|->)\s*([A-Za-z0-9_]+)\s*:\s*(.*)", line)
        if seq_match:
            src = seq_match.group(1)
            dst = seq_match.group(2)
            call = seq_match.group(3)
            entities.extend([src, dst])
            relationships.append(line)
            if "messages" not in metadata:
                metadata["messages"] = []
            metadata["messages"].append({"from": src, "to": dst, "call": call})

    @staticmethod
    def _extract_component_info(
        line: str,
        entities: list[str],
        relationships: list[str],
    ) -> None:
        if line.startswith("artifact "):
            entities.append(line.split()[1])
            return
        if "--" in line:
            relationships.append(line)

    @staticmethod
    def _extract_deployment_info(
        line: str,
        entities: list[str],
        relationships: list[str],
    ) -> None:
        if line.startswith("node "):
            entities.append(line.split()[1])
            return
        if "--" in line:
            relationships.append(line)


class ArchitectureDocParser:
    @classmethod
    def parse_document(cls, content: str) -> dict[str, Any]:
        sections: dict[str, str] = {}
        section_matches = list(re.finditer(r"(^#\s+[A-L]\.\s+[^\n]+)", content, re.MULTILINE))

        for idx, match in enumerate(section_matches):
            header = match.group(1).strip()
            start = match.end()
            end = section_matches[idx + 1].start() if idx + 1 < len(section_matches) else len(content)
            body = content[start:end].strip()
            section_key = header.split(".")[0].replace("#", "").strip()
            sections[section_key] = body

        summary = cls._parse_section_a(sections.get("A", ""))
        traceability = cls._parse_section_b(sections.get("B", ""))
        components = cls._parse_section_d(sections.get("D", ""), sections.get("C", ""))
        deliverables = cls._parse_section_l(sections.get("L", ""))

        return {
            "executive_summary": summary,
            "traceability_matrix": traceability,
            "components": components,
            "operations": cls._parse_operations(sections.get("E", "")),
            "security": cls._parse_security(sections.get("F", "")),
            "observability": cls._parse_observability(sections.get("G", "")),
            "testing_strategy": cls._parse_testing(sections.get("H", "")),
            "deliverables": deliverables,
            "raw_sections": sections,
        }

    @staticmethod
    def _parse_section_a(text: str) -> dict[str, Any]:
        style_match = re.search(r"Chosen architectural style:\s*([^\n]+)", text)
        topo_match = re.search(r"Deployment topology:\s*([^\n]+)", text)

        tables = text.split("\n\n")
        risks: list[dict[str, str]] = []
        qa_coverage: list[dict[str, str]] = []

        for block in tables:
            if "| Risk | Mitigation |" in block:
                risks = MarkdownTableParser.parse_table(block)
            elif "| ASR/NFR ID | Test Type |" in block:
                qa_coverage = MarkdownTableParser.parse_table(block)

        return {
            "architectural_style": style_match.group(1).strip() if style_match else "Microservices",
            "deployment_topology": topo_match.group(1).strip() if topo_match else "Cloud-based",
            "risks": risks,
            "qa_coverage": qa_coverage,
        }

    @staticmethod
    def _parse_section_b(text: str) -> list[dict[str, str]]:
        return MarkdownTableParser.parse_table(text)

    @classmethod
    def _parse_section_d(cls, text: str, overview_text: str) -> dict[str, Any]:
        components: dict[str, Any] = {}
        comp_blocks = re.split(r"(##\s+[A-Za-z0-9_]+)", text)

        for i in range(1, len(comp_blocks), 2):
            comp_name = comp_blocks[i].replace("##", "").strip()
            comp_body = comp_blocks[i + 1] if i + 1 < len(comp_blocks) else ""

            components[comp_name] = {
                "openapi": cls._extract_code_block(comp_body, "yml") or cls._extract_code_block(comp_body, "yaml"),
                "proto": cls._extract_code_block(comp_body, "proto"),
                "sql": cls._extract_code_block(comp_body, "sql"),
                "recommended_stack": cls._extract_bullet_list(comp_body, "Recommended default stack"),
                "tech_options": cls._extract_bullet_list(comp_body, "Technology options"),
            }

        return components

    @staticmethod
    def _parse_operations(text: str) -> dict[str, Any]:
        k8s_match = re.search(r"```ya?ml\n(apiVersion:[^`]+)```", text)
        return {
            "k8s_manifest": k8s_match.group(1).strip() if k8s_match else "",
            "raw_text": text,
        }

    @staticmethod
    def _parse_security(text: str) -> dict[str, Any]:
        return {"raw_text": text}

    @staticmethod
    def _parse_observability(text: str) -> dict[str, Any]:
        slo_match = re.search(r"SLO:\s*([^\n]+)", text)
        return {
            "slo": slo_match.group(1).strip() if slo_match else "99.99%",
            "raw_text": text,
        }

    @staticmethod
    def _parse_testing(text: str) -> dict[str, Any]:
        return {
            "matrix": MarkdownTableParser.parse_table(text),
            "raw_text": text,
        }

    @classmethod
    def _parse_section_l(cls, text: str) -> dict[str, str]:
        deliverables: dict[str, str] = {}
        code_blocks = list(re.finditer(r"```([a-zA-Z0-9_-]*)\n(.*?)```", text, re.DOTALL))

        for block in code_blocks:
            lang = block.group(1).strip().lower()
            snippet = block.group(2).strip()

            if "openapi:" in snippet:
                deliverables["openapi.yaml"] = snippet
            elif 'syntax = "proto3";' in snippet:
                deliverables["internal.proto"] = snippet
            elif "kind: Deployment" in snippet:
                deliverables["k8s/spacefractions-deployment.yaml"] = snippet
            elif "CREATE TABLE" in snippet:
                deliverables["sql/game_ddl.sql"] = snippet
            elif "Requirement ID,Short Text" in snippet:
                deliverables["traceability_matrix.csv"] = snippet
            elif lang == "markdown" and "architecture.md" in snippet:
                deliverables["manifest_list"] = snippet

        return deliverables

    @staticmethod
    def _extract_code_block(text: str, lang: str) -> str:
        pattern = rf"```{lang}\n(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_bullet_list(text: str, section_title: str) -> list[str]:
        pos = text.find(section_title)
        if pos == -1:
            return []
        sub = text[pos:]
        end_pos = sub.find("\n### ")
        if end_pos != -1:
            sub = sub[:end_pos]
        return [line.strip("* -").strip() for line in sub.splitlines() if line.strip().startswith(("*", "-"))]


class ArchitecturePreprocessor:
    def __init__(self, doc_path: Path | str, view_path: Path | str) -> None:
        self.doc_path = Path(doc_path)
        self.view_path = Path(view_path)

    def process(self) -> ArchitectureIR:
        if not self.doc_path.exists():
            raise FileNotFoundError(f"Documentation file not found: {self.doc_path}")
        if not self.view_path.exists():
            raise FileNotFoundError(f"Views file not found: {self.view_path}")

        doc_content = self.doc_path.read_text(encoding="utf-8")
        view_content = self.view_path.read_text(encoding="utf-8")

        parsed_doc = ArchitectureDocParser.parse_document(doc_content)
        parsed_diagrams = PlantUMLParser.parse_views(view_content)

        return ArchitectureIR(
            title="Space Fractions System Architecture",
            executive_summary=parsed_doc["executive_summary"],
            traceability_matrix=parsed_doc["traceability_matrix"],
            components=parsed_doc["components"],
            operations=parsed_doc["operations"],
            security=parsed_doc["security"],
            observability=parsed_doc["observability"],
            testing_strategy=parsed_doc["testing_strategy"],
            deliverables=parsed_doc["deliverables"],
            diagrams=parsed_diagrams,
            raw_sections=parsed_doc["raw_sections"],
        )

    def export_json(self, output_path: Path | str) -> Path:
        ir = self.process()
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(ir.to_json(), encoding="utf-8")
        return out_file


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Deterministic Architecture IR Preprocessor")
    parser.add_argument("doc", help="Path to Architecture_Documentation.md")
    parser.add_argument("view", help="Path to Architecture_View.md")
    parser.add_argument("-o", "--output", default="architecture_ir.json", help="Output JSON path")
    args = parser.parse_args()

    preprocessor = ArchitecturePreprocessor(args.doc, args.view)
    out = preprocessor.export_json(args.output)
    sys.stdout.write(f"[INFO] Exported Architecture IR to {out}\n")


if __name__ == "__main__":
    main()
