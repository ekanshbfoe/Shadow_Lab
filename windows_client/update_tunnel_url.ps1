# update_tunnel_url.ps1
# Automates the sync of ephemeral Cloudflare URLs across Windows configs

# Ensure the parent directory for the local sync file exists
$GoogleDriveSyncDir = "$env:USERPROFILE\Google Drive\shadowlab"
if (-not (Test-Path $GoogleDriveSyncDir)) {
    Write-Host "Creating local sync directory: $GoogleDriveSyncDir"
    New-Item -ItemType Directory -Force -Path $GoogleDriveSyncDir | Out-Null
}

$TunnelUrlSource = "$GoogleDriveSyncDir\tunnel_url.txt"

if (-not (Test-Path $TunnelUrlSource)) {
    Write-Error "Tunnel URL source file not found at $TunnelUrlSource. Ensure Colab has written the URL and Google Drive has synced."
    exit 1
}

$NewUrl = (Get-Content $TunnelUrlSource -Raw).Trim()
if (-not ($NewUrl -match "^https://.*\.trycloudflare\.com$")) {
    Write-Error "Invalid tunnel URL: $NewUrl"
    exit 1
}

Write-Host "Updating configs to: $NewUrl"

# 1. Update Claude Desktop 3P config
$ClaudeConfigPath = "$env:LOCALAPPDATA\Claude-3p\claude_desktop_config.json"
if (Test-Path $ClaudeConfigPath) {
    $config = Get-Content $ClaudeConfigPath | ConvertFrom-Json
    $config.inferenceGatewayBaseUrl = $NewUrl
    $config | ConvertTo-Json -Depth 10 | Set-Content $ClaudeConfigPath
    Write-Host "  ✅ Claude Desktop config updated"
} else {
    Write-Warning "  ⚠️ Claude Desktop config not found at $ClaudeConfigPath"
}

# 2. Update configLibrary profile
$ProfilePath = "$env:LOCALAPPDATA\Claude-3p\configLibrary\00000000-0000-4000-8000-000000000001.json"
if (Test-Path $ProfilePath) {
    $profileData = Get-Content $ProfilePath | ConvertFrom-Json
    $profileData.inferenceGatewayBaseUrl = $NewUrl
    $profileData | ConvertTo-Json -Depth 10 | Set-Content $ProfilePath
    Write-Host "  ✅ Claude Desktop profile updated"
} else {
    Write-Warning "  ⚠️ Claude Desktop profile not found at $ProfilePath"
}

# 3. Update Claude Code settings
$ClaudeCodeSettings = "$env:USERPROFILE\.claude\settings.json"
if (Test-Path $ClaudeCodeSettings) {
    $settings = Get-Content $ClaudeCodeSettings | ConvertFrom-Json
    $settings.env.ANTHROPIC_BASE_URL = $NewUrl
    $settings | ConvertTo-Json -Depth 10 | Set-Content $ClaudeCodeSettings
    Write-Host "  ✅ Claude Code settings updated"
} else {
    Write-Warning "  ⚠️ Claude Code settings not found at $ClaudeCodeSettings"
}

# 4. Update current session env var
$env:ANTHROPIC_BASE_URL = $NewUrl
Write-Host "  ✅ Session environment updated"

# 5. Remind about Cline & Open WebUI
Write-Host ""
Write-Host "⚠️  Manually update in:"
Write-Host "    - Cline (VS Code): Settings → cline.openAiBaseUrl → $NewUrl/v1"
Write-Host "    - Open WebUI: Admin → Connections → API Base URL → $NewUrl/v1"
Write-Host ""
Write-Host "🔄 Restart Claude Desktop (quit from system tray, relaunch)."
