# Cloudflare DNS Custom Domain Automation

**Purpose:** When Phase 18's new-app provisioning needs to spin up a new Worker + attach it to a subdomain on `mtourk.com`, this runbook specifies exactly how to use the Cloudflare API to provision the DNS record programmatically.

**Authority:** ADR-007 §3 (new-app deploy automation, Cloudflare Custom Domain approach).

**Status:** Design reference; to be implemented as part of `factory/deploy/cloudflare_adapter.py` during Phase 18.

---

## Prerequisites

- Cloudflare account API token with **Zone DNS Edit** permission for `mtourk.com` (minimum required scope)
- The Cloudflare zone ID for `mtourk.com` (obtainable via API or dashboard)
- `wrangler.toml` configured with the target Cloudflare account ID
- The target Pages project or Worker domain (e.g., `dark-factory-intake.pages.dev`)

## Finding Your Zone ID

**Via Cloudflare Dashboard:**
1. Go to **mtourk.com** → **Settings** → **Zone Settings** (bottom of left sidebar)
2. Copy the **Zone ID** from the right-side "API" section
3. Store it; you'll need it for all API calls

**Via API (if you already have a token):**
```bash
curl -s https://api.cloudflare.com/client/v4/zones \
  -H "Authorization: Bearer $CF_API_TOKEN" | jq '.result[] | select(.name == "mtourk.com") | .id'
```

---

## Creating a CNAME Record (Generic Approach)

When the factory needs to assign a new subdomain to a Pages project or Worker, it creates a CNAME record pointing to the stable project domain.

**Request format:**
```bash
curl -X POST https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d {
    "type": "CNAME",
    "name": "{subdomain}",
    "content": "{target_domain}",
    "ttl": 3600,
    "proxied": true
  }
```

**Parameters:**
- `{zone_id}` — your mtourk.com zone ID from above
- `{subdomain}` — e.g., `factory` (will resolve to `factory.mtourk.com`)
- `{target_domain}` — e.g., `dark-factory-intake.pages.dev` (the stable Pages project domain, NOT a preview URL)
- `proxied: true` — lets Cloudflare manage SSL/TLS automatically (recommended)
- `ttl: 3600` — 1 hour TTL (Cloudflare ignores this when proxied=true, but include it for clarity)

**Response on success (HTTP 200):**
```json
{
  "success": true,
  "result": {
    "id": "372e67954025e0ba6aaa6d586b9e0b59",
    "zone_id": "023e105f4ecf77a3ca51217dbbe7afa1",
    "zone_name": "mtourk.com",
    "name": "factory.mtourk.com",
    "type": "CNAME",
    "content": "dark-factory-intake.pages.dev",
    "proxied": true,
    "ttl": 3600,
    "created_on": "2026-10-04T12:00:00Z",
    "modified_on": "2026-10-04T12:00:00Z"
  }
}
```

---

## ⚠️ Critical Rule: One Hostname, One Resource

**Learned the hard way during Phase 17.0 deployment** (see `docs/operations/INTAKE_DEPLOYMENT_PLAYBOOK.md` §2.5 for the full incident writeup) — a single hostname (e.g., `expense-tracker.mtourk.com`) can be assigned to **exactly one** Cloudflare resource: a Pages project OR a Worker, never both. Assigning it to a second resource **silently overrides** the first with no error — the domain just starts serving different content than expected, with no warning.

**Before provisioning any new app's subdomain, the runner must first determine the app's shape:**

| App shape | Hostname assignment |
|---|---|
| **Worker only** (no frontend, e.g. a pure API/bot) | `<slug>.mtourk.com` → Worker directly (the pattern in the example below is correct for this case) |
| **Pages + Worker** (frontend + backend API, e.g. the intake system itself) | `<slug>.mtourk.com` → **Pages** (frontend). Worker stays on its ambient `*.workers.dev` domain, or gets a **separate** hostname like `api-<slug>.mtourk.com` if a branded API URL matters. The frontend's own source code/config then points at whichever domain the Worker actually ended up on. |
| **Pages only** (static site, no backend) | `<slug>.mtourk.com` → Pages, no Worker DNS step at all |

**The runner must never attempt to assign the same hostname to two resources "just in case."** Decide the app's shape first (this is almost always knowable from the issue/profile — does it need a backend?), then provision exactly one DNS/custom-domain assignment per hostname.

---

## Example: Provisioning a New Feature App Subdomain (Phase 18 Use Case)

Scenario: A new GitHub issue arrives for a project called "expense-tracker", and it needs a Worker-only backend (no separate frontend — this example is the **Worker only** row above). Phase 18's runner:

1. Creates a new GitHub repo `expense-tracker` on the user's account
2. Deploys a Worker to `https://dark-factory-expense-tracker.developers.workers.dev` (wrangler auto-generates the stable domain)
3. Provisions the DNS record so `expense-tracker.mtourk.com` points to that Worker, with a Cloudflare Custom Domain configuration

**If this app instead needed a Pages frontend too** (the **Pages + Worker** row above), step 3 would attach `expense-tracker.mtourk.com` to the **Pages** project instead, and the Worker would either stay on its ambient domain or get `api-expense-tracker.mtourk.com` as a second, separate DNS record — never the same hostname as Pages.

**Pseudocode (Python, as would go in `factory/deploy/cloudflare_adapter.py`):**

