param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8000,
    [switch]$Docker
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if ($Docker) {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            throw 'Docker is not installed. Install and start Docker Desktop, or run without -Docker.'
        }
        $taskPreviousPort = $env:APP_PORT
        try {
            $env:APP_PORT = "$Port"
            & docker compose config --quiet
            if ($LASTEXITCODE -ne 0) { throw 'Compose configuration failed. Check REVIEW_API_KEY in .env.' }
            & docker compose up --build --detach --wait
            if ($LASTEXITCODE -ne 0) { throw 'Container startup failed. Run docker compose logs api.' }
            Write-Host "Swagger: http://127.0.0.1:$Port/docs"
        }
        finally { $env:APP_PORT = $taskPreviousPort }
    }
    else {
        $taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $taskPython)) {
            throw 'Create .venv and install requirements.txt first. See README.md.'
        }
        & $taskPython -m scripts.local --port $Port
        if ($LASTEXITCODE -ne 0) { throw 'Local API exited with an error.' }
    }
}
finally { Pop-Location }
