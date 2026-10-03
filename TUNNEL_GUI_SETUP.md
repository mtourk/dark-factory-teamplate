# Configure Cloudflare Tunnel Route via Dashboard (GUI)

## The Issue: Domain & Service URL Errors

You're hitting two validation errors:

1. **Domain says:** "Enter a valid domain (e.g. example.com)"
2. **Service URL says:** "Invalid service URL format (must start with protocol like https://, tcp://, etc.)"

This suggests you're in a **Published Application** form that expects **real hostnames**, not localhost tunnels. That's not the right route type for us.

---

## The Real Problem: Wrong Route Type

Your tunnel (`factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com`) is a **Zero Trust / Cloudflare Access** tunnel, not a standard **Tunnel to a domain**.

For Access tunnels, you need a **different route type**.

---

## Step 1: Go Back and Choose the RIGHT Option

1. In Cloudflare dashboard: **Networks** → **Tunnels** → **factory-ollama-6393**
2. Go to the **Routes** or **Public Hostnames** tab
3. When you see the 4 options:
   - **Published Application** ❌ (this is what you tried — needs a real domain)
   - **Private Hostname** ✅ **SELECT THIS ONE**
   - Private CIDR ❌
   - Workers VPC ❌

**Choose "Private Hostname"** (even though it says "private", it works for Access tunnels)

---

## Step 2: Fill in Private Hostname Form

When you select "Private Hostname", you should see fields like:

```
Public hostname: factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com
Service: http://localhost:11434
```

Or simpler:

```
Hostname: [use the existing cloudflareaccess.com domain from dropdown]
Service URL: http://localhost:11434
```

If it asks:

- **Hostname/Domain:** Pick the dropdown option that shows `cloudflareaccess.com` or `*.cloudflareaccess.com`
- **Service URL:** `http://localhost:11434`
- **Path:** Leave blank

---

## Step 3: Save and Test

After saving, test with:

```bash
curl.exe -k https://factory-ollama-6393.174d2c93ae6f1a6de076789dd62be162.cloudflareaccess.com/api/tags
```

Should return JSON with your models.

---

## If You Still See Different Fields

Paste a screenshot or describe exactly what fields you see when you click "Private Hostname". The UI might vary depending on your account tier or Cloudflare version.

Or tell me:
- What options appear in the Domain/Hostname dropdown?
- What other fields are shown?

We'll adjust from there.
