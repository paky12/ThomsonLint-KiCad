"""Wrapper around kicad-cli subprocess calls."""
import shutil
import subprocess


class KiCadCLIError(Exception):
    pass


class KiCadCLI:
    def __init__(self, kicad_cli_path: str = "kicad-cli"):
        self._cli = kicad_cli_path

    def is_available(self) -> bool:
        return shutil.which(self._cli) is not None

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        result = subprocess.run([self._cli] + args, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise KiCadCLIError(f"kicad-cli failed (exit {result.returncode}): {result.stderr}")
        return result

    def export_netlist(self, sch_path: str, output_path: str) -> str:
        self._run(["sch", "export", "netlist", "-o", output_path, sch_path])
        return output_path

    def export_bom(self, sch_path: str, output_path: str) -> str:
        self._run(["sch", "export", "bom", "-o", output_path, "--fields", "*", sch_path])
        return output_path

    def export_positions(self, pcb_path: str, output_path: str) -> str:
        self._run(["pcb", "export", "pos", "-o", output_path, "--format", "csv", "--units", "mm", pcb_path])
        return output_path

    def export_drill(self, pcb_path: str, output_dir: str) -> str:
        self._run(["pcb", "export", "drill", "-o", output_dir, "--units", "mm", pcb_path])
        return output_dir

    def run_drc(self, pcb_path: str, output_path: str) -> str:
        self._run(["pcb", "drc", "-o", output_path, "--format", "json", pcb_path])
        return output_path
