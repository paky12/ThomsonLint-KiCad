import json
import os
import pytest
from kicad.mcp_server.server import get_review_context_impl, generate_report_impl


def test_get_review_context_all():
    result = get_review_context_impl(section="all")
    assert len(result) > 1000
    assert "ontology" in result.lower() or "ThomsonLint" in result


def test_get_review_context_ontology():
    result = get_review_context_impl(section="ontology")
    assert "rules" in result.lower()


def test_get_review_context_instructions():
    result = get_review_context_impl(section="instructions")
    assert len(result) > 100
    # Should contain review instructions content
    assert "review" in result.lower()


def test_get_review_context_docs():
    result = get_review_context_impl(section="docs")
    # docs directory has markdown files
    assert len(result) > 0


def test_get_review_context_unknown_section():
    with pytest.raises(ValueError):
        get_review_context_impl(section="nonexistent_section")


def test_generate_report_validates():
    bad_json = json.dumps({"bad": "data"})
    try:
        generate_report_impl(bad_json)
        assert False, "Should have raised"
    except Exception:
        pass


def test_generate_report_invalid_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        generate_report_impl("not-valid-json{{{")


def test_generate_report_valid_findings(tmp_path):
    findings = {
        "project_name": "test_project",
        "review_date": "2026-03-19",
        "issues": [
            {
                "rule_id": "PWR_DECPL_001",
                "severity": "Major",
                "domain": "Power",
                "summary": "Missing decoupling capacitor on U1 VDD pin.",
            }
        ],
    }
    # Should not raise (valid schema) and returns a path string
    result = generate_report_impl(json.dumps(findings))
    assert isinstance(result, str)
    assert result.endswith(".html")


def test_run_drc_impl(monkeypatch, tmp_path):
    """run_drc_impl returns parsed DRC JSON."""
    from kicad.mcp_server.server import run_drc_impl
    from kicad.kicad_cli import KiCadCLI

    pcb_file = tmp_path / "test.kicad_pcb"
    pcb_file.write_text("(kicad_pcb)")

    def mock_run_drc(self, pcb_path, output_path):
        import json as _json
        with open(output_path, "w") as f:
            _json.dump({"violations": [{"type": "clearance"}], "unconnected_items": []}, f)
        return output_path

    monkeypatch.setattr(KiCadCLI, "is_available", lambda self: True)
    monkeypatch.setattr(KiCadCLI, "run_drc", mock_run_drc)

    result = run_drc_impl(str(pcb_file))
    assert "violations" in result
    assert len(result["violations"]) == 1
    # Temp file should be cleaned up
    drc_tmp = str(tmp_path / f".thomsonlint_drc_{os.getpid()}.json")
    assert not os.path.exists(drc_tmp)


def test_run_drc_impl_no_kicad_cli(monkeypatch, tmp_path):
    """run_drc_impl raises when kicad-cli is not available."""
    from kicad.mcp_server.server import run_drc_impl
    from kicad.kicad_cli import KiCadCLI

    pcb_file = tmp_path / "test.kicad_pcb"
    pcb_file.write_text("(kicad_pcb)")

    monkeypatch.setattr(KiCadCLI, "is_available", lambda self: False)

    with pytest.raises(RuntimeError, match="kicad-cli not found"):
        run_drc_impl(str(pcb_file))
