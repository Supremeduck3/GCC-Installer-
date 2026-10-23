#!/usr/bin/env bash
set -Eeuo pipefail

# Instala o ambiente de desenvolvimento em C no Ubuntu/Debian ou Fedora.
# Execute este arquivo a partir da pasta raiz do projeto no VS Code.

# Usa sudo só quando não estiver rodando como root.
if [[ $EUID -eq 0 ]]; then
  SUDO=()
elif command -v sudo >/dev/null 2>&1; then
  SUDO=(sudo)
else
  echo 'Erro: sudo não foi encontrado. Rode este script como root.' >&2
  exit 1
fi

echo '=== Instalação do ambiente C para VS Code ==='
echo 'Instalando compilador, ferramentas de build e depurador...'

if command -v apt-get >/dev/null 2>&1; then
  "${SUDO[@]}" apt-get update
  "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y build-essential gcc gdb make cmake
elif command -v dnf >/dev/null 2>&1; then
  "${SUDO[@]}" dnf install -y gcc gcc-c++ gdb make cmake
else
  echo 'Este script suporta Ubuntu/Debian (apt) e Fedora (dnf).' >&2
  exit 1
fi

if ! command -v gcc >/dev/null 2>&1; then
  echo 'Erro: gcc não foi encontrado após a instalação.' >&2
  exit 1
fi

gcc_path="$(command -v gcc)"
echo "GCC encontrado em: $gcc_path"
gcc --version | head -n 1

extensions=(
  'ms-vscode.cpptools'
  'ms-vscode.cpptools-extension-pack'
  'ms-vscode.cmake-tools'
  'formulahendry.code-runner'
  'usernamehw.errorlens'
)

code_cmd=''
for candidate in "$(command -v code 2>/dev/null || true)" /snap/bin/code /usr/bin/code /usr/share/code/bin/code; do
  if [[ -n "$candidate" && -x "$candidate" ]]; then
    code_cmd="$candidate"
    break
  fi
done

if [[ -n "$code_cmd" ]]; then
  echo 'Instalando extensões do VS Code...'
  for extension in "${extensions[@]}"; do
    if [[ $EUID -eq 0 && -n "${SUDO_USER:-}" ]]; then
      # O VS Code se recusa a rodar como root; instala para o usuário real.
      sudo -u "$SUDO_USER" "$code_cmd" --install-extension "$extension" --force
    else
      "$code_cmd" --install-extension "$extension" --force
    fi
  done
else
  echo 'Aviso: o comando code não foi encontrado.' >&2
  echo 'Instale o VS Code (https://code.visualstudio.com/) e execute este script novamente.' >&2
fi

mkdir -p .vscode
settings_path='.vscode/settings.json'
if [[ -e "$settings_path" ]]; then
  settings_path='.vscode/settings.c-vscode.generated.json'
  echo "Aviso: .vscode/settings.json já existe; a configuração foi salva em $settings_path" >&2
fi

cat > "$settings_path" <<JSON
{
  "C_Cpp.default.compilerPath": "$gcc_path",
  "C_Cpp.default.cStandard": "c17",
  "C_Cpp.default.intelliSenseMode": "linux-gcc-x64",
  "code-runner.runInTerminal": true,
  "code-runner.saveFileBeforeRun": true,
  "code-runner.clearPreviousOutput": true,
  "code-runner.executorMap": {
    "c": "cd \$dir && gcc \"\$fileName\" -Wall -Wextra -std=c17 -o \"\$fileNameWithoutExt\" && ./\"\$fileNameWithoutExt\""
  },
  "files.associations": {
    "*.h": "c",
    "*.c": "c"
  }
}
JSON

if [[ $EUID -eq 0 && -n "${SUDO_USER:-}" ]]; then
  chown -R "$SUDO_USER": .vscode
fi

echo
printf 'Instalação concluída.\n'
printf 'Configuração criada em: %s\n' "$settings_path"
printf 'Teste com: gcc --version\n'
printf 'No VS Code, abra um arquivo .c e pressione Ctrl+Alt+N para usar o Code Runner.\n'
