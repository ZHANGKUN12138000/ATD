param(
    [string]$Destination = (Join-Path $env:USERPROFILE 'abaqus_plugins')
)

$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'abaqus_plugins'
if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw "Plugin source folder not found: $source"
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Copy-Item -LiteralPath (Join-Path $source 'ATD_plugin.py') -Destination $Destination -Force
Copy-Item -LiteralPath (Join-Path $source 'atd_gui.py') -Destination $Destination -Force
Copy-Item -LiteralPath (Join-Path $source 'atd_kernel.py') -Destination $Destination -Force
Copy-Item -LiteralPath (Join-Path $source 'atd') -Destination $Destination -Recurse -Force
Write-Host "ATD installed in $Destination"
Write-Host 'Restart Abaqus/CAE, then use Plug-ins > ATD - Abaqus to LS-DYNA.'
