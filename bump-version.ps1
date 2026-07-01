param(
    [Parameter(Mandatory = $true)][string]$Version
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Replace-InFile {
    param([string]$Path, [string]$Pattern, [string]$Replacement)
    $content = Get-Content -Path $Path -Raw -Encoding utf8
    $updated = [regex]::Replace($content, $Pattern, $Replacement)
    if ($updated -ne $content) {
        # Set-Content -Encoding utf8 writes a BOM in Windows PowerShell 5.1,
        # which serde_json (Tauri's Rust JSON parser) chokes on for
        # tauri.conf.json - write raw bytes instead to keep it BOM-less.
        [System.IO.File]::WriteAllText($Path, $updated, $Utf8NoBom)
        Write-Host "  Updated $(Resolve-Path -Relative $Path)"
    }
}

Replace-InFile "$root\package.json" '"version":\s*"[0-9]+\.[0-9]+\.[0-9]+"' "`"version`": `"$Version`""
Replace-InFile "$root\src-tauri\tauri.conf.json" '"version":\s*"[0-9]+\.[0-9]+\.[0-9]+"' "`"version`": `"$Version`""
Replace-InFile "$root\sidecar\core\config.py" 'APP_VERSION = "[0-9]+\.[0-9]+\.[0-9]+"' "APP_VERSION = `"$Version`""
Replace-InFile "$root\src\components\Sidebar.tsx" 'v[0-9]+\.[0-9]+\.[0-9]+' "v$Version"
Replace-InFile "$root\src\tools\Settings.tsx" 'CHSuite v[0-9]+\.[0-9]+\.[0-9]+' "CHSuite v$Version"

Write-Host "Version set to $Version."
