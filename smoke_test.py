"""Testes rápidos do assistente (não instalam nada no sistema)."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import instalador_c_gui as gui


def descriptions(steps):
    return [step.description for step in steps]


def test_build_steps() -> None:
    project = Path(".")
    ubuntu = gui.build_steps("Ubuntu/Debian", ["compiler", "debugger", "cmake", "code_runner"], project)
    names = descriptions(ubuntu)
    assert any("build-essential" in n and "gdb" in n and "cmake" in n for n in names), names
    assert any("formulahendry.code-runner" in n for n in names)
    assert names[-1] == "Criando a configuração do Code Runner"
    # Uma única chamada elevada para o apt (só pede senha uma vez).
    assert sum(1 for s in ubuntu if s.args and "apt-get" in " ".join(s.args)) == 1

    fedora = gui.build_steps("Fedora", ["compiler"], project)
    assert all("groupinstall" not in " ".join(s.args or []) for s in fedora)

    windows = gui.build_steps("Windows", ["compiler", "debugger", "code_runner", "vscode"], project)
    names = descriptions(windows)
    assert "Instalando o MSYS2" in names
    assert "Adicionando o GCC ao PATH do usuário" in names
    winget_steps = [s for s in windows if s.args and s.args[0] == "winget"]
    assert winget_steps and all(-1978335189 in s.ok_codes for s in winget_steps)

    only_runner = gui.build_steps("Ubuntu/Debian", ["code_runner"], project)
    assert len(only_runner) == 2


def test_settings_merge() -> None:
    with tempfile.TemporaryDirectory() as folder:
        project = Path(folder)
        (project / ".vscode").mkdir()
        (project / ".vscode" / "settings.json").write_text('{"editor.fontSize": 16}', encoding="utf-8")
        path = gui.write_code_runner_settings(project, "Ubuntu/Debian")
        settings = json.loads(path.read_text(encoding="utf-8"))
        assert settings["editor.fontSize"] == 16  # preserva o que já existia
        assert settings["C_Cpp.default.cStandard"] == "c17"

        # settings.json com comentários não é sobrescrito.
        (project / ".vscode" / "settings.json").write_text('// comentário\n{}', encoding="utf-8")
        path = gui.write_code_runner_settings(project, "Windows")
        assert path.name == "settings.c-setup.generated.json"
        runner = json.loads(path.read_text(encoding="utf-8"))["code-runner.executorMap"]["c"]
        assert "&&" not in runner  # PowerShell 5.1 não aceita &&


def test_runner_linux_compiles_and_runs() -> None:
    if not shutil.which("gcc"):
        print("(gcc ausente: teste do Code Runner pulado)")
        return
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder) / "pasta com espaço"
        folder.mkdir()
        (folder / "main.c").write_text('#include <stdio.h>\nint main(void){puts("ola C");return 0;}\n')
        # Simula a substituição de variáveis que o Code Runner faz ($dir vem entre aspas).
        command = (gui.RUNNER_LINUX
                   .replace("$dir", f'"{folder}/"')
                   .replace("$fileNameWithoutExt", "main")
                   .replace("$fileName", "main.c"))
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "ola C", result.stdout


def test_run_steps() -> None:
    logs: list[str] = []
    stages: list[tuple] = []
    steps = [
        gui.Step("ok", ["true"]),
        gui.Step("pulado", ["false"], skip_if=lambda: "já existe"),
        gui.Step("opcional", ["false"], optional=True),
        gui.Step("aviso", action=lambda: gui._raise_warning("teste")),
    ]
    warnings = gui.run_steps(steps, logs.append, lambda *a: stages.append(a))
    assert warnings == ["aviso: teste"], warnings
    assert len([s for s in stages if s[2]]) == 4
    try:
        gui.run_steps([gui.Step("falha", ["false"])], logs.append, lambda *a: None)
    except RuntimeError as error:
        assert "falha" in str(error)
    else:
        raise AssertionError("deveria ter falhado")


def main() -> None:
    test_build_steps()
    test_settings_merge()
    if os.name != "nt":
        test_runner_linux_compiles_and_runs()
        test_run_steps()
    print("Smoke test concluído com sucesso.")


if __name__ == "__main__":
    main()
