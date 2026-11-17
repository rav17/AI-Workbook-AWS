from __future__ import annotations

import json
from pathlib import Path

from speckit_flow.cli import main


def _diagram(feature_dir: Path, content: str) -> Path:
    directory = feature_dir / "architecture" / "diagrams"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "context.drawio"
    path.write_text(content, encoding="utf-8")
    return path


def test_diagrams_validate_cli(capsys, tmp_path: Path) -> None:
    feature_dir = tmp_path / "specs" / "feature"
    path = _diagram(
        feature_dir,
        """<mxfile><diagram name="Context"><mxGraphModel><root>
        <mxCell id="0"/><mxCell id="1" parent="0"/>
        <mxCell id="system" vertex="1" parent="1"/>
        <mxCell id="actor" vertex="1" parent="1"/>
        <mxCell id="flow" edge="1" parent="1" source="actor" target="system"/>
        </root></mxGraphModel></diagram></mxfile>""",
    )

    assert main(
        ["diagrams", "validate", "--feature-dir", str(feature_dir), "--json"]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {"valid": ["architecture/diagrams/context.drawio"], "count": 1}
    assert path.is_file()


def test_diagrams_validate_rejects_malformed_xml(capsys, tmp_path: Path) -> None:
    feature_dir = tmp_path / "specs" / "feature"
    _diagram(feature_dir, "<mxfile>")

    assert main(["diagrams", "validate", "--feature-dir", str(feature_dir)]) == 1
    assert "invalid draw.io XML" in capsys.readouterr().err


def test_diagrams_validate_rejects_missing_graph_reference(capsys, tmp_path: Path) -> None:
    feature_dir = tmp_path / "specs" / "feature"
    _diagram(
        feature_dir,
        """<mxfile><diagram name="Context"><mxGraphModel><root>
        <mxCell id="0"/><mxCell id="1" parent="0"/>
        <mxCell id="flow" edge="1" parent="1" source="missing" target="1"/>
        </root></mxGraphModel></diagram></mxfile>""",
    )

    assert main(["diagrams", "validate", "--feature-dir", str(feature_dir)]) == 1
    assert "missing source reference" in capsys.readouterr().err


def test_diagrams_validate_requires_diagram_directory(capsys, tmp_path: Path) -> None:
    feature_dir = tmp_path / "specs" / "feature"
    feature_dir.mkdir(parents=True)

    assert main(["diagrams", "validate", "--feature-dir", str(feature_dir)]) == 1
    assert "diagram directory not found" in capsys.readouterr().err
