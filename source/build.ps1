param([string]$PythonExecutable = 'python')
$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $desktopRoot 'app'
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compiler /nologo /target:winexe /platform:x64 /optimize+ "/out:$appDir\ReportInterview.exe" "/win32manifest:$PSScriptRoot\app.manifest" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll "$PSScriptRoot\Desktop.cs"
if ($LASTEXITCODE -ne 0) { throw 'Native interface compilation failed' }
Copy-Item -LiteralPath "$PSScriptRoot\ReportInterview.exe.config" -Destination $appDir
Copy-Item -LiteralPath "$desktopRoot\LICENSE" -Destination "$appDir\LICENSE.txt"
Copy-Item -LiteralPath "$desktopRoot\NOTICE.md" -Destination "$appDir\NOTICE.txt"
Push-Location "$PSScriptRoot\engine"
try {
    go test ./...
    if ($LASTEXITCODE -ne 0) { throw 'Engine tests failed' }
    go build -trimpath -ldflags '-s -w' -o "$appDir\ReportEngine.exe" .
    if ($LASTEXITCODE -ne 0) { throw 'Engine build failed' }
} finally { Pop-Location }
# Python 3.11 with msilib is used only to build the installer, never at runtime.
& $PythonExecutable "$PSScriptRoot\build_msi.py"
if ($LASTEXITCODE -ne 0) { throw 'MSI build failed' }
