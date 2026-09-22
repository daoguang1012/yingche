param(
    [ValidateSet('Menu','Beauty','All')][string]$Group = 'Menu',
    [switch]$CheckOnly,
    [string]$ModelDirectory = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $ModelDirectory) { $ModelDirectory = Join-Path $projectRoot 'models' }
$ModelDirectory = [System.IO.Path]::GetFullPath($ModelDirectory)
try {
    if ($Group -eq 'Menu') {
        Write-Host 'Yingche model setup / 映澈模型安装'
        Write-Host '1: 人脸追踪（约 4 MB）    2: 追踪及换脸（约 549 MB）    Q: 退出'
        Write-Host '换脸模型限非商业研究；条款和来源见 MODELS.md。'
        $choice = Read-Host '选择'
        if ($choice -eq '1') { $Group = 'Beauty' }
        elseif ($choice -eq '2') { $Group = 'All' }
        else { exit 0 }
    }
    $manifest = Get-Content -LiteralPath (Join-Path $projectRoot 'model-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $selected = @($manifest.models | Where-Object { $Group -eq 'All' -or $_.group -eq 'beauty' })
    if (-not $CheckOnly) { New-Item -ItemType Directory -Force -Path $ModelDirectory | Out-Null }
    $missing = @()
    foreach ($item in $selected) {
        if ($item.name -notmatch '^[a-zA-Z0-9_.-]+$' -or $item.url -notmatch '^https://') { throw 'Invalid manifest entry' }
        $target = Join-Path $ModelDirectory $item.name
        $valid = (Test-Path -LiteralPath $target -PathType Leaf) -and ((Get-Item -LiteralPath $target).Length -eq [long]$item.bytes)
        if ($valid) { $valid = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -eq $item.sha256 }
        if ($valid) { Write-Host ('OK ' + $item.name); continue }
        if ($CheckOnly) { $missing += $item.name; continue }
        Write-Host ('Downloading ' + $item.name)
        $part = $target + '.download'
        & curl.exe --location --fail --retry 3 --connect-timeout 30 --max-time 1800 --proto '=https' --proto-redir '=https' --output $part $item.url
        if ($LASTEXITCODE -ne 0) { throw ('Download failed: ' + $item.name) }
        if ((Get-Item -LiteralPath $part).Length -ne [long]$item.bytes) { throw ('Size mismatch: ' + $item.name) }
        if ((Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) { throw ('SHA256 mismatch: ' + $item.name) }
        Move-Item -LiteralPath $part -Destination $target -Force
        Write-Host ('Verified ' + $item.name)
    }
    if ($missing.Count -gt 0) { throw ('Missing or invalid: ' + ($missing -join ', ')) }
    Write-Host 'READY. Restart Yingche / 已就绪，请重新打开映澈。'
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'No unverified model was installed. Please retry or see MODELS.md.'
    exit 1
}
