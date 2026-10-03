# Cloudflare Tunnel Setup for Ollama - Complete Copy-Paste Commands

## Tunnel Details

- **Tunnel Name:** factory-ollama-6393
- **Tunnel ID:** 9bdef772-9e7c-495b-a295-6f542c35a1e9
- **Tunnel Token:** `eyJhIjoiYThlNTVkNzNjYTIxNDY1NDI5ZWNhNTI1MDE1ZmFlODgiLCJ0IjoiOWJkZWY3NzItOWU3Yy00OTViLWEyOTUtNmY1NDJjMzVhMWU5IiwicyI6IllXWmtNelprWXpndE5qazVOeTAwWkRVekxXRTBNelV0TXpnM05URXlZamd3T1RZd09HWXpNMk5pTkdFdFpHTXpPQzAwTjJGbExUZ3hNamd0T0RoaE9EbGhZak0xTW1SaCJ9`
- **cloudflared location:** `C:\Tools\cloudflared\cloudflared.exe`

---

## STEP 1: Create Tunnel Configuration File

**In Git Bash or PowerShell, run this to create the config file:**

### Git Bash:
```bash
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: 9bdef772-9e7c-495b-a295-6f542c35a1e9
credentials-file: ~/.cloudflared/9bdef772-9e7c-495b-a295-6f542c35a1e9.json
ingress:
  - hostname: factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com
    service: http://localhost:11434
  - service: http_status:404
EOF
cat ~/.cloudflared/config.yml
```

### PowerShell:
```powershell
$configDir = "$env:USERPROFILE\.cloudflared"
New-Item -ItemType Directory -Path $configDir -Force | Out-Null

$configContent = @"
tunnel: 9bdef772-9e7c-495b-a295-6f542c35a1e9
credentials-file: ~/.cloudflared/9bdef772-9e7c-495b-a295-6f542c35a1e9.json
ingress:
  - hostname: factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com
    service: http://localhost:11434
  - service: http_status:404
"@

$configContent | Out-File -FilePath "$configDir\config.yml" -Encoding UTF8
Write-Host "Config file created at: $configDir\config.yml"
Get-Content "$configDir\config.yml"
```

---

## STEP 2: Create Credentials File

**In Git Bash or PowerShell, run this to create the credentials file:**

### Git Bash:
```bash
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/9bdef772-9e7c-495b-a295-6f542c35a1e9.json << 'EOF'
{
  "AccountTag": "a8e55d73ca21465429eca525015fae88",
  "TunnelID": "9bdef772-9e7c-495b-a295-6f542c35a1e9",
  "TunnelName": "factory-ollama-6393",
  "TunnelSecret": "YWZkNzZkYzg0NTk0OZUzLWE0MzU3ZWE1MjVhZWU5NGE4YzMyNGNiNGE0OTY4NDZhNDM0MzgzZmJlZjc0MmFlMDhiODlhYjM1Mm1kh"
}
EOF
cat ~/.cloudflared/9bdef772-9e7c-495b-a295-6f542c35a1e9.json
```

### PowerShell:
```powershell
$configDir = "$env:USERPROFILE\.cloudflared"
$credentialsContent = @"
{
  "AccountTag": "a8e55d73ca21465429eca525015fae88",
  "TunnelID": "9bdef772-9e7c-495b-a295-6f542c35a1e9",
  "TunnelName": "factory-ollama-6393",
  "TunnelSecret": "YWZkNzZkYzg0NTk0OZUzLWE0MzU3ZWE1MjVhZWU5NGE4YzMyNGNiNGE0OTY4NDZhNDM0MzgzZmJlZjc0MmFlMDhiODlhYjM1Mm1kh"
}
"@

$credentialsContent | Out-File -FilePath "$configDir\9bdef772-9e7c-495b-a295-6f542c35a1e9.json" -Encoding UTF8
Write-Host "Credentials file created at: $configDir\9bdef772-9e7c-495b-a295-6f542c35a1e9.json"
Get-Content "$configDir\9bdef772-9e7c-495b-a295-6f542c35a1e9.json"
```

---

## STEP 3: Start the Tunnel

**Use ONE of these commands to start the tunnel:**

### Option 3a: Git Bash (Full Path)
```bash
/c/Tools/cloudflared/cloudflared.exe tunnel run --config ~/.cloudflared/config.yml
```

### Option 3b: PowerShell (Full Path)
```powershell
& "C:\Tools\cloudflared\cloudflared.exe" tunnel run --config "$env:USERPROFILE\.cloudflared\config.yml"
```

### Option 3c: PowerShell (Simpler)
```powershell
C:\Tools\cloudflared\cloudflared.exe tunnel run --config $env:USERPROFILE\.cloudflared\config.yml
```