```python
import os
import requests

class CloudflareDNSAdapter:
    def __init__(self, api_token: str, zone_id: str):
        self.api_token = api_token
        self.zone_id = zone_id
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def provision_subdomain(self, subdomain: str, target_domain: str) -> dict:
        """
        Create a CNAME record pointing subdomain to target_domain.
        
        Args:
            subdomain: e.g., "expense-tracker" (will become expense-tracker.mtourk.com)
            target_domain: e.g., "dark-factory-expense-tracker.pages.dev" or 
                          "dark-factory-expense-tracker.developers.workers.dev"
        
        Returns:
            dict with 'success' bool, 'record_id', 'full_domain', 'message'
        """
        payload = {
            "type": "CNAME",
            "name": subdomain,  # Cloudflare auto-appends .mtourk.com context
            "content": target_domain,
            "ttl": 3600,
            "proxied": True,  # Auto SSL/TLS
        }
        
        url = f"{self.base_url}/zones/{self.zone_id}/dns_records"
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if not result.get("success"):
                error_msg = result.get("errors", [{}])[0].get("message", "Unknown error")
                return {
                    "success": False,
                    "message": f"API error: {error_msg}",
                }
            
            record = result["result"]
            return {
                "success": True,
                "record_id": record["id"],
                "full_domain": record["name"],  # e.g., "factory.mtourk.com"
                "message": f"DNS record created: {record['name']} → {target_domain}",
            }
        
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"HTTP error: {str(e)}",
            }

# Usage (during Phase 18.2 deploy step):
adapter = CloudflareDNSAdapter(
    api_token=os.environ["CLOUDFLARE_API_TOKEN"],
    zone_id=os.environ["CLOUDFLARE_ZONE_ID"]
)

result = adapter.provision_subdomain(
    subdomain="expense-tracker",
    target_domain="dark-factory-expense-tracker.pages.dev"
)

if result["success"]:
    print(f"✅ {result['message']}")
    final_url = f"https://{result['full_domain']}"
else:
    print(f"❌ {result['message']}")
    raise RuntimeError(f"Failed to provision DNS: {result['message']}")
```

---

## Secrets: How to Store the API Token

**ADR-007 constraint:** The queue runner is a local process on the user's machine. It uses the ambient `wrangler login` session for Worker deploys (no new secret stored anywhere). But DNS provisioning also needs a credential.

**Decision:** The Cloudflare API token is stored as a **Cloudflare Worker environment secret**, the same way the Gemini key and GitHub PAT are (ADR-005, ADR-006). The local queue runner fetches it from the D1 database (or from a Worker endpoint that returns it in a header) at runtime, same as ADR-005's ephemeral-token pattern.

**Setup once (manual):**
```bash
wrangler secret put CLOUDFLARE_API_TOKEN
# Paste token when prompted
```

**Retrieval in Phase 18 code:**
```python
# The queue runner fetches the token from the Worker (same secure pattern as Gemini tokens)
response = requests.get(
    f"{WORKER_URL}/dns-provision-token",
    headers={"Authorization": f"Bearer {session_token}"}
)
cf_token = response.json()["token"]
```

---

## Error Handling

Common failures and how to handle them:

| Status | Error | Cause | Fix |
|--------|-------|-------|-----|
| 401 | Invalid API token | Token expired or revoked | Re-run `wrangler secret put CLOUDFLARE_API_TOKEN` |
| 403 | Permission denied | Token lacks Zone DNS Edit scope | Regenerate token on Cloudflare dashboard with correct permissions |
| 400 | Invalid zone ID | Zone ID doesn't exist or mismatched | Verify zone ID via dashboard Zone Settings |
| 409 | Record already exists | CNAME `subdomain` already exists on the zone | Delete the old record first or use a different subdomain |
| 429 | Rate limit | Too many requests in short time | Back off exponentially; Cloudflare allows ~100 req/min |
| 500 | Internal server error | Transient Cloudflare issue | Retry after 5 seconds |

**Retry strategy (Python):**
```python
import time
from requests.exceptions import HTTPError

def provision_with_retry(adapter, subdomain, target_domain, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = adapter.provision_subdomain(subdomain, target_domain)
            if result["success"]:
                return result
            
            # If API returned success=false, check if it's retryable
            if "Rate limit" in result["message"] or "500" in result["message"]:
                wait_time = (2 ** attempt)  # Exponential backoff: 1, 2, 4 seconds
                print(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                # Non-retryable error, fail immediately
                return result
        
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt)
                print(f"Exception: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
    
    return {"success": False, "message": "Max retries exceeded"}
```

---

## Verification

After creating a DNS record, verify it resolves correctly:

```bash
# Should resolve to the Pages/Worker IP within a few seconds
nslookup factory.mtourk.com

# Or via curl
curl -I https://factory.mtourk.com/
# Expected: HTTP 200, no CORS errors (if origin matches)
```

---

## Listing Existing Records (for debugging)

If you need to see all CNAME records on mtourk.com:

```bash
curl -s https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?type=CNAME \
  -H "Authorization: Bearer $CF_API_TOKEN" | jq '.result[] | {name, content, id}'
```

---

## Deleting a DNS Record (cleanup, if needed)

If a subdomain is no longer in use (e.g., a project was archived):

```bash
curl -X DELETE https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id} \
  -H "Authorization: Bearer $CF_API_TOKEN"
```

---

## References

- Cloudflare API docs: [DNS Records](https://developers.cloudflare.com/api/operations/dns-records-create-dns-record)
- Cloudflare Custom Domain: [Setup Guide](https://developers.cloudflare.com/pages/platform/custom-domains/)
- ADR-007: Autonomous Intake-to-Deploy Pipeline (context for why this automation is needed)

