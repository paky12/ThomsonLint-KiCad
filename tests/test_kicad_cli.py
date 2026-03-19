import pytest
from unittest.mock import patch, MagicMock
from kicad.kicad_cli import KiCadCLI, KiCadCLIError


def test_check_available_missing():
    with patch("shutil.which", return_value=None):
        cli = KiCadCLI()
        assert cli.is_available() is False


def test_check_available_found():
    with patch("shutil.which", return_value="/usr/bin/kicad-cli"):
        cli = KiCadCLI()
        assert cli.is_available() is True


def test_export_netlist_calls_correct_command():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        cli = KiCadCLI()
        cli.export_netlist("/path/to/project.kicad_sch", "/tmp/out.xml")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "kicad-cli" in args[0]
        assert "sch" in args
        assert "export" in args
        assert "netlist" in args


def test_export_bom_calls_correct_command():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        cli = KiCadCLI()
        cli.export_bom("/path/to/project.kicad_sch", "/tmp/out.csv")
        args = mock_run.call_args[0][0]
        assert "bom" in args


def test_export_positions_calls_correct_command():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        cli = KiCadCLI()
        cli.export_positions("/path/to/project.kicad_pcb", "/tmp/out.csv")
        args = mock_run.call_args[0][0]
        assert "pos" in args


def test_raises_on_failure():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "error: file not found"
    with patch("subprocess.run", return_value=mock_result):
        cli = KiCadCLI()
        with pytest.raises(KiCadCLIError):
            cli.export_netlist("/bad/path.kicad_sch", "/tmp/out.xml")


def test_export_netlist_returns_output_path():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result):
        cli = KiCadCLI()
        result = cli.export_netlist("/path/to/project.kicad_sch", "/tmp/out.xml")
        assert result == "/tmp/out.xml"


def test_export_drill_calls_correct_command():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        cli = KiCadCLI()
        cli.export_drill("/path/to/project.kicad_pcb", "/tmp/drill/")
        args = mock_run.call_args[0][0]
        assert "drill" in args


def test_run_drc_calls_correct_command():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        cli = KiCadCLI()
        cli.run_drc("/path/to/project.kicad_pcb", "/tmp/drc.json")
        args = mock_run.call_args[0][0]
        assert "drc" in args
        assert "json" in args
