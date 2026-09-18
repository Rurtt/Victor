<#
    Installs the pinned offline Thai speech runtime for Victor.

    Everything is verified against hard-coded SHA-256 values before it is used.
    Nothing here is downloaded at voice time; local_voice.py refuses to run
    unless runtime/voice-manifest.json still matches the files on disk.

    Run:  powershell -ExecutionPolicy Bypass -File scripts\install-voice.ps1
#>
[CmdletBinding()]
param([switch]$Force)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root       = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RuntimeDir = Join-Path $Root 'runtime\whisper'
$ModelDir   = Join-Path $Root 'models'
$Manifest   = Join-Path $Root 'runtime\voice-manifest.json'

# Pinned 2026-09-16. Change the tag and the hash together, never one alone.
$Binary = @{
    Url    = 'https://github.com/ggml-org/whisper.cpp/releases/download/b5130/whisper-bin-x64.zip'
    Sha256 = 'f9ec6c52a2e949b62ab51fa21d0d497958f9e41c3010c157c4e42932d5316f3c'
}
$Model = @{
    Url    = 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin'
    Sha256 = '1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b'
    Name   = 'ggml-small.bin'
}

function Get-VerifiedDownload {
    param([string]$Url, [string]$Sha256, [string]$Destination)

    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing -MaximumRedirection 5
    $actual = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Sha256.ToLowerInvariant()) {
        Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
        throw "Checksum mismatch for $Url`n  expected $Sha256`n  actual   $actual`nThe file was deleted. Do not retry with a different hash unless you verified the release yourself."
    }
    Write-Host "  SHA-256 verified."
}

if ((Test-Path $Manifest) -and -not $Force) {
    Write-Host "Voice runtime already installed. Re-run with -Force to reinstall."
    exit 0
}

$stage = Join-Path ([IO.Path]::GetTempPath()) ("victor-voice-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage -Force | Out-Null
try {
    # --- whisper.cpp CPU binaries -------------------------------------------
    $zip = Join-Path $stage 'whisper.zip'
    Get-VerifiedDownload -Url $Binary.Url -Sha256 $Binary.Sha256 -Destination $zip
    $unpacked = Join-Path $stage 'unpacked'
    Expand-Archive -LiteralPath $zip -DestinationPath $unpacked -Force

    $cli = Get-ChildItem -LiteralPath $unpacked -Recurse -Filter 'whisper-cli.exe' | Select-Object -First 1
    if (-not $cli) { throw "whisper-cli.exe was not found inside the release archive." }

    if (Test-Path $RuntimeDir) { Remove-Item -LiteralPath $RuntimeDir -Recurse -Force }
    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
    # Copy the CLI plus only the libraries that ship beside it; nothing else.
    Get-ChildItem -LiteralPath $cli.DirectoryName -File |
        Where-Object { $_.Extension -in '.exe', '.dll' } |
        Copy-Item -Destination $RuntimeDir -Force
    Write-Host "Installed $( (Get-ChildItem -LiteralPath $RuntimeDir -File).Count ) runtime files."

    # --- Thai-capable Whisper model -----------------------------------------
    New-Item -ItemType Directory -Path $ModelDir -Force | Out-Null
    $modelPath = Join-Path $ModelDir $Model.Name
    if ($Force -or -not (Test-Path $modelPath) -or
        (Get-FileHash -LiteralPath $modelPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Model.Sha256) {
        $staged = Join-Path $stage $Model.Name
        Get-VerifiedDownload -Url $Model.Url -Sha256 $Model.Sha256 -Destination $staged
        Move-Item -LiteralPath $staged -Destination $modelPath -Force
    } else {
        Write-Host "Model already present and verified."
    }

    # --- Manifest local_voice.py checks on every transcription ---------------
    $files = [ordered]@{}
    foreach ($file in @(Get-ChildItem -LiteralPath $RuntimeDir -File) + @(Get-Item -LiteralPath $modelPath)) {
        $relative = $file.FullName.Substring($Root.Length).TrimStart('\', '/').Replace('\', '/')
        $files[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    New-Item -ItemType Directory -Path (Split-Path $Manifest) -Force | Out-Null
    [IO.File]::WriteAllText(
        $Manifest,
        (@{ pinned = 'whisper.cpp b5130 + ggml-small'; files = $files } | ConvertTo-Json -Depth 4),
        (New-Object Text.UTF8Encoding($false)))

    Write-Host ""
    Write-Host "Offline Thai speech is installed. $($files.Count) files pinned in runtime\voice-manifest.json"
}
finally {
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
}
