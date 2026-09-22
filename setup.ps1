$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$runtimePath = Join-Path $PSScriptRoot '.runtime'
New-Item -ItemType Directory -Force $runtimePath | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $runtimePath 'python.exe'))) {
    Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' -OutFile (Join-Path $runtimePath 'python.zip')
    Expand-Archive -LiteralPath (Join-Path $runtimePath 'python.zip') -DestinationPath $runtimePath -Force
}
@('python312.zip', '.', '..', 'import site') | Set-Content -LiteralPath (Join-Path $runtimePath 'python312._pth')
$pythonPath = Join-Path $runtimePath 'python.exe'
if (-not (Test-Path -LiteralPath (Join-Path $runtimePath 'Lib\site-packages\pip\__main__.py'))) {
    Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile (Join-Path $runtimePath 'get-pip.py')
    & $pythonPath (Join-Path $runtimePath 'get-pip.py') --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw 'Unable to bootstrap pip.' }
}
& $pythonPath -m pip --isolated install --ignore-installed --no-user --no-warn-script-location -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Ready. Double-click launch.bat to start Balance Lab.'
