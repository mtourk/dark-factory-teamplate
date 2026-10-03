# Troubleshoot Private Hostname Creation Failure

## Step 1: Verify Tunnel is Still Running

Check if the `cloudflared tunnel run` process is still active.

**Is the tunnel terminal still showing output like:**
```
2026-10-03T15:23:45Z INF Registered tunnel connection connIndex=0 location=LAX
```

**If the tunnel window closed or shows "Connection lost", the tunnel is not running:**
- Go back to TUNNEL_SETUP.md Step 3
- Run the tunnel command again
- Keep it running in a separate terminal

---

## Step 2: Check Tunnel Connections via API

**Git Bash:**
```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
ACCOUNT_ID="a8e55d73ca21465429eca525015fae88"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

echo "=== Tunnel Status ==="
curl -s "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID" \
  -H "Authorization: Bearer $TOKEN" | grep -o '"status":"[^"]*'

echo ""
echo "=== Active Connections ==="
curl -s "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/connections" \
  -H "Authorization: Bearer $TOKEN" | grep -o '"is_pending":[^,}]*'

echo ""
```

**PowerShell:**
```powershell
$tunnelId = "9bdef772-9e7c-495b-a295-6f542c35a1e9"
$accountId = "a8e55d73ca21465429eca525015fae88"
$token = "cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

$headers = @{ "Authorization" = "Bearer $token" }

Write-Host "=== Tunnel Status ==="
$status = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId" `
    -Headers $headers -UseBasicParsing
Write-Host $status.Content

Write-Host ""
Write-Host "=== Active Connections ==="
$conn = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId/connections" `
    -Headers $headers -UseBasicParsing
Write-Host $conn.Content
```

**Look for:**
- `"status": "healthy"` or `"status": "ready"` ✓
- `"is_pending": false` and a connection listed ✓

If you see `"status": "inactive"` or no connections listed ❌, **the tunnel is not running. Restart it.**

---

## Step 3: Try Different Hostname Format

The **Hostname** field might expect:
- **Option A:** Just the subdomain: `factory-ollama-6393`
- **Option B:** The full cloudflareaccess.com domain: `factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com`
- **Option C:** Auto-select from a dropdown (don't type, click dropdown)

**Try each approach:**

1. Go back to add route in Cloudflare dashboard
2. Choose **Private Hostname** again
3. Try **Option A first:** Type only `factory-ollama-6393` in Hostname field
4. If Service URL field appears, use: `http://localhost:11434`
5. Click Save

If that fails, try **Option B** (full hostname), then **Option C** (if there's a dropdown).

---

## Step 4: Alternative - Use Cloudflare CLI Instead

If the GUI keeps failing, try creating the route via `cloudflared` CLI:

**Git Bash:**
```bash
/c/Tools/cloudflared/cloudflared.exe tunnel route dns \
  9bdef772-9e7c-495b-a295-6f542c35a1e9 \
  factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com
```

**PowerShell:**
```powershell
C:\Tools\cloudflared\cloudflared.exe tunnel route dns `
  9bdef772-9e7c-495b-a295-6f542c35a1e9 `
  factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com
```

This creates the route via CLI instead of the GUI.

---

## Debugging Info Needed

Run Step 2's diagnostic commands and **paste the output here** so I can see:
- Is the tunnel actually "healthy" and connected?
- Or is it showing as "inactive" or no connections?

That will tell us if the tunnel is the problem, or if it's just the route creation UI.
