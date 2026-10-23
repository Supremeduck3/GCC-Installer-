#!/usr/bin/env python3
"""Assistente gráfico para instalar C/GCC e configurar o VS Code.

O aplicativo não executa nada automaticamente ao abrir. O usuário escolhe o
sistema-alvo, os componentes e o diretório do projeto antes de iniciar.
"""

from __future__ import annotations

import json
import os
import platform
import queue
import shlex
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Callable

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText
except ModuleNotFoundError as _tk_error:  # pragma: no cover - depende do sistema
    raise SystemExit(
        "O Tkinter não está instalado.\n"
        "Ubuntu/Debian: sudo apt-get install -y python3-tk\n"
        "Fedora: sudo dnf install -y python3-tkinter\n"
        "Windows: reinstale o Python marcando a opção 'tcl/tk and IDLE'."
    ) from _tk_error


APP_TITLE = "C Setup Assistant"

MSYS_ROOT = PureWindowsPath(r"C:\msys64")
MSYS_BASH = Path(MSYS_ROOT / "usr" / "bin" / "bash.exe")
MSYS_GCC_BIN = PureWindowsPath(MSYS_ROOT / "ucrt64" / "bin")
MSYS_GCC = PureWindowsPath(MSYS_GCC_BIN / "gcc.exe")

# Códigos que o winget devolve quando o pacote já está instalado/atualizado.
# No Windows o Python pode receber o valor com ou sem sinal.
WINGET_ALREADY_OK = {
    0,
    0x8A15002B, 0x8A15002B - 2**32,  # UPDATE_NOT_APPLICABLE
    0x8A150061, 0x8A150061 - 2**32,  # PACKAGE_ALREADY_INSTALLED
}

EXTENSIONS = {
    "cpp": "ms-vscode.cpptools",
    "cpp_pack": "ms-vscode.cpptools-extension-pack",
    "cmake_tools": "ms-vscode.cmake-tools",
    "code_runner": "formulahendry.code-runner",
    "error_lens": "usernamehw.errorlens",
}

COMPONENTS = [
    ("compiler", "Compilador GCC", "Instala o GCC, o Make e as ferramentas básicas de compilação."),
    ("debugger", "Depurador GDB", "Instala o GDB para depurar programas C."),
    ("vscode", "Visual Studio Code", "Instala o VS Code quando ele ainda não estiver disponível."),
    ("extensions", "Extensões principais", "Instala C/C++, o pacote C/C++, CMake Tools e Error Lens."),
    ("code_runner", "Code Runner", "Instala o Code Runner e configura a execução de arquivos .c."),
    ("cmake", "CMake", "Instala o CMake para projetos que usam configuração de build."),
]

# Comandos do Code Runner. O $dir já vem entre aspas pelo próprio Code Runner.
# Linux: bash/zsh. Windows: PowerShell (terminal padrão do VS Code), que não
# aceita "&&" na versão 5.1 e precisa de "&" para executar um caminho entre aspas.
RUNNER_LINUX = 'cd $dir && gcc "$fileName" -Wall -Wextra -std=c17 -o "$fileNameWithoutExt" && ./"$fileNameWithoutExt"'
RUNNER_WINDOWS = (
    "cd $dir; & '" + str(MSYS_GCC) + "' \"$fileName\" -Wall -Wextra -std=c17 "
    "-o \"$fileNameWithoutExt.exe\"; if ($?) { & \".\\$fileNameWithoutExt.exe\" }"
)


@dataclass
class Step:
    """Uma etapa da instalação."""

    description: str
    args: list[str] | None = None
    action: Callable[[], None] | None = None
    ok_codes: set[int] = field(default_factory=lambda: {0})
    skip_if: Callable[[], str | None] | None = None
    needs_code: bool = False
    optional: bool = False


def detect_os() -> str:
    current = platform.system().lower()
    if current == "windows":
        return "Windows"
    if current == "linux":
        info = ""
        try:
            info = Path("/etc/os-release").read_text(encoding="utf-8").lower()
        except OSError:
            pass
        if any(name in info for name in ("fedora", "rhel", "centos")) or shutil.which("dnf"):
            if not shutil.which("apt-get"):
                return "Fedora"
        return "Ubuntu/Debian"
    return "Windows"


