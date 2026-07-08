$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RootDir = $PSScriptRoot
$BackendDir = Join-Path $RootDir "server"
$FrontendDir = Join-Path $RootDir "web"
$BackendLogDir = Join-Path $BackendDir "logs"
$FrontendLogDir = Join-Path $FrontendDir "logs"

New-Item -ItemType Directory -Force -Path $BackendLogDir | Out-Null
New-Item -ItemType Directory -Force -Path $FrontendLogDir | Out-Null

function Resolve-CommandPath {
    param(
        [string[]]$Candidates,
        [string]$Fallback
    )

    foreach ($Candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($Candidate)) {
            continue
        }
        if (Test-Path -LiteralPath $Candidate) {
            return $Candidate
        }
        $Command = Get-Command $Candidate -ErrorAction SilentlyContinue
        if ($Command) {
            return $Command.Source
        }
    }
    return $Fallback
}

function Test-PortListening {
    param([int]$Port)
    $Connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return [bool]$Connection
}

function Start-Backend {
    if (Test-PortListening 8000) {
        Write-Host "Backend already running: http://127.0.0.1:8000"
        return
    }

    $Python = Resolve-CommandPath `
        -Candidates @(
            "python",
            "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
        ) `
        -Fallback "python"

    Start-Process `
        -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput (Join-Path $BackendLogDir "uvicorn.out.log") `
        -RedirectStandardError (Join-Path $BackendLogDir "uvicorn.err.log") `
        -WindowStyle Hidden

    Write-Host "Backend starting: http://127.0.0.1:8000"
}

function Start-Frontend {
    if (Test-PortListening 3000) {
        Write-Host "Frontend already running: http://127.0.0.1:3000"
        return
    }

    $Node = Resolve-CommandPath `
        -Candidates @(
            "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe",
            "node"
        ) `
        -Fallback "node"
    $ViteScript = Join-Path $FrontendDir "node_modules\vite\bin\vite.js"

    if (-not (Test-Path -LiteralPath $ViteScript)) {
        throw "Frontend dependency not found: $ViteScript. Please install dependencies in the web directory first."
    }

    Start-Process `
        -FilePath $Node `
        -ArgumentList @($ViteScript, "--host", "127.0.0.1", "--port", "3000") `
        -WorkingDirectory $FrontendDir `
        -RedirectStandardOutput (Join-Path $FrontendLogDir "vite.out.log") `
        -RedirectStandardError (Join-Path $FrontendLogDir "vite.err.log") `
        -WindowStyle Hidden

    Write-Host "Frontend starting: http://127.0.0.1:3000"
}

Start-Backend
Start-Frontend

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "Service URLs:"
Write-Host "Frontend: http://127.0.0.1:3000"
Write-Host "Backend docs: http://127.0.0.1:8000/docs"
