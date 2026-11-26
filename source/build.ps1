param([string]$PythonExecutable = 'python')
$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $desktopRoot 'app'
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
$version = (Get-Content -Raw -LiteralPath "$desktopRoot\VERSION").Trim()
if ($version -notmatch '^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$') { throw 'Invalid VERSION' }
$numericVersion = "$($Matches[1]).$($Matches[2]).$($Matches[3]).0"
$versionParts = $numericVersion.Split('.')
$versionTuple = $versionParts -join ", "
$productName = "Report Interview"
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
& $compiler /nologo /target:winexe /platform:x64 /optimize+ "/out:$appDir\ReportInterview.exe" "/win32manifest:$manifestPath" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll /reference:Microsoft.CSharp.dll "$PSScriptRoot\Desktop.cs" "$PSScriptRoot\LogicMatrix.cs" "$PSScriptRoot\PdfReview.cs" $versionSource
if ($LASTEXITCODE -ne 0) { throw 'Native interface compilation failed' }
Copy-Item -LiteralPath "$PSScriptRoot\ReportInterview.exe.config" -Destination $appDir
Copy-Item -LiteralPath "$desktopRoot\LICENSE" -Destination "$appDir\LICENSE.txt"
Copy-Item -LiteralPath "$desktopRoot\NOTICE.md" -Destination "$appDir\NOTICE.txt"
$engineResource = Join-Path "$PSScriptRoot\engine" 'report_version_windows_amd64.syso'
Push-Location "$PSScriptRoot\engine"
try {
    go test ./...
    if ($LASTEXITCODE -ne 0) { throw 'Engine tests failed' }
    go run github.com/tc-hib/go-winres@v0.3.3 simply --arch amd64 --manifest none --no-suffix --out $engineResource --product-name $productName --product-version $version --file-version $numericVersion --file-description 'Report Interview engine' --original-filename ReportEngine.exe
    if ($LASTEXITCODE -ne 0) { throw 'Engine version resource generation failed' }
    go build -trimpath -ldflags '-s -w' -o "$appDir\ReportEngine.exe" .
    if ($LASTEXITCODE -ne 0) { throw 'Engine build failed' }
} finally {
    Pop-Location
    if (Test-Path -LiteralPath $engineResource) { Remove-Item -LiteralPath $engineResource }
}
# Freeze the PDF helper so the review PC does not need a separate Python installation.
& $PythonExecutable -m pip install -r "$PSScriptRoot\pdf-build-requirements.txt"
if ($LASTEXITCODE -ne 0) { throw 'PDF helper build dependencies could not be installed' }
$pdfVersionResource = Join-Path $generatedDir 'pdf-version.txt'
@"
VSVersionInfo(
    ffi=FixedFileInfo(filevers=($versionTuple), prodvers=($versionTuple),
                      mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
    kids=[
        StringFileInfo([StringTable('040904B0', [
            StringStruct('FileDescription', 'Report Interview PDF helper'),
            StringStruct('FileVersion', '$numericVersion'),
            StringStruct('OriginalFilename', 'ReportPdf.exe'),
            StringStruct('ProductName', '$productName'),
            StringStruct('ProductVersion', '$version')
        ])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])])
    ]
)
"@ | Set-Content -LiteralPath $pdfVersionResource -Encoding Ascii
& $PythonExecutable -m PyInstaller --noconfirm --clean --onefile --console --name ReportPdf --version-file $pdfVersionResource --distpath $appDir --workpath "$generatedDir\pdf" --specpath $generatedDir "$PSScriptRoot\prepare_pdf.py"
if ($LASTEXITCODE -ne 0) { throw 'PDF helper build failed' }
foreach ($name in @('ReportInterview.exe', 'ReportEngine.exe', 'ReportPdf.exe')) {
    $info = [System.Diagnostics.FileVersionInfo]::GetVersionInfo((Join-Path $appDir $name))
    if ($info.ProductName -ne $productName -or $info.ProductVersion -ne $version -or
        $info.FileMajorPart -ne [int]($versionParts[0]) -or
        $info.FileMinorPart -ne [int]($versionParts[1]) -or
        $info.FileBuildPart -ne [int]($versionParts[2]) -or $info.FilePrivatePart -ne 0) {
        throw "Unexpected version information in ${name}: $($info.ProductName), $($info.ProductVersion), $($info.FileVersion)"
    }
}
& $PythonExecutable "$PSScriptRoot\test_prepare_pdf.py" --helper "$appDir\ReportPdf.exe"
if ($LASTEXITCODE -ne 0) { throw 'PDF preparation tests failed' }
& $PythonExecutable "$PSScriptRoot\pdf_notices.py" "$appDir\PDF-Third-Party-Notices.txt"
if ($LASTEXITCODE -ne 0) { throw 'PDF helper notices could not be built' }
# Python 3.11 with msilib is used only to build the installer, never at runtime.
& $PythonExecutable "$PSScriptRoot\build_msi.py"
if ($LASTEXITCODE -ne 0) { throw 'MSI build failed' }