### Option 3d: Using Token Directly (Git Bash)
```bash
/c/Tools/cloudflared/cloudflared.exe tunnel run --token eyJhIjoiYThlNTVkNzNjYTIxNDY1NDI5ZWNhNTI1MDE1ZmFlODgiLCJ0IjoiOWJkZWY3NzItOWU3Yy00OTViLWEyOTUtNmY1NDJjMzVhMWU5IiwicyI6IllXWmtNelprWXpndE5qazVOeTAwWkRVekxXRTBNelV0TXpnM05URXlZamd3T1RZd09HWXpNMk5pTkdFdFpHTXpPQzAwTjJGbExUZ3hNamd0T0RoaE9EbGhZak0xTW1SaCJ9
```

### Option 3e: Using Token Directly (PowerShell)
```powershell
C:\Tools\cloudflared\cloudflared.exe tunnel run --token eyJhIjoiYThlNTVkNzNjYTIxNDY1NDI5ZWNhNTI1MDE1ZmFlODgiLCJ0IjoiOWJkZWY3NzItOWU3Yy00OTViLWEyOTUtNmY1NDJjMzVhMWU5IiwicyI6IllXWmtNelprWXpndE5qazVOeTAwWkRVekxXRTBNelV0TXpnM05URXlZamd3T1RZd09HWXpNMk5pTkdFdFpHTXpPQzAwTjJGbExUZ3hNamd0T0RoaE9EbGhZak0xTW1SaCJ9
```

**After you run one of these, you should see output like:**
```
Registered tunnel connection connIndex=0 location=LAX
Connection established
```

**LEAVE THIS RUNNING.** Do not close this window.

---

## STEP 4: Test the Tunnel (Open a NEW Terminal Window)

Keep the tunnel running from Step 3. Open a new Git Bash or PowerShell window and try these test commands **one at a time**:

### Test 4a: Git Bash - curl with insecure flag
```bash
curl -k https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags
```

### Test 4b: Git Bash - curl without flags
```bash
curl https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags
```

### Test 4c: PowerShell - Invoke-WebRequest with SkipCertificateCheck
```powershell
Invoke-WebRequest -Uri "https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags" -SkipCertificateCheck
```

### Test 4d: PowerShell - Invoke-WebRequest with SkipCertificateCheck and display content
```powershell
$response = Invoke-WebRequest -Uri "https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags" -SkipCertificateCheck
$response.Content
```

### Test 4e: PowerShell - Invoke-WebRequest with SkipCertificateCheck and parse JSON
```powershell
$response = Invoke-WebRequest -Uri "https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags" -SkipCertificateCheck
$response.Content | ConvertFrom-Json
```

### Test 4f: PowerShell - curl.exe (native Windows curl)
```powershell
curl.exe -k https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags
```

### Test 4g: Local Test - No Tunnel (Baseline Check)
```bash
curl http://localhost:11434/api/tags
```

### Test 4h: Local Test - PowerShell (Baseline Check)
```powershell
Invoke-WebRequest -Uri "http://localhost:11434/api/tags"
```

---

## Expected Success Response

When a test works, you should see JSON output like:

```json
{
  "models": [
    {
      "name": "qwen2.5-coder:32b",
      "model": "qwen2.5-coder:32b",
      "modified_at": "2026-10-03T15:52:15.5324831+02:00",
      "size": 19851349898,
      "digest": "b92d6a0bd47ee79114298de0177bf920c05a706d12633950b3936778492bef41",
      "details": {
        "parent_model": "",
        "format": "gguf",
        "family": "qwen2",
        "families": ["qwen2"],
        "parameter_size": "32.8B",
        "quantization_level": "Q4_K_M",
        "context_length": 32768,
        "embedding_length": 5120
      },
      "capabilities": ["completion", "tools", "insert"]
    }
  ]
}
```

**If you see this JSON output, the tunnel is working! ✓**

---

## Step 5: Stop the Tunnel

Press **Ctrl+C** in the window where the tunnel is running.

---

## Cleanup After Testing

Once confirmed working, revoke the temporary Cloudflare token:

### Git Bash:
```bash
curl -s -X DELETE "https://api.cloudflare.com/client/v4/tokens/cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70" \
  -H "Authorization: Bearer cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"
```

Or manually:
1. Go to: https://dash.cloudflare.com/?to=/:account/iam/api-tokens
2. Find and delete the token

---

## Troubleshooting

**If test 4g (local Ollama) works but tunnel tests fail:**
- Ollama is running ✓
- Tunnel might not be routing correctly
- Make sure config.yml was created in Step 1
- Make sure credentials file was created in Step 2
- Try restarting the tunnel from Step 3

**If tunnel shows "Connection established" but tests still fail:**
- Wait 10–15 seconds and try again (tunnel can take time to activate)
- The tunnel might need DNS propagation (Cloudflare might take a minute to activate)

**"Command not found" errors:**
- Make sure you're using Git Bash or PowerShell (not cmd.exe)
- Use the full path: `C:\Tools\cloudflared\cloudflared.exe`

**Certificate errors:**
- Use `-k` flag in curl
- Use `-SkipCertificateCheck` in PowerShell
