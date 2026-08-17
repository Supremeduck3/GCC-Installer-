# C Setup Assistant

O `C Setup Assistant` é um aplicativo gráfico simples para instalar e configurar um ambiente de C no VS Code. A interface possui uma **Home**, uma aba **Como usar**, seleção do sistema operacional, escolha da pasta do projeto, seleção individual dos componentes e um registro da operação.

## O que a interface permite

| Área | Função |
|---|---|
| Home | Escolher o sistema, a pasta do projeto e os componentes. |
| Como usar | Consultar as instruções e voltar para a Home. |
| Componentes | Instalar tudo ou somente GCC, GDB, VS Code, extensões, Code Runner e/ou CMake. |
| Registro da operação | Acompanhar os comandos e mensagens de erro. |
| Barra de progresso | Mostrar a etapa atual, o percentual e se a operação foi concluída ou interrompida. |

O aplicativo não executa comandos ao abrir. A instalação começa apenas depois que o usuário clica em **Instalar componentes selecionados**. Durante a execução, a barra de progresso mostra a etapa atual, o percentual aproximado e um contador no formato `etapa atual de total de etapas`. Em caso de erro, o status muda para **Falha na instalação** e o registro mostra a etapa que interrompeu o processo.

Para publicar o projeto no GitHub, consulte o arquivo `GITHUB.md`.

## Como executar durante o desenvolvimento

No Linux, instale o Tkinter caso ele ainda não exista e execute:

```bash
sudo apt-get install -y python3-tk
python3 instalador_c_gui.py
```

No Windows, é necessário ter Python 3 instalado. Execute:

```powershell
python instalador_c_gui.py
```

O arquivo deve ser executado no sistema que será configurado. A seleção do sistema operacional determina os comandos usados pelo assistente, mas não transforma comandos Linux em comandos Windows nem o contrário.

## Como gerar o `.exe` no Windows

O arquivo `build-windows.bat` instala o PyInstaller e gera:

```text
dist\\C-Setup-Assistant.exe
```

Para usar:

```text
1. Abra esta pasta em um computador Windows.
2. Instale o Python 3 e marque “Add Python to PATH”.
3. Execute build-windows.bat.
4. Distribua o arquivo dist\\C-Setup-Assistant.exe.
```

O executável é criado com a opção `--windowed`, portanto não abre um console separado. A primeira execução da instalação pode solicitar permissões administrativas para `winget`, MSYS2 ou o gerenciador de pacotes do sistema.

## Observação sobre o ambiente atual

O projeto também pode ser empacotado como um executável Linux, mas um `.exe` Windows precisa ser compilado em Windows, porque o empacotador incorpora o interpretador e as bibliotecas do sistema-alvo. Por isso, o pacote inclui o código completo e o `build-windows.bat` para gerar o `.exe` no Windows.

## Segurança e comportamento

O aplicativo monta comandos com argumentos separados, mostra cada etapa no registro e interrompe o processo quando uma etapa retorna erro. Como a instalação de pacotes altera o sistema, execute o aplicativo somente quando você reconhecer o sistema operacional selecionado e os componentes marcados.

## Referências

[1]: https://docs.python.org/3/library/tkinter.html "Python Documentation — tkinter"
[2]: https://pyinstaller.org/en/stable/ "PyInstaller Documentation"
[3]: https://code.visualstudio.com/docs/editor/command-line "Visual Studio Code — Command Line Interface"
[4]: https://marketplace.visualstudio.com/items?itemName=formulahendry.code-runner "Visual Studio Code Marketplace — Code Runner"