def find_code() -> str | None:
    """Procura o comando do VS Code no momento da execução (pode ter acabado de ser instalado)."""
    candidates: list[str | None] = [shutil.which("code")]
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        candidates += [
            os.path.join(local, "Programs", "Microsoft VS Code", "bin", "code.cmd"),
            os.path.join(program_files, "Microsoft VS Code", "bin", "code.cmd"),
        ]
    else:
        candidates += ["/snap/bin/code", "/usr/bin/code", "/usr/share/code/bin/code"]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def elevated_linux(script: str) -> list[str]:
    """Executa um script shell como administrador sem depender de terminal."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ["sh", "-c", script]
    if shutil.which("pkexec") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return ["pkexec", "sh", "-c", script]
    # -n: não pergunta senha (não há terminal); falha com mensagem clara.
    return ["sudo", "-n", "sh", "-c", script]


def build_steps(target_os: str, selected: list[str], project_path: Path) -> list[Step]:
    steps: list[Step] = []
    extensions: list[str] = []

    if "extensions" in selected:
        extensions += [EXTENSIONS["cpp"], EXTENSIONS["cpp_pack"], EXTENSIONS["cmake_tools"], EXTENSIONS["error_lens"]]
    if "code_runner" in selected:
        extensions.append(EXTENSIONS["code_runner"])

    if target_os == "Windows":
        winget = ["winget", "install", "--exact", "--source", "winget",
                  "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity", "--id"]
        if "vscode" in selected:
            steps.append(Step(
                "Instalando o Visual Studio Code",
                winget + ["Microsoft.VisualStudioCode"],
                ok_codes=WINGET_ALREADY_OK,
                skip_if=lambda: "o VS Code já está instalado" if find_code() else None,
            ))
        if "compiler" in selected or "debugger" in selected:
            packages: list[str] = []
            if "compiler" in selected:
                packages += ["mingw-w64-ucrt-x86_64-gcc", "mingw-w64-ucrt-x86_64-make"]
            if "debugger" in selected:
                packages.append("mingw-w64-ucrt-x86_64-gdb")
            steps.append(Step(
                "Instalando o MSYS2",
                winget + ["MSYS2.MSYS2"],
                ok_codes=WINGET_ALREADY_OK,
                skip_if=lambda: "o MSYS2 já está instalado" if MSYS_BASH.exists() else None,
            ))
            # Numa instalação nova, a 1ª atualização troca o núcleo e encerra com erro;
            # a 2ª conclui a atualização.
            steps.append(Step("Atualizando o núcleo do MSYS2", [str(MSYS_BASH), "-lc", "pacman -Syu --noconfirm"], optional=True))
            steps.append(Step("Atualizando os pacotes do MSYS2", [str(MSYS_BASH), "-lc", "pacman -Syu --noconfirm"]))
            steps.append(Step(
                "Instalando GCC/GDB/Make",
                [str(MSYS_BASH), "-lc", "pacman -S --needed --noconfirm " + " ".join(packages)],
            ))
            steps.append(Step("Adicionando o GCC ao PATH do usuário", action=add_gcc_to_windows_path))
        if "cmake" in selected:
            steps.append(Step(
                "Instalando CMake",
                winget + ["Kitware.CMake"],
                ok_codes=WINGET_ALREADY_OK,
                skip_if=lambda: "o CMake já está instalado" if shutil.which("cmake") else None,
            ))

    elif target_os == "Ubuntu/Debian":
        packages = []
        if "compiler" in selected:
            packages += ["build-essential", "gcc", "make"]
        if "debugger" in selected:
            packages.append("gdb")
        if "cmake" in selected:
            packages.append("cmake")
        if packages:
            script = ("apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y "
                      + " ".join(packages))
            steps.append(Step("Instalando " + ", ".join(packages) + " (apt)", elevated_linux(script)))
        if "vscode" in selected:
            if shutil.which("snap"):
                steps.append(Step(
                    "Instalando o Visual Studio Code (snap)",
                    elevated_linux("snap install code --classic"),
                    skip_if=lambda: "o VS Code já está instalado" if find_code() else None,
                ))
            else:
                steps.append(Step("VS Code", action=lambda: _raise_warning(
                    "snap não encontrado. Instale o VS Code pelo .deb em https://code.visualstudio.com/")))

    elif target_os == "Fedora":
        packages = []
        if "compiler" in selected:
            packages += ["gcc", "gcc-c++", "make"]
        if "debugger" in selected:
            packages.append("gdb")
        if "cmake" in selected:
            packages.append("cmake")
        if packages:
            steps.append(Step("Instalando " + ", ".join(packages) + " (dnf)",
                              elevated_linux("dnf install -y " + " ".join(packages))))
        if "vscode" in selected:
            steps.append(Step("VS Code", action=lambda: _raise_warning(
                "instale o VS Code pelo repositório oficial: https://code.visualstudio.com/docs/setup/linux")))

    for extension in dict.fromkeys(extensions):
        steps.append(Step(f"Instalando extensão {extension}", ["{code}", "--install-extension", extension, "--force"],
                          needs_code=True))

    if "code_runner" in selected:
        steps.append(Step("Criando a configuração do Code Runner",
                          action=lambda: write_code_runner_settings(project_path, target_os)))

    return steps


class StepWarning(Exception):
    """Problema que não impede as demais etapas."""


def _raise_warning(message: str) -> None:
    raise StepWarning(message)


def add_gcc_to_windows_path() -> None:
    if not Path(MSYS_GCC).exists():
        raise RuntimeError(f"O GCC não foi encontrado em {MSYS_GCC}.")
    import winreg  # type: ignore[import-not-found]

    entry = str(MSYS_GCC_BIN)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            current, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current, kind = "", winreg.REG_EXPAND_SZ
        parts = [p for p in current.split(";") if p.strip()]
        if not any(p.rstrip("\\").lower() == entry.lower() for p in parts):
            parts.append(entry)
            winreg.SetValueEx(key, "Path", 0, kind, ";".join(parts))
    # Avisa o Windows que o ambiente mudou (novos terminais já enxergam o PATH).
    try:
        import ctypes

        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 2, 5000, None)
    except Exception:  # noqa: BLE001
        pass
    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + entry


def write_code_runner_settings(project_path: Path, target_os: str) -> Path:
    vscode_dir = project_path / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    settings_path = vscode_dir / "settings.json"
    settings: dict = {}
    if settings_path.exists():
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8-sig"))
            settings = loaded if isinstance(loaded, dict) else {}
            if not isinstance(loaded, dict):
                raise ValueError
        except (ValueError, OSError):
            # settings.json com comentários (JSONC) ou inválido: não sobrescreve.
            settings_path = vscode_dir / "settings.c-setup.generated.json"
            settings = {}

    if target_os == "Windows":
        compiler, mode, command = str(MSYS_GCC), "windows-gcc-x64", RUNNER_WINDOWS
    else:
        compiler, mode, command = shutil.which("gcc") or "/usr/bin/gcc", "linux-gcc-x64", RUNNER_LINUX

    settings.update({
        "C_Cpp.default.compilerPath": compiler,
        "C_Cpp.default.cStandard": "c17",
        "C_Cpp.default.intelliSenseMode": mode,
        "code-runner.runInTerminal": True,
        "code-runner.saveFileBeforeRun": True,
        "code-runner.clearPreviousOutput": True,
    })
    executor_map = settings.get("code-runner.executorMap")
    executor_map = executor_map if isinstance(executor_map, dict) else {}
    executor_map["c"] = command
    settings["code-runner.executorMap"] = executor_map
    if target_os == "Windows":
        # O comando acima é para PowerShell; garante que o terminal do projeto seja ele.
        settings.setdefault("terminal.integrated.defaultProfile.windows", "PowerShell")
    associations = settings.get("files.associations")
    associations = associations if isinstance(associations, dict) else {}
    associations.update({"*.c": "c", "*.h": "c"})
    settings["files.associations"] = associations
    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return settings_path


def format_command(args: list[str]) -> str:
    return subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)


def run_streaming(args: list[str], log: Callable[[str], None]) -> int:
    """Executa um comando mostrando a saída linha a linha."""
    if os.name == "nt" and args[0].lower().endswith((".cmd", ".bat")):
        args = ["cmd", "/c", *args]
    env = dict(os.environ)
    if os.name == "nt":
        env.setdefault("MSYSTEM", "UCRT64")
        env["CHERE_INVOKING"] = "1"
    process = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip()
        # Ignora barras de progresso do winget/pacman que só poluem o registro.
        if line and not set(line.strip()) <= set("-\\|/ █▒░"):
            log(line)
    return process.wait()


def run_steps(steps: list[Step], log: Callable[[str], None], on_stage: Callable[[int, str, bool], None]) -> list[str]:
    """Executa as etapas. Devolve a lista de avisos; lança RuntimeError em falha."""
    warnings: list[str] = []
    for index, step in enumerate(steps, start=1):
        on_stage(index, step.description, False)
        reason = step.skip_if() if step.skip_if else None
        if reason:
            log(f"Pulando: {step.description} ({reason}).")
            on_stage(index, step.description, True)
            continue
        try:
            if step.action:
                step.action()
            elif step.args:
                args = list(step.args)
                if step.needs_code:
                    code = find_code()
                    if not code:
                        raise StepWarning("comando 'code' do VS Code não encontrado; instale o VS Code e rode de novo")
                    args = [code if a == "{code}" else a for a in args]
                log(f"$ {format_command(args)}")
                try:
                    returncode = run_streaming(args, log)
                except FileNotFoundError as error:
                    raise RuntimeError(f"Comando não encontrado: {args[0]}. Verifique se ele está instalado.") from error
                if returncode not in step.ok_codes:
                    if step.optional:
                        log(f"(código {returncode} ignorado; a próxima etapa completa a operação)")
                    elif args[0] == "sudo":
                        raise RuntimeError(
                            "O sudo precisa de senha e não há terminal. Rode 'sudo -v' num terminal e "
                            "abra o assistente de novo, ou instale o pacote 'policykit-1'.")
                    else:
                        raise RuntimeError(f"A etapa '{step.description}' terminou com código {returncode}.")
            log(f"Concluído: {step.description}")
        except StepWarning as warning:
            message = f"{step.description}: {warning}"
            warnings.append(message)
            log("AVISO: " + message)
        on_stage(index, step.description, True)
    return warnings


class InstallerApp(tk.Tk):
    """Janela principal e navegação do aplicativo."""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1000x820")
        self.minsize(860, 760)
        self.configure(bg="#f4f7fb")

        self.command_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.install_thread: threading.Thread | None = None
        self.is_running = False
        self.run_button: ttk.Button | None = None
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="Pronto para iniciar")
        self.step_var = tk.StringVar(value="0 de 0 etapas")
        self.total_steps = 0
        self.os_var = tk.StringVar(value=detect_os())
        self.project_var = tk.StringVar(value=str(Path.cwd()))
        self.all_var = tk.BooleanVar(value=True)
        self.component_vars = {key: tk.BooleanVar(value=True) for key, _, _ in COMPONENTS}

        self._configure_style()
        self._build_shell()
        self.show_home()
        self.after(100, self._process_queue)

    # Mantidos como métodos para compatibilidade com o smoke test.
    detect_os = staticmethod(detect_os)

    def build_commands(self, target_os: str, selected: list[str], project_path: Path) -> list[Step]:
        return build_steps(target_os, selected, project_path)

    def write_code_runner_settings(self, project_path: Path, target_os: str) -> Path:
        return write_code_runner_settings(project_path, target_os)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("App.TFrame", background="#f4f7fb")
        style.configure("Header.TFrame", background="#172b4d")
        style.configure("Header.TLabel", background="#172b4d", foreground="white")
        style.configure("Title.TLabel", background="#f4f7fb", foreground="#172b4d", font=("Segoe UI", 22, "bold"))
        style.configure("Subtitle.TLabel", background="#f4f7fb", foreground="#526581", font=("Segoe UI", 10))
        style.configure("Section.TLabel", background="#f4f7fb", foreground="#172b4d", font=("Segoe UI", 12, "bold"))
        style.configure("Card.TFrame", background="white", relief="solid", borderwidth=1)
        style.configure("Card.TCheckbutton", background="white", foreground="#172b4d", font=("Segoe UI", 10))
        style.configure("CardDescription.TLabel", background="white", foreground="#60708a", font=("Segoe UI", 9))
        style.configure("App.TCheckbutton", background="#f4f7fb")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 9))
        style.configure("Nav.TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("App.Horizontal.TProgressbar", troughcolor="#e3e9f2", background="#2f6fed", bordercolor="#e3e9f2", thickness=14)

    def _build_shell(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame", padding=(24, 14))
        header.pack(fill="x")
        ttk.Label(header, text="C Setup Assistant", style="Header.TLabel", font=("Segoe UI", 17, "bold")).pack(side="left")
        ttk.Label(header, text="GCC + VS Code", style="Header.TLabel", font=("Segoe UI", 10)).pack(side="left", padx=(15, 0))

        nav = ttk.Frame(header, style="Header.TFrame")
        nav.pack(side="right")
        ttk.Button(nav, text="Home", style="Nav.TButton", command=self.show_home).pack(side="left", padx=4)
        ttk.Button(nav, text="Como usar", style="Nav.TButton", command=self.show_help).pack(side="left", padx=4)

        # A barra de progresso e o registro ficam embaixo e são empacotados antes
        # da página, para nunca serem empurrados para fora da janela.
        log_frame = ttk.Frame(self, style="App.TFrame", padding=(30, 0, 30, 22))
        log_frame.pack(side="bottom", fill="x")
        ttk.Label(log_frame, text="Registro da operação", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        self.log = ScrolledText(log_frame, height=6, wrap="word", state="disabled", font=("Consolas", 9),
                                background="#101827", foreground="#d8e2f0", insertbackground="white")
        self.log.pack(fill="x")

        progress_frame = ttk.Frame(self, style="App.TFrame", padding=(30, 0, 30, 10))
        progress_frame.pack(side="bottom", fill="x")
        progress_top = ttk.Frame(progress_frame, style="App.TFrame")
        progress_top.pack(fill="x", pady=(0, 5))
        ttk.Label(progress_top, textvariable=self.status_var, style="Section.TLabel").pack(side="left")
        ttk.Label(progress_top, textvariable=self.step_var, style="Subtitle.TLabel").pack(side="right")
        ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate", maximum=100,
                        variable=self.progress_var, style="App.Horizontal.TProgressbar").pack(fill="x")

        self.page_container = ttk.Frame(self, style="App.TFrame", padding=(30, 18, 30, 12))
        self.page_container.pack(fill="both", expand=True)

    def _clear_page(self) -> None:
        self.run_button = None
        for child in self.page_container.winfo_children():
            child.destroy()

    def show_home(self) -> None:
        self._clear_page()

        page_title = ttk.Label(self.page_container, text="Configure seu ambiente de C", style="Title.TLabel")
        page_title.pack(anchor="w")
        ttk.Label(self.page_container, text="Escolha o sistema-alvo, o diretório do projeto e os componentes que deseja instalar.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(4, 14))

        top = ttk.Frame(self.page_container, style="App.TFrame")
        top.pack(fill="x")
        self._make_os_selector(top)
        self._make_project_selector(top)

        ttk.Label(self.page_container, text="Componentes", style="Section.TLabel").pack(anchor="w", pady=(16, 6))
        selection_bar = ttk.Frame(self.page_container, style="App.TFrame")
        selection_bar.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(selection_bar, text="Selecionar tudo", variable=self.all_var, style="App.TCheckbutton",
                        command=self._toggle_all).pack(side="left")
        ttk.Label(selection_bar, text="Você pode instalar só o Code Runner, só o compilador ou qualquer combinação.",
                  style="Subtitle.TLabel").pack(side="left", padx=20)

        cards = ttk.Frame(self.page_container, style="App.TFrame")
        cards.pack(fill="x")
        for index, (key, title, description) in enumerate(COMPONENTS):
            card = ttk.Frame(cards, style="Card.TFrame", padding=(14, 8))
            card.grid(row=index // 2, column=index % 2, sticky="nsew",
                      padx=(0 if index % 2 == 0 else 8, 8 if index % 2 == 0 else 0), pady=4)
            cards.grid_columnconfigure(index % 2, weight=1)
            ttk.Checkbutton(card, text=title, variable=self.component_vars[key], style="Card.TCheckbutton",
                            command=self._update_all_state).pack(anchor="w")
            ttk.Label(card, text=description, style="CardDescription.TLabel", wraplength=400,
                      justify="left").pack(anchor="w", pady=(6, 0))

        bottom = ttk.Frame(self.page_container, style="App.TFrame")
        bottom.pack(side="bottom", fill="x", pady=(12, 0), before=page_title)
        self.run_button = ttk.Button(bottom, text="Instalar componentes selecionados", style="Primary.TButton",
                                     command=self.start_installation)
        self.run_button.pack(side="right")
        self._refresh_run_button()
        ttk.Button(bottom, text="Abrir instruções", command=self.show_help).pack(side="right", padx=(0, 10))

    def _make_os_selector(self, parent: ttk.Frame) -> None:
        box = ttk.Frame(parent, style="App.TFrame")
        box.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ttk.Label(box, text="Sistema operacional", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Combobox(box, textvariable=self.os_var, values=["Windows", "Ubuntu/Debian", "Fedora"],
                     state="readonly").pack(fill="x")

    def _make_project_selector(self, parent: ttk.Frame) -> None:
        box = ttk.Frame(parent, style="App.TFrame")
        box.pack(side="left", fill="x", expand=True)
        ttk.Label(box, text="Pasta do projeto", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        row = ttk.Frame(box, style="App.TFrame")
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.project_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Escolher...", command=self.choose_project).pack(side="left", padx=(8, 0))

    def show_help(self) -> None:
        self._clear_page()
        ttk.Label(self.page_container, text="Como usar", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.page_container, text="Siga estas etapas para configurar o ambiente com segurança.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(4, 12))

        help_text = (
            "1. Na Home, selecione o sistema operacional que será configurado.\n\n"
            "2. Escolha a pasta raiz do seu projeto. O arquivo .vscode/settings.json será criado nessa pasta quando o Code Runner for selecionado.\n\n"
            "3. Marque apenas o que precisa. Para um ambiente completo, use Selecionar tudo.\n\n"
            "4. Clique em Instalar componentes selecionados. Algumas etapas pedem autorização de administrador (UAC no Windows, senha no Linux).\n\n"
            "5. Depois da instalação, FECHE E ABRA o VS Code, abra um arquivo .c e pressione Ctrl+Alt+N para executar.\n\n"
            "Windows: o GCC é instalado pelo MSYS2 em C:\\msys64\\ucrt64\\bin. Ubuntu/Debian: pelo apt. Fedora: pelo dnf.\n\n"
            "Linux: se aparecer erro de senha do sudo, rode 'sudo -v' num terminal e abra o assistente pelo mesmo terminal.\n\n"
            "Se algo falhar, consulte o Registro da operação na parte inferior da janela, corrija o requisito indicado e execute novamente. "
            "Rodar de novo é seguro: o que já está instalado é pulado."
        )
        text = ScrolledText(self.page_container, wrap="word", font=("Segoe UI", 10), padx=16, pady=16,
                            background="white", foreground="#26364d", relief="solid", borderwidth=1)
        text.pack(fill="both", expand=True)
        text.insert("1.0", help_text)
        text.configure(state="disabled")

        ttk.Button(self.page_container, text="Voltar para Home", style="Primary.TButton",
                   command=self.show_home).pack(anchor="e", pady=(14, 0))

    def choose_project(self) -> None:
        selected = filedialog.askdirectory(title="Escolha a pasta raiz do projeto")
        if selected:
            self.project_var.set(selected)

    def _toggle_all(self) -> None:
        selected = self.all_var.get()
        for variable in self.component_vars.values():
            variable.set(selected)

    def _update_all_state(self) -> None:
        self.all_var.set(all(variable.get() for variable in self.component_vars.values()))

    def _refresh_run_button(self) -> None:
        if self.run_button is not None and self.run_button.winfo_exists():
            if self.is_running:
                self.run_button.configure(state="disabled", text="Instalando...")
            else:
                self.run_button.configure(state="normal", text="Instalar componentes selecionados")

    def selected_components(self) -> list[str]:
        return [key for key, _, _ in COMPONENTS if self.component_vars[key].get()]

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start_installation(self) -> None:
        if self.is_running:
            return
        selected = self.selected_components()
        if not selected:
            messagebox.showwarning("Nenhum componente", "Selecione pelo menos um componente para continuar.")
            return

        target_os = self.os_var.get()
        current = detect_os()
        if (target_os == "Windows") != (os.name == "nt"):
            messagebox.showerror(
                "Sistema diferente",
                f"Este computador é {current}, mas você escolheu {target_os}.\n\n"
                "Execute o assistente no próprio sistema que será configurado.")
            return
        if current != target_os and not messagebox.askyesno(
            "Distribuição diferente",
            f"A distribuição detectada é {current}, mas você escolheu {target_os}. Deseja continuar?",
        ):
            return

        project_path = Path(self.project_var.get()).expanduser()
        try:
            project_path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror("Pasta inválida", f"Não foi possível criar a pasta escolhida:\n{error}")
            return

        steps = build_steps(target_os, selected, project_path)
        self.is_running = True
        self._refresh_run_button()
        self.total_steps = len(steps)
        self.progress_var.set(0)
        self.status_var.set("Preparando instalação...")
        self.step_var.set(f"0 de {self.total_steps} etapas")
        self.append_log(f"Iniciando configuração para {target_os} em {project_path}")
        self.append_log("Componentes: " + ", ".join(title for key, title, _ in COMPONENTS if key in selected))
        self.install_thread = threading.Thread(target=self._installation_worker, args=(steps,), daemon=True)
        self.install_thread.start()

    def _installation_worker(self, steps: list[Step]) -> None:
        try:
            warnings = run_steps(
                steps,
                log=lambda text: self.command_queue.put(("log", text)),
                on_stage=lambda i, d, done: self.command_queue.put(("stage", (i, d, done))),
            )
            message = "Configuração concluída com sucesso."
            if warnings:
                message = "Configuração concluída com avisos:\n\n" + "\n".join("• " + w for w in warnings)
            self.command_queue.put(("done", message))
        except Exception as error:  # noqa: BLE001 - a mensagem é mostrada na interface
            self.command_queue.put(("error", str(error)))

    def _process_queue(self) -> None:
        try:
            while True:
                event, payload = self.command_queue.get_nowait()
                if event == "log":
                    self.append_log(str(payload))
                elif event == "stage":
                    step_index, description, completed = payload  # type: ignore[misc]
                    done_steps = step_index if completed else step_index - 1
                    self.progress_var.set(done_steps / self.total_steps * 100 if self.total_steps else 100)
                    if completed:
                        self.status_var.set(f"Concluído: {description}")
                        self.step_var.set(f"{step_index} de {self.total_steps} etapas")
                    else:
                        self.status_var.set(f"Executando: {description}")
                        self.step_var.set(f"Etapa {step_index} de {self.total_steps}")
                elif event in ("done", "error"):
                    self.is_running = False
                    self._refresh_run_button()
                    if event == "done":
                        self.progress_var.set(100)
                        self.status_var.set("Concluído")
                        self.step_var.set(f"{self.total_steps} de {self.total_steps} etapas")
                        self.append_log(str(payload))
                        messagebox.showinfo("Concluído", str(payload) + "\n\nReinicie o VS Code para aplicar tudo.")
                    else:
                        self.status_var.set("Falha na instalação")
                        self.step_var.set("Operação interrompida")
                        self.append_log("ERRO: " + str(payload))
                        messagebox.showerror("Falha na instalação", str(payload))
        except queue.Empty:
            pass
        finally:
            # Sempre reagenda, mesmo se algo acima falhar, para a janela não "congelar".
            self.after(100, self._process_queue)


def main() -> None:
    app = InstallerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
