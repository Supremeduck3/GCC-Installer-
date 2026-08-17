#!/usr/bin/env bash
set -Eeuo pipefail

# Instala o ambiente de desenvolvimento em C no Ubuntu/Debian.
# Execute este arquivo a partir da pasta raiz do projeto no VS Code.

if ! command -v sudo >/dev/null 2>&1; then
  echo 'Erro: sudo não foi encontrado.' >&2
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo 'Este script foi preparado para Ubuntu/Debian.' >&2
  echo 'Para Fedora, use: sudo dnf groupinstall "Development Tools" && sudo dnf install gdb.' >&2
  exit 1
fi

echo '=== Instalação do ambiente C para VS Code ==='

echo 'Instalando compilador, ferramentas de build e depurador...'
sudo apt-get update
sudo apt-get install -y build-essential gcc gdb make

if ! command -v gcc >/dev/null 2>&1; then
  echo 'Erro: gcc não foi encontrado após a instalação.' >&2
  exit 1
fi

echo "GCC encontrado em: $(command -v gcc)"
gcc --version | head -n 1

extensions=(
  'ms-vscode.cpptools'
  'ms-vscode.cpptools-extension-pack'
  'ms-vscode.cmake-tools'
  'formulahendry.code-runner'
  'usernamehw.errorlens'
)

if command -v code >/dev/null 2>&1; then
  echo 'Instalando extensões do VS Code...'
  for extension in "${extensions[@]}"; do
    code --install-extension "$extension" --force
  done
else
  echo 'Aviso: o comando code não está no PATH.' >&2
  echo 'Instale o VS Code ou habilite o comando code e execute este script novamente.' >&2
fi

mkdir -p .vscode
settings_path='.vscode/settings.json'
if [[ -e "$settings_path" ]]; then
  settings_path='.vscode/settings.c-vscode.generated.json'
  echo "Aviso: .vscode/settings.json já existe; a configuração foi salva em $settings_path" >&2
fi

cat > "$settings_path" <<'JSON'
{
  "C_Cpp.default.compilerPath": "/usr/bin/gcc",
  "C_Cpp.default.cStandard": "c17",
  "C_Cpp.default.intelliSenseMode": "linux-gcc-x64",
  "code-runner.runInTerminal": true,
  "code-runner.saveFileBeforeRun": true,
  "code-runner.executorMap": {
    "c": "cd $dir && gcc \"$fileName\" -Wall -Wextra -std=c17 -o \"$fileNameWithoutExt\" && \"$dir/$fileNameWithoutExt\""
  },
  "files.associations": {
    "*.h": "c",
    "*.c": "c"
  }
}
JSON

echo
printf 'Instalação concluída.\n'
printf 'Configuração criada em: %s\n' "$settings_path"
printf 'Teste com: gcc --version\n'
printf 'No VS Code, abra um arquivo .c e pressione Ctrl+Alt+N para usar o Code Runner.\n'
