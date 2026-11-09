param([string]$PythonExecutable = 'python')
$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $desktopRoot 'app'
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
$version = (Get-Content -Raw -LiteralPath "$desktopRoot\VERSION").Trim()
if ($version -notmatch '^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$') { throw 'Invalid VERSION' }
$numericVersion = "$($Matches[1]).$($Matches[2]).$($Matches[3]).0"
$generatedDir = Join-Path $desktopRoot 'work\build'
New-Item -ItemType Directory -Force -Path $generatedDir | Out-Null
$versionSource = Join-Path $generatedDir 'VersionInfo.cs'
@"
using System.Reflection;
[assembly: AssemblyVersion("$numericVersion")]
[assembly: AssemblyFileVersion("$numericVersion")]
[assembly: AssemblyInformationalVersion("$version")]
"@ | Set-Content -LiteralPath $versionSource -Encoding UTF8
$manifest = (Get-Content -Raw -LiteralPath "$PSScriptRoot\app.manifest").Replace('version="2.0.0.0"', "version=`"$numericVersion`"")
$manifestPath = Join-Path $generatedDir 'app.manifest'
$manifest | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compiler /nologo /target:winexe /platform:x64 /optimize+ "/out:$appDir\ReportInterview.exe" "/win32manifest:$manifestPath" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll "$PSScriptRoot\Desktop.cs" $versionSource
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
