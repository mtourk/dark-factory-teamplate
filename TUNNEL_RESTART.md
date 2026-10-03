# Restart the Tunnel Connection

## The Problem

Tunnel status is "healthy" (configured correctly) but has **ZERO active connections**.
This means `cloudflared` is not currently running on your machine.

## Fix: Start cloudflared Again

**Open a NEW terminal (Git Bash) and run this, then LEAVE IT OPEN:**

```bash
/c/Tools/cloudflared/cloudflared.exe tunnel run --token eyJhIjoiYThlNTVkNzNjYTIxNDY1NDI5ZWNhNTI1MDE1ZmFlODgiLCJ0IjoiOWJkZWY3NzItOWU3Yy00OTViLWEyOTUtNmY1NDJjMzVhMWU5IiwicyI6IllXWmtNelprWXpndE5qazVOeTAwWkRVekxXRTBNelV0TXpnM05URXlZamd3T1RZd09HWXpNMk5pTkdFdFpHTXpPQzAwTjJGbExUZ3hNamd0T0RoaE9EbGhZak0xTW1SaCJ9
```

**Or in PowerShell (leave it open):**

```powershell
C:\Tools\cloudflared\cloudflared.exe tunnel run --token eyJhIjoiYThlNTVkNzNjYTIxNDY1NDI5ZWNhNTI1MDE1ZmFlODgiLCJ0IjoiOWJkZWY3NzItOWU3Yy00OTViLWEyOTUtNmY1NDJjMzVhMWU5IiwicyI6IllXWmtNelprWXpndE5qazVOeTAwWkRVekxXRTBNelV0TXpnM05URXlZamd3T1RZd09HWXpNMk5pTkdFdFpHTXpPQzAwTjJGbExUZ3hNamd0T0RoaE9EbGhZak0xTW1SaCJ9
```

## Watch For This Output

You should see:
```
2026-10-03T...Z INF Starting tunnel tunnelID=9bdef772-9e7c-495b-a295-6f542c35a1e9
2026-10-03T...Z INF Version 2026.9.3
2026-10-03T...Z INF Registered tunnel connection connIndex=0 ...
2026-10-03T...Z INF Registered tunnel connection connIndex=1 ...
```

**If you see "Registered tunnel connection" — the tunnel is now live.**

**Keep this terminal window open and visible. Do not close it, do not let your laptop sleep.**

---

## Verify Connection (in a DIFFERENT terminal, while tunnel is running)

```bash
TUNNEL_ID="9bdef772-9e7c-495b-a295-6f542c35a1e9"
ACCOUNT_ID="a8e55d73ca21465429eca525015fae88"
TOKEN="cfat_ZJSdt4K6N4AzSv8Xa6K1rI2I3192GITOb9m06r1J123e5a70"

echo "=== Active Connections (should NOT be empty now) ==="
curl -s "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/connections" \
  -H "Authorization: Bearer $TOKEN"
```

You should now see connection data (not empty).

---

## Then Test Again

In a third terminal (or reuse the verify one):

```bash
curl -k https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags
```

**Note:** Use the `-k` version (ignore cert) in Git Bash due to the Windows certificate revocation check issue (`CRYPT_E_REVOKED`) you saw. That's a separate, unrelated Windows/schannel quirk — not a tunnel problem. The `-k` flag bypasses it for testing purposes.

---

## Important: 3 Terminal Windows Needed

1. **Terminal 1:** Running `cloudflared tunnel run --token ...` (keep open, don't touch)
2. **Terminal 2:** For checking connection status
3. **Terminal 3:** For testing with curl

Make sure Terminal 1 stays running the whole time you're testing.
