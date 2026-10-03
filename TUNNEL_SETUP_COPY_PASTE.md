# Copy-Paste Values for Cloudflare Tunnel Setup

## Copy These Values Directly Into Cloudflare Dashboard

### Hostname (Copy this entire value):
```
factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com
```

### Service URL (Copy this entire value):
```
http://localhost:11434
```

### Description (Optional):
```
Local Ollama bridge
```

---

## How to Use in Cloudflare GUI

1. Go to: https://one.dash.cloudflare.com/
2. **Networks** → **Tunnels** → **factory-ollama-6393**
3. Click **Add a route** (or similar)
4. Choose **Private Hostname**
5. Paste into the **Hostname** field: `factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com`
6. Paste into the **Service URL** field (if it appears): `http://localhost:11434`
7. Fill in **Description** (optional): `Local Ollama bridge`
8. Click **Save**

---

## After Saving - Test Command

Open Git Bash or PowerShell and run:

```bash
curl.exe -k https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags
```

Should return JSON with your Ollama models (not 403 Forbidden).

---

## Additional Info

- **Tunnel ID:** `9bdef772-9e7c-495b-a295-6f542c35a1e9`
- **Account ID:** `a8e55d73ca21465429eca525015fae88`
- **Tunnel Token:** `eyJhIjoiYThlNTVkNzNjYTIxNDY1NDI5ZWNhNTI1MDE1ZmFlODgiLCJ0IjoiOWJkZWY3NzItOWU3Yy00OTViLWEyOTUtNmY1NDJjMzVhMWU5IiwicyI6IllXWmtNelprWXpndE5qazVOeTAwWkRVekxXRTBNelV0TXpnM05URXlZamd3T1RZd09HWXpNMk5pTkdFdFpHTXpPQzAwTjJGbExUZ3hNamd0T0RoaE9EbGhZak0xTW1SaCJ9`
