# Fix Tunnel Routing with Your Own Domain (mtourk.com)

The issue: `*.cloudflareaccess.com` is Cloudflare's zone, not yours. Tunnel routing requires a DNS record in **your** zone.
The fix: Point `ollama.mtourk.com` → tunnel → `localhost:11434`.

---

## Step 1: Get Your Zone ID for mtourk.com

**Git Bash:**
```bash
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

echo "=== Fetching zone ID for mtourk.com ==="
ZONE_ID=$(curl -s "https://api.cloudflare.com/client/v4/zones?name=mtourk.com" \
  -H "Authorization: Bearer $TOKEN" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)

echo "Zone ID: $ZONE_ID"
```

**PowerShell:**
```powershell
$token = "cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"
$headers = @{ "Authorization" = "Bearer $token" }

Write-Host "=== Fetching zone ID for mtourk.com ==="
$zone = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/zones?name=mtourk.com" `
    -Headers $headers -UseBasicParsing | ConvertFrom-Json

$zoneId = $zone.result[0].id
Write-Host "Zone ID: $zoneId"
```

**Copy the Zone ID value — you'll need it for the next step.**

---

## Step 2: Create CNAME Record (ollama.mtourk.com → tunnel)

Replace `ZONE_ID_HERE` with the value from Step 1.

**Git Bash:**
```bash
ZONE_ID="ZONE_ID_HERE"  # Paste the zone ID from Step 1
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

echo "=== Creating CNAME record: ollama.mtourk.com → tunnel ==="
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "CNAME",
    "name": "ollama",
    "content": "'$TUNNEL_ID'.cfargotunnel.com",
    "ttl": 3600,
    "proxied": true
  }' | tee /tmp/cname.json

echo ""
echo "=== Verify it was created (look for \"success\":true above) ==="
```

**PowerShell:**
```powershell
$zoneId = "ZONE_ID_HERE"  # Paste the zone ID from Step 1
$tunnelId = "9bdef772-9e7c-495b-a295-6f542c35a1e9"
$token = "cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

$body = @{
    type = "CNAME"
    name = "ollama"
    content = "$tunnelId.cfargotunnel.com"
    ttl = 3600
    proxied = $true
} | ConvertTo-Json

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

Write-Host "=== Creating CNAME record: ollama.mtourk.com → tunnel ==="
$result = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/zones/$zoneId/dns_records" `
    -Method POST `
    -Headers $headers `
    -Body $body `
    -UseBasicParsing

Write-Host $result.Content
Write-Host ""
Write-Host "=== Verify it was created (look for ""success"":true above) ==="
```

---

## Step 3: Update Tunnel Ingress Config to Use Your Domain

**Git Bash:**
```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
ACCOUNT_ID="a8e55d73ca21465429eca525015fae88"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

echo "=== Updating tunnel config: ollama.mtourk.com → localhost:11434 ==="
curl -s -X PUT "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "ingress": [
        {
          "hostname": "ollama.mtourk.com",
          "service": "http://localhost:11434"
        },
        {
          "service": "http_status:404"
        }
      ]
    }
  }'

echo ""
echo "=== Done - look for \"success\":true above ==="
```

**PowerShell:**
```powershell
$tunnelId = "9bdef772-9e7c-495b-a295-6f542c35a1e9"
$accountId = "a8e55d73ca21465429eca525015fae88"
$token = "cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

$body = @{
    config = @{
        ingress = @(
            @{
                hostname = "ollama.mtourk.com"
                service = "http://localhost:11434"
            },
            @{
                service = "http_status:404"
            }
        )
    }
} | ConvertTo-Json -Depth 10

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

Write-Host "=== Updating tunnel config: ollama.mtourk.com → localhost:11434 ==="
$result = Invoke-WebRequest -Uri "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId/configurations" `
    -Method PUT `
    -Headers $headers `
    -Body $body `
    -UseBasicParsing

Write-Host $result.Content
Write-Host ""
Write-Host "=== Done - look for ""success"":true above ==="
```

---

## Step 4: Wait & Test

Wait 10-15 seconds for DNS propagation, then:

```bash
curl -k https://ollama.mtourk.com/api/tags
```

**This should return your Ollama models (JSON array), not 403.**

If it works: **✅ Tunnel is proven. Proceed to Phase 17.0 build.**

If still 403:
- Verify DNS propagated: `nslookup ollama.mtourk.com` (should resolve to a Cloudflare IP)
- Check tunnel is still running in its terminal window (look for active connections)
- Rerun Step 3 to confirm config is saved
- Try one more curl test

---

## After Confirming It Works

Run this to revoke the temporary token (keeping `cert.pem` for future tunnel management):

```bash
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"
curl -s -X DELETE "https://api.cloudflare.com/client/v4/accounts/a8e55d73ca21465429eca525015fae88/cfd_tunnel/9bdef772-9e7c-495b-a295-6f542c35a1e9/token" \
  -H "Authorization: Bearer $TOKEN"
```

(You can keep the tunnel itself running and connected — revoking the API token just means you can't create new routes/configs via this token anymore. The tunnel's credentials file stays intact.)

Then delete the local `TUNNEL_*.md` scratch files from your repo directory before any commit, so the token never gets accidentally committed to git.
