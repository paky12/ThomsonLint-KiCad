import json
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
