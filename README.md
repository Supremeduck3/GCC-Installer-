# Ambiente C para VS Code

Este pacote configura um ambiente básico para programar em **C** no Visual Studio Code. Ele instala o compilador GCC, o depurador GDB, ferramentas de compilação, extensões úteis e uma configuração de execução pelo Code Runner.

## Arquivos

| Arquivo | Finalidade |
|---|---|
| `install-c-vscode.ps1` | Instalação no Windows usando MSYS2 e `winget`. |
| `install-c-vscode.sh` | Instalação no Ubuntu/Debian usando `apt`. |

> Os scripts devem ser executados a partir da pasta raiz do seu projeto. Assim, a configuração é criada em `.vscode/settings.json`.

## Windows

Abra o PowerShell na pasta do projeto. Se necessário, permita a execução de scripts apenas para a sessão atual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Execute:

```powershell
.\install-c-vscode.ps1
```

O script utiliza o **MSYS2** para instalar o GCC nativo para Windows no diretório `C:\msys64\ucrt64\bin`. Esse diretório é adicionado ao `PATH` do usuário. Após a conclusão, feche e abra novamente o PowerShell e o VS Code para que a alteração do `PATH` seja reconhecida.

Teste:

```powershell
gcc --version
gdb --version
```

Se o comando `code` não estiver disponível após a instalação do VS Code, reinicie o terminal e execute novamente o script para instalar as extensões.

## Ubuntu ou Debian

Dê permissão de execução e execute o script:

```bash
chmod +x install-c-vscode.sh
./install-c-vscode.sh
```

Teste:

```bash
gcc --version
gdb --version
```

O script pressupõe que o VS Code já esteja instalado e que o comando `code` esteja no `PATH`. Caso contrário, instale o VS Code pelo site oficial ou pelo gerenciador de pacotes da sua distribuição, habilite o comando `code` e execute o script novamente.

## Extensões instaladas

| Extensão | Uso |
|---|---|
| `ms-vscode.cpptools` | IntelliSense, navegação, análise e depuração de C/C++. |
| `ms-vscode.cpptools-extension-pack` | Pacote complementar para desenvolvimento em C/C++. |
| `ms-vscode.cmake-tools` | Integração com projetos que usam CMake. |
| `formulahendry.code-runner` | Execução rápida do arquivo atual. |
| `usernamehw.errorlens` | Exibe erros e avisos diretamente na linha do código. |

## Como usar o Code Runner

Crie um arquivo `main.c`:

```c
#include <stdio.h>

int main(void) {
    printf("Olá, C!\n");
    return 0;
}
```

Abra o arquivo no VS Code e pressione **Ctrl + Alt + N**, ou clique no botão **Run Code**. O Code Runner salvará o arquivo, compilará usando `gcc` com `-Wall`, `-Wextra` e o padrão **C17**, e executará o programa no terminal integrado.

A compilação manual equivalente no Linux é:

```bash
gcc main.c -Wall -Wextra -std=c17 -o main && ./main
```

No Windows, o executável gerado será `main.exe`.

## Observação sobre projetos maiores

O Code Runner é conveniente para arquivos simples. Para projetos com vários arquivos, bibliotecas próprias ou configurações de produção, é melhor usar **Make** ou **CMake**. As extensões e ferramentas instaladas pelos scripts já deixam essa base preparada.

## Referências

[1]: https://code.visualstudio.com/docs/languages/cpp "Visual Studio Code — C/C++"
[2]: https://marketplace.visualstudio.com/items?itemName=formulahendry.code-runner "Visual Studio Code Marketplace — Code Runner"
[3]: https://www.msys2.org/docs/installing/ "MSYS2 — Installing"
[4]: https://packages.ubuntu.com/jammy/build-essential "Ubuntu Packages — build-essential"
