"""
CLI entry point for post-deployment health/version validation (§15).

Invoked by `.factory/workflows/deploy.yml` inside GitHub Actions, after a
Wrangler deploy step, as:

    python -m factory.deploy.run_health_check \\
        --url <deployed-url> --expected-sha <sha> --target preview|production

Exits non-zero on failure so the workflow step (and therefore the
`factory/check-preview-smoke` / production health gate) fails cleanly.
Never reads or logs Cloudflare credentials -- this process only makes a
plain HTTPS GET to the already-deployed URL.
"""

import argparse
import json
import sys

from factory.deploy.cloudflare_adapter import CloudflareAdapter, redact_for_logging


def _http_get(url: str):
    """Thin wrapper so `requests` is only imported when this CLI actually runs."""
    import requests  # local import: keeps the adapter module dependency-free for unit tests

    return requests.get(url, timeout=30)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Factory Cloudflare deployment health check")
    parser.add_argument("--url", required=True, help="Deployed URL to validate")
    parser.add_argument("--expected-sha", required=True, help="Commit SHA expected to be live")
    parser.add_argument("--target", choices=["preview", "production"], required=True)
    args = parser.parse_args(argv)

    adapter = CloudflareAdapter(http_get=_http_get)

    try:
        result = adapter.run_health_check(args.url, expected_sha=args.expected_sha)
    except Exception as exc:  # noqa: BLE001 - surface as a clean CLI failure, not a traceback with secrets
        print(f"Health check errored: {redact_for_logging(str(exc))}", file=sys.stderr)
        return 2

    print(json.dumps({
        "target": args.target,
        "url": result.url,
        "healthy": result.healthy,
        "status_code": result.status_code,
        "version_matches": result.version_matches,
        "error": result.error,
    }, indent=2))

    return 0 if result.healthy else 1


if __name__ == "__main__":
    sys.exit(main())
