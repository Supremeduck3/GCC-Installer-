import json
import tempfile
from pathlib import Path

from instalador_c_gui import InstallerApp


def main() -> None:
    app = InstallerApp.__new__(InstallerApp)
    with tempfile.TemporaryDirectory() as folder:
        project = Path(folder)
        commands = app.build_commands("Ubuntu/Debian", ["code_runner"], project)
        assert any("extensão formulahendry.code-runner" in description for description, _ in commands)
        settings_path = app.write_code_runner_settings(project, "Ubuntu/Debian")
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        assert settings["code-runner.runInTerminal"] is True
        assert "gcc" in settings["code-runner.executorMap"]["c"]
        assert settings["C_Cpp.default.cStandard"] == "c17"

    windows_commands = app.build_commands("Windows", ["compiler", "debugger", "code_runner"], Path("."))
    assert any("MSYS2" in description for description, _ in windows_commands)
    print("Smoke test concluído com sucesso.")


if __name__ == "__main__":
    main()
