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
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


APP_TITLE = "C Setup Assistant"
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
    ("code_runner", "Code Runner", "Instala o Code Runner e cria a configuração para executar arquivos .c."),
    ("cmake", "CMake", "Instala o CMake para projetos que usam configuração de build."),
]


class InstallerApp(tk.Tk):
    """Janela principal e navegação do aplicativo."""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x720")
        self.minsize(820, 600)
        self.configure(bg="#f4f7fb")

        self.command_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.install_thread: threading.Thread | None = None
        self.is_running = False
        self.current_page = "home"
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="Pronto para iniciar")
        self.step_var = tk.StringVar(value="0 de 0 etapas")
        self.total_steps = 0
        self.os_var = tk.StringVar(value=self.detect_os())
        self.project_var = tk.StringVar(value=str(Path.cwd()))
        self.all_var = tk.BooleanVar(value=True)
        self.component_vars = {key: tk.BooleanVar(value=True) for key, _, _ in COMPONENTS}

        self._configure_style()
        self._build_shell()
        self.show_home()
        self.after(100, self._process_queue)

    @staticmethod
    def detect_os() -> str:
        current = platform.system().lower()
        if current == "windows":
            return "Windows"
        if current == "linux":
            return "Ubuntu/Debian"
        return "Windows"

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
        style.configure("Card.TLabel", background="white", foreground="#172b4d", font=("Segoe UI", 10))
        style.configure("CardDescription.TLabel", background="white", foreground="#60708a", font=("Segoe UI", 9))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 9))
        style.configure("Nav.TButton", font=("Segoe UI", 10), padding=(12, 7))

    def _build_shell(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame", padding=(24, 14))
        header.pack(fill="x")
        ttk.Label(header, text="C Setup Assistant", style="Header.TLabel", font=("Segoe UI", 17, "bold")).pack(side="left")
        ttk.Label(header, text="GCC + VS Code", style="Header.TLabel", font=("Segoe UI", 10)).pack(side="left", padx=(15, 0))

        nav = ttk.Frame(header, style="Header.TFrame")
        nav.pack(side="right")
        self.home_button = ttk.Button(nav, text="Home", style="Nav.TButton", command=self.show_home)
        self.home_button.pack(side="left", padx=4)
        self.help_button = ttk.Button(nav, text="Como usar", style="Nav.TButton", command=self.show_help)
        self.help_button.pack(side="left", padx=4)

        self.page_container = ttk.Frame(self, style="App.TFrame", padding=(30, 24, 30, 12))
        self.page_container.pack(fill="both", expand=True)

        progress_frame = ttk.Frame(self, style="App.TFrame", padding=(30, 0, 30, 10))
        progress_frame.pack(fill="x")
        progress_top = ttk.Frame(progress_frame, style="App.TFrame")
        progress_top.pack(fill="x", pady=(0, 5))
        ttk.Label(progress_top, textvariable=self.status_var, style="Section.TLabel").pack(side="left")
        ttk.Label(progress_top, textvariable=self.step_var, style="Subtitle.TLabel").pack(side="right")
        self.progressbar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate", maximum=100, variable=self.progress_var)
        self.progressbar.pack(fill="x")

        log_frame = ttk.Frame(self, style="App.TFrame", padding=(30, 0, 30, 22))
        log_frame.pack(fill="x")
        ttk.Label(log_frame, text="Registro da operação", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        self.log = ScrolledText(log_frame, height=7, wrap="word", state="disabled", font=("Consolas", 9), background="#101827", foreground="#d8e2f0", insertbackground="white")
        self.log.pack(fill="x")

    def _clear_page(self) -> None:
        for child in self.page_container.winfo_children():
            child.destroy()

    def show_home(self) -> None:
        self.current_page = "home"
        self._clear_page()

        ttk.Label(self.page_container, text="Configure seu ambiente de C", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.page_container, text="Escolha o sistema-alvo, o diretório do projeto e os componentes que deseja instalar.", style="Subtitle.TLabel").pack(anchor="w", pady=(4, 20))

        top = ttk.Frame(self.page_container, style="App.TFrame")
        top.pack(fill="x")
        self._make_labeled_entry(top, "Sistema operacional", self.os_var, readonly=True, values=["Windows", "Ubuntu/Debian", "Fedora"])
        self._make_project_selector(top)

        ttk.Label(self.page_container, text="Componentes", style="Section.TLabel").pack(anchor="w", pady=(22, 8))
        selection_bar = ttk.Frame(self.page_container, style="App.TFrame")
        selection_bar.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(selection_bar, text="Selecionar tudo", variable=self.all_var, command=self._toggle_all).pack(side="left")
        ttk.Label(selection_bar, text="Você poderá executar somente o Code Runner, somente o compilador ou qualquer combinação.", style="Subtitle.TLabel").pack(side="left", padx=20)

        cards = ttk.Frame(self.page_container, style="App.TFrame")
        cards.pack(fill="both", expand=True)
        for index, (key, title, description) in enumerate(COMPONENTS):
            card = ttk.Frame(cards, style="Card.TFrame", padding=(14, 11))
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else 8, 8 if index % 2 == 0 else 0), pady=5)
            cards.grid_columnconfigure(index % 2, weight=1)
            cards.grid_rowconfigure(index // 2, weight=1)
            ttk.Checkbutton(card, text=title, variable=self.component_vars[key], command=self._update_all_state).pack(anchor="w")
            ttk.Label(card, text=description, style="CardDescription.TLabel", wraplength=360, justify="left").pack(anchor="w", pady=(6, 0))

        bottom = ttk.Frame(self.page_container, style="App.TFrame")
        bottom.pack(fill="x", pady=(18, 0))
        self.run_button = ttk.Button(bottom, text="Instalar componentes selecionados", style="Primary.TButton", command=self.start_installation)
        if self.is_running:
            self.run_button.configure(state="disabled", text="Instalando...")
        self.run_button.pack(side="right")
        ttk.Button(bottom, text="Abrir instruções", command=self.show_help).pack(side="right", padx=(0, 10))

    def _make_labeled_entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar, readonly: bool = False, values: list[str] | None = None) -> None:
        box = ttk.Frame(parent, style="App.TFrame")
        box.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ttk.Label(box, text=label, style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        if values:
            widget = ttk.Combobox(box, textvariable=variable, values=values, state="readonly" if readonly else "normal")
        else:
            widget = ttk.Entry(box, textvariable=variable)
        widget.pack(fill="x")

    def _make_project_selector(self, parent: ttk.Frame) -> None:
        box = ttk.Frame(parent, style="App.TFrame")
        box.pack(side="left", fill="x", expand=True)
        ttk.Label(box, text="Pasta do projeto", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        row = ttk.Frame(box, style="App.TFrame")
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.project_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Escolher...", command=self.choose_project).pack(side="left", padx=(8, 0))

    def show_help(self) -> None:
        self.current_page = "help"
        self._clear_page()
        ttk.Label(self.page_container, text="Como usar", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.page_container, text="Siga estas etapas para configurar o ambiente com segurança.", style="Subtitle.TLabel").pack(anchor="w", pady=(4, 12))

        help_text = (
            "1. Na Home, selecione o sistema operacional que será configurado.\n\n"
            "2. Escolha a pasta raiz do seu projeto. O arquivo .vscode/settings.json será criado nessa pasta quando a configuração do Code Runner for selecionada.\n\n"
            "3. Marque apenas o que precisa. Para um ambiente completo, use Selecionar tudo. Para instalar somente o executor, deixe marcado apenas Code Runner.\n\n"
            "4. Clique em Instalar componentes selecionados. Algumas etapas podem pedir autorização de administrador.\n\n"
            "5. Depois da instalação, abra um arquivo .c no VS Code e pressione Ctrl+Alt+N para executar pelo Code Runner.\n\n"
            "Atenção: o aplicativo executa comandos do sistema escolhido. Use Windows quando o aplicativo estiver rodando no Windows e Ubuntu/Debian ou Fedora quando estiver rodando na distribuição Linux correspondente.\n\n"
            "Windows: o GCC é instalado pelo MSYS2 em C:\\msys64\\ucrt64\\bin. Ubuntu/Debian: o GCC é instalado pelo apt. Fedora: o GCC é instalado pelo dnf.\n\n"
            "Se algo falhar, consulte o Registro da operação na parte inferior da janela. Corrija o requisito indicado e execute novamente."
        )
        text = ScrolledText(self.page_container, wrap="word", font=("Segoe UI", 10), padx=16, pady=16, background="white", foreground="#26364d", relief="solid", borderwidth=1)
        text.pack(fill="both", expand=True)
        text.insert("1.0", help_text)
        text.configure(state="disabled")

        ttk.Button(self.page_container, text="Voltar para Home", style="Primary.TButton", command=self.show_home).pack(anchor="e", pady=(14, 0))

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

    def selected_components(self) -> list[str]:
        return [key for key, _, _ in COMPONENTS if self.component_vars[key].get()]

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _queue_log(self, text: str) -> None:
        self.command_queue.put(("log", text))

    def _make_command(self, args: list[str]) -> str:
        if os.name == "nt":
            return subprocess.list2cmdline(args)
        return shlex.join(args)

    def _elevated_linux(self, args: list[str]) -> list[str]:
        if shutil.which("pkexec"):
            return ["pkexec", *args]
        return ["sudo", *args]

    def _code_command(self) -> str:
        candidates = [shutil.which("code")]
        if os.name == "nt":
            local = os.environ.get("LOCALAPPDATA", "")
            candidates.extend([
                os.path.join(local, "Programs", "Microsoft VS Code", "bin", "code.cmd"),
                r"C:\Program Files\Microsoft VS Code\bin\code.cmd",
            ])
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return "code"

    def build_commands(self, target_os: str, selected: list[str], project_path: Path) -> list[tuple[str, list[str] | None]]:
        commands: list[tuple[str, list[str] | None]] = []
        code = self._code_command()
        extensions: list[str] = []

        if target_os == "Windows":
            bash = r"C:\msys64\usr\bin\bash.exe"
            if "vscode" in selected:
                commands.append(("Instalando o Visual Studio Code", ["winget", "install", "--id", "Microsoft.VisualStudioCode", "--exact", "--source", "winget", "--accept-package-agreements", "--accept-source-agreements"]))
            if "compiler" in selected or "debugger" in selected:
                commands.append(("Instalando ou atualizando o MSYS2", ["winget", "install", "--id", "MSYS2.MSYS2", "--exact", "--source", "winget", "--accept-package-agreements", "--accept-source-agreements"]))
                commands.append(("Atualizando os pacotes do MSYS2", [bash, "-lc", "pacman -Syu --noconfirm"]),)
                packages = []
                if "compiler" in selected:
                    packages.extend(["mingw-w64-ucrt-x86_64-gcc", "mingw-w64-ucrt-x86_64-make"])
                if "debugger" in selected:
                    packages.append("mingw-w64-ucrt-x86_64-gdb")
                commands.append(("Instalando GCC/GDB/Make", [bash, "-lc", "pacman -S --needed --noconfirm " + " ".join(packages)]))
                commands.append(("Adicionando o GCC ao PATH do usuário", None))
            if "cmake" in selected:
                commands.append(("Instalando CMake", ["winget", "install", "--id", "Kitware.CMake", "--exact", "--source", "winget", "--accept-package-agreements", "--accept-source-agreements"]))
            if "extensions" in selected:
                extensions.extend([EXTENSIONS["cpp"], EXTENSIONS["cpp_pack"], EXTENSIONS["cmake_tools"], EXTENSIONS["error_lens"]])
            if "code_runner" in selected:
                extensions.append(EXTENSIONS["code_runner"])

        elif target_os == "Ubuntu/Debian":
            if "compiler" in selected:
                commands.append(("Instalando GCC e ferramentas de compilação", self._elevated_linux(["apt-get", "update"])))
                commands.append(("Instalando GCC/Make", self._elevated_linux(["apt-get", "install", "-y", "build-essential", "gcc", "make"])))
            if "debugger" in selected:
                commands.append(("Instalando GDB", self._elevated_linux(["apt-get", "install", "-y", "gdb"])))
            if "vscode" in selected:
                if shutil.which("snap"):
                    commands.append(("Instalando o Visual Studio Code", self._elevated_linux(["snap", "install", "code", "--classic"])))
                else:
                    commands.append(("VS Code: instalar manualmente", None))
            if "cmake" in selected:
                commands.append(("Instalando CMake", self._elevated_linux(["apt-get", "install", "-y", "cmake"])))
            if "extensions" in selected:
                extensions.extend([EXTENSIONS["cpp"], EXTENSIONS["cpp_pack"], EXTENSIONS["cmake_tools"], EXTENSIONS["error_lens"]])
            if "code_runner" in selected:
                extensions.append(EXTENSIONS["code_runner"])

        elif target_os == "Fedora":
            if "compiler" in selected:
                commands.append(("Instalando GCC e ferramentas de desenvolvimento", self._elevated_linux(["dnf", "groupinstall", "-y", "Development Tools"])))
                commands.append(("Instalando GCC/Make", self._elevated_linux(["dnf", "install", "-y", "gcc", "gcc-c++", "make"])))
            if "debugger" in selected:
                commands.append(("Instalando GDB", self._elevated_linux(["dnf", "install", "-y", "gdb"])))
            if "vscode" in selected:
                commands.append(("VS Code: instalar manualmente", None))
            if "cmake" in selected:
                commands.append(("Instalando CMake", self._elevated_linux(["dnf", "install", "-y", "cmake"])))
            if "extensions" in selected:
                extensions.extend([EXTENSIONS["cpp"], EXTENSIONS["cpp_pack"], EXTENSIONS["cmake_tools"], EXTENSIONS["error_lens"]])
            if "code_runner" in selected:
                extensions.append(EXTENSIONS["code_runner"])

        for extension in dict.fromkeys(extensions):
            commands.append((f"Instalando extensão {extension}", [code, "--install-extension", extension, "--force"]))

        if "code_runner" in selected:
            commands.append(("Criando a configuração do Code Runner", None))
            commands.append(("Criando a pasta .vscode", None))

        return commands

    def write_code_runner_settings(self, project_path: Path, target_os: str) -> Path:
        vscode_dir = project_path / ".vscode"
        vscode_dir.mkdir(parents=True, exist_ok=True)
        settings_path = vscode_dir / "settings.json"
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                settings_path = vscode_dir / "settings.c-setup.generated.json"
                settings = {}
        else:
            settings = {}

        if target_os == "Windows":
            compiler = r"C:\msys64\ucrt64\bin\gcc.exe"
            mode = "windows-gcc-x64"
            command = 'cd $dir && gcc "$fileName" -Wall -Wextra -std=c17 -o "$fileNameWithoutExt.exe" && "$dir\\$fileNameWithoutExt.exe"'
        else:
            compiler = "/usr/bin/gcc"
            mode = "linux-gcc-x64"
            command = 'cd $dir && gcc "$fileName" -Wall -Wextra -std=c17 -o "$fileNameWithoutExt" && "$dir/$fileNameWithoutExt"'

        settings.update({
            "C_Cpp.default.compilerPath": compiler,
            "C_Cpp.default.cStandard": "c17",
            "C_Cpp.default.intelliSenseMode": mode,
            "code-runner.runInTerminal": True,
            "code-runner.saveFileBeforeRun": True,
        })
        executor_map = settings.get("code-runner.executorMap", {})
        if not isinstance(executor_map, dict):
            executor_map = {}
        executor_map["c"] = command
        settings["code-runner.executorMap"] = executor_map
        associations = settings.get("files.associations", {})
        if not isinstance(associations, dict):
            associations = {}
        associations.update({"*.c": "c", "*.h": "c"})
        settings["files.associations"] = associations
        settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return settings_path

    def start_installation(self) -> None:
        if self.is_running:
            return
        selected = self.selected_components()
        if not selected:
            messagebox.showwarning("Nenhum componente", "Selecione pelo menos um componente para continuar.")
            return

        target_os = self.os_var.get()
        project_path = Path(self.project_var.get()).expanduser()
        if not project_path.exists():
            try:
                project_path.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                messagebox.showerror("Pasta inválida", f"Não foi possível criar a pasta escolhida:\n{error}")
                return

        current = self.detect_os()
        if current != target_os and not messagebox.askyesno(
            "Sistema diferente",
            f"O sistema detectado é {current}, mas você escolheu {target_os}.\n\nOs comandos só funcionarão se forem compatíveis com o sistema em execução. Deseja continuar?",
        ):
            return

        self.is_running = True
        self.run_button.configure(state="disabled", text="Instalando...")
        self.total_steps = len(self.build_commands(target_os, selected, project_path))
        self.progress_var.set(0)
        self.status_var.set("Preparando instalação...")
        self.step_var.set(f"0 de {self.total_steps} etapas")
        self.append_log(f"Iniciando configuração para {target_os} em {project_path}")
        self.append_log("Componentes: " + ", ".join(title for key, title, _ in COMPONENTS if key in selected))
        self.append_log(f"Total de etapas: {self.total_steps}")
        self.install_thread = threading.Thread(target=self._installation_worker, args=(target_os, selected, project_path), daemon=True)
        self.install_thread.start()

    def _installation_worker(self, target_os: str, selected: list[str], project_path: Path) -> None:
        try:
            for step_index, (description, args) in enumerate(self.build_commands(target_os, selected, project_path), start=1):
                self.command_queue.put(("stage", (step_index, description, False)))
                if args is None:
                    if description == "Adicionando o GCC ao PATH do usuário":
                        if target_os == "Windows":
                            self._run_path_update_windows()
                        self.command_queue.put(("stage", (step_index, description, True)))
                        continue
                    if description == "Criando a configuração do Code Runner":
                        settings_path = self.write_code_runner_settings(project_path, target_os)
                        self._queue_log(f"Configuração criada em {settings_path}")
                        self.command_queue.put(("stage", (step_index, description, True)))
                        continue
                    if description == "Criando a pasta .vscode":
                        self.command_queue.put(("stage", (step_index, description, True)))
                        continue
                    self._queue_log(f"Aviso: {description}. Consulte a aba Como usar.")
                    self.command_queue.put(("stage", (step_index, description, True)))
                    continue
                self._queue_log(f"$ {self._make_command(args)}")
                result = subprocess.run(
                    args,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                if result.stdout:
                    self._queue_log(result.stdout.rstrip())
                if result.returncode != 0:
                    raise RuntimeError(f"A etapa '{description}' terminou com código {result.returncode}.")
                self._queue_log(f"Concluído: {description}")
                self.command_queue.put(("stage", (step_index, description, True)))
            self.command_queue.put(("done", "Configuração concluída com sucesso."))
        except FileNotFoundError as error:
            self.command_queue.put(("error", f"Comando não encontrado: {error}. Verifique se o gerenciador necessário está instalado."))
        except Exception as error:  # noqa: BLE001 - a mensagem será mostrada na interface
            self.command_queue.put(("error", str(error)))

    def _run_path_update_windows(self) -> None:
        powershell = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "$entry='C:\\msys64\\ucrt64\\bin'; $p=[Environment]::GetEnvironmentVariable('Path','User'); if ($null -eq $p) {$p=''}; if ($p -notlike ('*' + $entry + '*')) {[Environment]::SetEnvironmentVariable('Path', ($p.TrimEnd(';') + ';' + $entry).Trim(';'), 'User')}",
        ]
        result = subprocess.run(powershell, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode != 0:
            raise RuntimeError("Não foi possível atualizar o PATH do usuário no Windows.")
        self._queue_log("GCC adicionado ao PATH do usuário. Reinicie o VS Code para reconhecê-lo.")

    def _process_queue(self) -> None:
        try:
            while True:
                event, payload = self.command_queue.get_nowait()
                if event == "log":
                    self.append_log(str(payload))
                elif event == "stage":
                    step_index, description, completed = payload
                    if completed:
                        percent = (step_index / self.total_steps * 100) if self.total_steps else 100
                        self.progress_var.set(percent)
                        self.status_var.set(f"Concluído: {description}")
                        self.step_var.set(f"{step_index} de {self.total_steps} etapas")
                    else:
                        percent = ((step_index - 1) / self.total_steps * 100) if self.total_steps else 0
                        self.progress_var.set(percent)
                        self.status_var.set(f"Executando: {description}")
                        self.step_var.set(f"Etapa {step_index} de {self.total_steps}")
                elif event == "done":
                    self.is_running = False
                    self.progress_var.set(100)
                    self.status_var.set("Concluído")
                    self.step_var.set(f"{self.total_steps} de {self.total_steps} etapas")
                    self.run_button.configure(state="normal", text="Instalar componentes selecionados")
                    self.append_log(str(payload))
                    messagebox.showinfo("Concluído", str(payload))
                elif event == "error":
                    self.is_running = False
                    self.status_var.set("Falha na instalação")
                    self.step_var.set("Operação interrompida")
                    self.run_button.configure(state="normal", text="Instalar componentes selecionados")
                    self.append_log("ERRO: " + str(payload))
                    messagebox.showerror("Falha na instalação", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._process_queue)


def main() -> None:
    app = InstallerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
