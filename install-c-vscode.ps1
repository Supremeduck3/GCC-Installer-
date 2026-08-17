#requires -Version 5.1
<#
.SYNOPSIS
    Instala o ambiente de desenvolvimento em C no Windows.
.DESCRIPTION
    Instala o MSYS2, atualiza os pacotes UCRT64, instala GCC/GDB/Make,
    adiciona o GCC ao PATH do usuário, instala extensões do VS Code e
    cria a configuração do Code Runner no projeto atual.
.NOTES
    Execute este script a partir da pasta raiz do seu projeto no VS Code.
#>

$ErrorActionPreference = 'Stop'

function Test-CommandExists {
    param([Parameter(Mandatory = $true)][string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Add-UserPathEntry {
    param([Parameter(Mandatory = $true)][string]$Entry)

    $currentPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ([string]::IsNullOrWhiteSpace($currentPath)) {
        $currentPath = ''
    }

    $entries = $currentPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    $alreadyExists = $entries | Where-Object { $_.TrimEnd('\') -ieq $Entry.TrimEnd('\') }

    if ($null -eq $alreadyExists) {
        $newPath = (($entries + $Entry) -join ';')
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
        Write-Host "Adicionado ao PATH do usuário: $Entry" -ForegroundColor Green
    } else {
        Write-Host "O diretório já está no PATH: $Entry" -ForegroundColor DarkGray
    }
}

Write-Host '=== Instalação do ambiente C para VS Code ===' -ForegroundColor Cyan

if (-not (Test-CommandExists 'winget')) {
    throw 'O winget não foi encontrado. Instale/atualize o App Installer pela Microsoft Store e execute o script novamente.'
}

# Instala o VS Code, caso o comando code ainda não esteja disponível.
if (-not (Test-CommandExists 'code')) {
    Write-Host 'VS Code não encontrado no PATH. Tentando instalar pelo winget...' -ForegroundColor Yellow
    winget install --id Microsoft.VisualStudioCode --exact --source winget --accept-package-agreements --accept-source-agreements
    Write-Host 'O VS Code foi instalado. Feche e abra o PowerShell se o comando code ainda não for reconhecido.' -ForegroundColor Yellow
}

# Instala o MSYS2, que fornece o GCC nativo para Windows.
$msysRoot = 'C:\msys64'
if (-not (Test-Path (Join-Path $msysRoot 'usr\bin\bash.exe'))) {
    Write-Host 'Instalando MSYS2...' -ForegroundColor Yellow
    winget install --id MSYS2.MSYS2 --exact --source winget --accept-package-agreements --accept-source-agreements
}

$bash = Join-Path $msysRoot 'usr\bin\bash.exe'
if (-not (Test-Path $bash)) {
    throw "MSYS2 não foi encontrado em $msysRoot. Instale-o manualmente e execute novamente."
}

# A primeira atualização pode solicitar uma segunda execução em instalações novas.
Write-Host 'Atualizando os pacotes do MSYS2...' -ForegroundColor Yellow
& $bash -lc 'pacman -Syu --noconfirm' 2>$null
& $bash -lc 'pacman -Syu --noconfirm' 2>$null

Write-Host 'Instalando GCC, GDB e Make...' -ForegroundColor Yellow
& $bash -lc 'pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-gdb mingw-w64-ucrt-x86_64-make'

$gccBin = Join-Path $msysRoot 'ucrt64\bin'
$gccExe = Join-Path $gccBin 'gcc.exe'
if (-not (Test-Path $gccExe)) {
    throw "O GCC não foi encontrado em $gccExe após a instalação."
}
Add-UserPathEntry -Entry $gccBin

$extensions = @(
    'ms-vscode.cpptools',
    'ms-vscode.cpptools-extension-pack',
    'formulahendry.code-runner',
    'usernamehw.errorlens'
)

if (Test-CommandExists 'code') {
    Write-Host 'Instalando extensões do VS Code...' -ForegroundColor Yellow
    foreach ($extension in $extensions) {
        code --install-extension $extension --force
    }
} else {
    Write-Host 'O comando code não está disponível nesta sessão; instale as extensões manualmente ou reabra o PowerShell e execute novamente.' -ForegroundColor Yellow
}

# Configurações de workspace. Se já existir settings.json, não sobrescreve o arquivo.
$workspaceDir = (Get-Location).Path
$vscodeDir = Join-Path $workspaceDir '.vscode'
New-Item -ItemType Directory -Path $vscodeDir -Force | Out-Null
$settingsPath = Join-Path $vscodeDir 'settings.json'
if (Test-Path $settingsPath) {
    $settingsPath = Join-Path $vscodeDir 'settings.c-vscode.generated.json'
    Write-Host "settings.json já existe; a configuração foi salva separadamente em $settingsPath" -ForegroundColor Yellow
}

$settings = [ordered]@{
    'C_Cpp.default.compilerPath' = 'C:\msys64\ucrt64\bin\gcc.exe'
    'C_Cpp.default.cStandard' = 'c17'
    'C_Cpp.default.intelliSenseMode' = 'windows-gcc-x64'
    'code-runner.runInTerminal' = $true
    'code-runner.saveFileBeforeRun' = $true
    'code-runner.executorMap' = [ordered]@{
        'c' = 'cd $dir && gcc "$fileName" -Wall -Wextra -std=c17 -o "$fileNameWithoutExt.exe" && "$dir\\$fileNameWithoutExt.exe"'
    }
    'files.associations' = [ordered]@{
        '*.h' = 'c'
        '*.c' = 'c'
    }
}
$settings | ConvertTo-Json -Depth 10 | Set-Content -Path $settingsPath -Encoding UTF8

Write-Host ''
Write-Host 'Instalação concluída.' -ForegroundColor Green
Write-Host "Configuração criada em: $settingsPath"
Write-Host 'Feche e abra novamente o VS Code/PowerShell para atualizar o PATH.' -ForegroundColor Yellow
Write-Host 'Teste com: gcc --version'
Write-Host 'No VS Code, abra um arquivo .c e pressione Ctrl+Alt+N para usar o Code Runner.'
