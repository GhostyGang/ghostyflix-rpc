param(
    [string]$Destination = (Join-Path $PSScriptRoot '..\dist\browser-companion')
)

$ErrorActionPreference = 'Stop'
$manifest = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') | ConvertFrom-Json
$packageName = "GhostyFlix-Browser-Companion-$($manifest.version)"
$null = New-Item -ItemType Directory -Force -Path $Destination
$zipPath = Join-Path $Destination "$packageName.zip"
$xpiPath = Join-Path $Destination "$packageName-unsigned.xpi"
$files = @(
    'manifest.json', 'background.js', 'content.js',
    'options.html', 'options.css', 'options.js', 'icon.png'
) | ForEach-Object { Join-Path $PSScriptRoot $_ }

Compress-Archive -Path $files -DestinationPath $zipPath -Force
Copy-Item -LiteralPath $zipPath -Destination $xpiPath -Force
Write-Output "Created Chromium/Opera package: $zipPath"
Write-Output "Created Firefox signing package (unsigned): $xpiPath"
