# Cloudflare Private Hostname Route - Simple Setup

## Two Fields for Private Hostname

If you only see **Hostname** and **Description**, fill them like this:

| Field | Value |
|-------|-------|
| **Hostname** | `factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com` |
| **Description** | `Local Ollama bridge` (optional — just for your notes) |

---

## Where to Find the Service URL Field

After you fill Hostname and Description, you should see **one of these:**

**Option A:** A third field appears: **Service URL**
- Set it to: `http://localhost:11434`
- Click Save

**Option B:** You click Save, then it asks for Service URL on a next screen
- Set it to: `http://localhost:11434`
- Click Save again

**Option C:** There's no explicit Service URL field shown
- This might mean the tunnel automatically routes to `localhost:11434` (sometimes Cloudflare pre-fills this if it's configured in your tunnel)
- Just click Save with Hostname + Description

---

## What to Do

1. Fill in:
   - **Hostname:** `factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com`
   - **Description:** `Local Ollama bridge` (or leave blank)

2. Click **Save** or **Next**

3. If it asks for Service URL:
   - Enter: `http://localhost:11434`
   - Click **Save**

4. Wait 10 seconds

5. Test:
   ```bash
   curl.exe -k https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags
   ```

Let me know what happens — if you see another field or error, paste the exact text shown.
