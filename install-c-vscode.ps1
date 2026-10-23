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
    Pode ser executado de novo com segurança: o que já existe é pulado.
#>

$ErrorActionPreference = 'Stop'
# Garante acentos corretos na saída de programas externos.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$msysRoot = 'C:\msys64'
$bash = Join-Path $msysRoot 'usr\bin\bash.exe'
$gccBin = Join-Path $msysRoot 'ucrt64\bin'
$gccExe = Join-Path $gccBin 'gcc.exe'

# winget: "já instalado" e "nenhuma atualização" não são erros.
$wingetOk = @(0, -1978335189, -1978335135)

function Test-CommandExists {
    param([Parameter(Mandatory = $true)][string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Update-SessionPath {
    # Recarrega o PATH do registro para enxergar programas recém-instalados.
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ';'
}

function Invoke-Native {
    # Executa um programa externo e verifica o código de saída.
    # No PowerShell 5.1, ErrorActionPreference=Stop + stderr de programa externo
    # vira erro fatal; por isso relaxamos só durante a chamada.
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [int[]]$OkCodes = @(0),
        [switch]$IgnoreFailure
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $FilePath @Arguments 2>&1 | ForEach-Object { Write-Host "  $_" }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if (($OkCodes -notcontains $code) -and -not $IgnoreFailure) {
        throw "O comando '$FilePath $($Arguments -join ' ')' falhou com código $code."
    }
}

function Install-WithWinget {
    param([Parameter(Mandatory = $true)][string]$Id)
    Invoke-Native -FilePath 'winget' -OkCodes $wingetOk -Arguments @(
        'install', '--id', $Id, '--exact', '--source', 'winget',
        '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity'
    )
    Update-SessionPath
}

function Find-Code {
    $candidates = @(
        (Get-Command 'code' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source),
        (Join-Path $env:LOCALAPPDATA 'Programs\Microsoft VS Code\bin\code.cmd'),
        (Join-Path $env:ProgramFiles 'Microsoft VS Code\bin\code.cmd')
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    return $null
}

function Add-UserPathEntry {
    param([Parameter(Mandatory = $true)][string]$Entry)

    $currentPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ([string]::IsNullOrWhiteSpace($currentPath)) { $currentPath = '' }

    $entries = @($currentPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $alreadyExists = $entries | Where-Object { $_.TrimEnd('\') -ieq $Entry.TrimEnd('\') }

    if ($null -eq $alreadyExists) {
        [Environment]::SetEnvironmentVariable('Path', (($entries + $Entry) -join ';'), 'User')
        Write-Host "Adicionado ao PATH do usuário: $Entry" -ForegroundColor Green
    } else {
        Write-Host "O diretório já está no PATH: $Entry" -ForegroundColor DarkGray
    }
    Update-SessionPath
}

Write-Host '=== Instalação do ambiente C para VS Code ===' -ForegroundColor Cyan

if (-not (Test-CommandExists 'winget')) {
    throw 'O winget não foi encontrado. Instale/atualize o App Installer pela Microsoft Store e execute o script novamente.'
}

# VS Code
if (-not (Find-Code)) {
    Write-Host 'VS Code não encontrado. Instalando pelo winget...' -ForegroundColor Yellow
    Install-WithWinget -Id 'Microsoft.VisualStudioCode'
} else {
    Write-Host 'VS Code já instalado.' -ForegroundColor DarkGray
}

# MSYS2 (fornece o GCC nativo para Windows)
if (-not (Test-Path $bash)) {
    Write-Host 'Instalando MSYS2...' -ForegroundColor Yellow
    Install-WithWinget -Id 'MSYS2.MSYS2'
}
if (-not (Test-Path $bash)) {
    throw "MSYS2 não foi encontrado em $msysRoot. Instale-o manualmente (https://www.msys2.org) e execute novamente."
}

$env:MSYSTEM = 'UCRT64'
$env:CHERE_INVOKING = '1'

# Numa instalação nova, a 1ª atualização troca o núcleo e encerra com erro;
# a 2ª conclui a atualização.
Write-Host 'Atualizando os pacotes do MSYS2 (pode demorar)...' -ForegroundColor Yellow
Invoke-Native -FilePath $bash -Arguments @('-lc', 'pacman -Syu --noconfirm') -IgnoreFailure
Invoke-Native -FilePath $bash -Arguments @('-lc', 'pacman -Syu --noconfirm')

Write-Host 'Instalando GCC, GDB e Make...' -ForegroundColor Yellow
Invoke-Native -FilePath $bash -Arguments @('-lc', 'pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-gdb mingw-w64-ucrt-x86_64-make')

if (-not (Test-Path $gccExe)) {
    throw "O GCC não foi encontrado em $gccExe após a instalação."
}
Add-UserPathEntry -Entry $gccBin
Invoke-Native -FilePath $gccExe -Arguments @('--version')

# Extensões
$extensions = @(
    'ms-vscode.cpptools',
    'ms-vscode.cpptools-extension-pack',
    'ms-vscode.cmake-tools',
    'formulahendry.code-runner',
    'usernamehw.errorlens'
)

$code = Find-Code
if ($code) {
    Write-Host 'Instalando extensões do VS Code...' -ForegroundColor Yellow
    foreach ($extension in $extensions) {
        Invoke-Native -FilePath $code -Arguments @('--install-extension', $extension, '--force')
    }
} else {
    Write-Host 'O VS Code não foi encontrado; reabra o PowerShell e execute o script novamente para instalar as extensões.' -ForegroundColor Yellow
}

# Configurações do workspace. Se já existir settings.json, não sobrescreve.
$vscodeDir = Join-Path (Get-Location).Path '.vscode'
New-Item -ItemType Directory -Path $vscodeDir -Force | Out-Null
$settingsPath = Join-Path $vscodeDir 'settings.json'
if (Test-Path $settingsPath) {
    $settingsPath = Join-Path $vscodeDir 'settings.c-vscode.generated.json'
    Write-Host "settings.json já existe; a configuração foi salva separadamente em $settingsPath" -ForegroundColor Yellow
}

# Comando para o terminal PowerShell do VS Code (o PowerShell 5.1 não aceita '&&'
# e precisa de '&' para executar um caminho entre aspas).
$runner = "cd `$dir; & '$gccExe' `"`$fileName`" -Wall -Wextra -std=c17 -o `"`$fileNameWithoutExt.exe`"; if (`$?) { & `".\`$fileNameWithoutExt.exe`" }"

$settings = [ordered]@{
    'C_Cpp.default.compilerPath' = $gccExe
    'C_Cpp.default.cStandard' = 'c17'
    'C_Cpp.default.intelliSenseMode' = 'windows-gcc-x64'
    'code-runner.runInTerminal' = $true
    'code-runner.saveFileBeforeRun' = $true
    'code-runner.clearPreviousOutput' = $true
    'code-runner.executorMap' = [ordered]@{ 'c' = $runner }
    'terminal.integrated.defaultProfile.windows' = 'PowerShell'
    'files.associations' = [ordered]@{ '*.h' = 'c'; '*.c' = 'c' }
}
$json = $settings | ConvertTo-Json -Depth 10
# UTF-8 sem BOM (Set-Content -Encoding UTF8 do PowerShell 5.1 adiciona BOM).
[System.IO.File]::WriteAllText($settingsPath, $json, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ''
Write-Host 'Instalação concluída.' -ForegroundColor Green
Write-Host "Configuração criada em: $settingsPath"
Write-Host 'Feche e abra novamente o VS Code para ele reconhecer o GCC.' -ForegroundColor Yellow
Write-Host 'No VS Code, abra um arquivo .c e pressione Ctrl+Alt+N para usar o Code Runner.'
