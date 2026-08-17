# Publicar o projeto no GitHub

O GitHub armazena o código do projeto. O arquivo `.exe` pode ser gerado no Windows quando necessário; para manter o repositório leve, a configuração padrão ignora `dist/`, `build/`, arquivos `.spec`, ZIPs e caches do Python.

## 1. Criar o repositório no GitHub

Acesse [github.com](https://github.com), entre na sua conta e escolha **New repository**. Defina um nome, por exemplo `c-setup-assistant`. Para evitar conflitos no primeiro envio, deixe desmarcadas as opções de criar README, `.gitignore` ou licença, pois esses arquivos já estão no projeto local.

Copie a URL HTTPS do repositório, que terá um formato semelhante a:

```text
https://github.com/SEU_USUARIO/c-setup-assistant.git
```

## 2. Abrir o terminal na pasta do projeto

Extraia o pacote, abra o terminal dentro da pasta `instalador-c-vscode` e confirme o local:

```bash
cd caminho/para/instalador-c-vscode
```

No Windows PowerShell, o exemplo seria:

```powershell
cd "$HOME\Downloads\instalador-c-vscode"
```

## 3. Inicializar o Git e fazer o primeiro envio

Execute os comandos abaixo, substituindo a URL pelo endereço do seu repositório:

```bash
git init
git branch -M main
git add .
git commit -m "feat: adiciona assistente grafico para C e VS Code"
git remote add origin https://github.com/SEU_USUARIO/c-setup-assistant.git
git push -u origin main
```

Quando o Git solicitar autenticação via HTTPS, utilize o login do GitHub e um **Personal Access Token** no lugar da senha. Outra opção é configurar uma chave SSH e usar uma URL no formato `git@github.com:SEU_USUARIO/c-setup-assistant.git`.

## 4. Atualizar o projeto depois de alterações

Depois de modificar o aplicativo, execute:

```bash
git status
git add .
git commit -m "feat: adiciona barra de progresso"
git push
```

Use mensagens de commit curtas e descritivas. Exemplos: `fix: corrige caminho do GCC no Windows` ou `docs: atualiza instrucoes de build`.

## 5. Publicar o executável Windows

O `.exe` não deve ser colocado diretamente no histórico a cada compilação. No computador Windows, execute `build-windows.bat` e confirme que o arquivo apareceu em `dist\\C-Setup-Assistant.exe`. Depois, no GitHub, abra a página **Releases**, escolha **Create a new release**, defina uma tag como `v1.0.0` e anexe o `.exe` na seção de arquivos binários.

Essa separação mantém o código no repositório e disponibiliza o executável pronto para download na área apropriada de Releases.

## Cuidados importantes

Nunca envie senhas, tokens, chaves privadas, arquivos `.env` ou credenciais para o GitHub. Verifique `git status` antes de cada `git add .`. O `.gitignore` deste projeto já exclui caches, pastas de build e arquivos gerados mais comuns.

## Referências

[1]: https://docs.github.com/en/get-started/start-your-journey/creating-an-account-on-github "GitHub Docs — Creating an account"
[2]: https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository "GitHub Docs — Creating a new repository"
[3]: https://docs.github.com/en/get-started/getting-started-with-git/set-up-git "GitHub Docs — Set up Git"
[4]: https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository "GitHub Docs — Managing releases"
