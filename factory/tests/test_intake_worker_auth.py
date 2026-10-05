"""
FF-P03-01 (D-NEW-002, Option A): Cloudflare Access authentication for the
intake Worker.

The Worker (factory/intake/worker/src/index.ts) is real TypeScript, not a
Python port, so these tests build it with esbuild (same `npm run build` the
project already uses) and exercise the actual bundled code from a small Node
driver script (factory/tests/helpers/worker_auth_driver.mjs). That driver:

- signs a throwaway RSA keypair's JWTs to stand in for Cloudflare Access
- mocks the Access JWKS endpoint (`fetch` to <team>.cloudflareaccess.com)
- mocks the D1 binding just enough for handleCreateConversation()
- calls worker.fetch(request, env) directly and asserts on response status

This file is the pytest entry point: it shells out to `npm run build` to
produce a fresh factory/intake/worker/dist/index.js, then runs the Node
driver against it and asserts on the driver's exit code/output.

Skips (rather than fails) when Node.js or the Worker's npm dependencies
aren't available in the environment, since this suite exercises the
TypeScript Worker, not Python code.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

WORKER_DIR = Path(__file__).resolve().parents[2] / "factory" / "intake" / "worker"
DRIVER_SCRIPT = Path(__file__).resolve().parent / "helpers" / "worker_auth_driver.mjs"
DIST_INDEX = WORKER_DIR / "dist" / "index.js"


def _node_available() -> bool:
    return shutil.which("node") is not None


def _worker_deps_available() -> bool:
    return (WORKER_DIR / "node_modules").is_dir() and (WORKER_DIR / "src" / "index.ts").is_file()


pytestmark = pytest.mark.skipif(
    not _node_available() or not _worker_deps_available(),
    reason="Node.js and factory/intake/worker/node_modules (esbuild) are required to build/test the Worker",
)


@pytest.fixture(scope="module")
def built_worker() -> Path:
    """Build the Worker with esbuild (same bundling `npm run build` uses) and
    return the path to the bundled dist/index.js, so tests always exercise
    current source rather than a possibly-stale committed artifact.

    Invokes esbuild's own bin script via `node` directly (rather than
    `npm run build`) to avoid npm/shell indirection quirks across platforms.
    """
    esbuild_bin = WORKER_DIR / "node_modules" / "esbuild" / "bin" / "esbuild"
    assert esbuild_bin.is_file(), f"esbuild not found at {esbuild_bin} -- run `npm install` in {WORKER_DIR}"

    if DIST_INDEX.exists():
        DIST_INDEX.unlink()

    result = subprocess.run(
        [
            "node",
            str(esbuild_bin),
            "src/index.ts",
            "--bundle",
            "--platform=neutral",
            "--target=es2020",
            "--outfile=dist/index.js",
        ],
        cwd=str(WORKER_DIR),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"esbuild failed in {WORKER_DIR}:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert DIST_INDEX.is_file(), f"Expected build output at {DIST_INDEX}"
    return DIST_INDEX


@pytest.fixture(scope="module")
def driver_run(built_worker: Path) -> subprocess.CompletedProcess:
    """Run the Node auth driver once per module and share its result."""
    return subprocess.run(
        ["node", str(DRIVER_SCRIPT), str(built_worker)],
        capture_output=True,
        text=True,
    )


def test_driver_all_checks_pass(driver_run: subprocess.CompletedProcess):
    """All individual auth-gate assertions in the Node driver pass."""
    assert driver_run.returncode == 0, (
        f"Worker auth driver failed:\nstdout:\n{driver_run.stdout}\nstderr:\n{driver_run.stderr}"
    )
    assert "All" in driver_run.stdout and "checks passed" in driver_run.stdout


def test_missing_access_header_rejected(driver_run: subprocess.CompletedProcess):
    """POST /conversations with no Cf-Access-Jwt-Assertion header -> 401."""
    assert "PASS: POST /conversations with no Access header returns 401" in driver_run.stdout


def test_malformed_jwt_rejected(driver_run: subprocess.CompletedProcess):
    assert "PASS: POST /conversations with malformed Access header returns 401" in driver_run.stdout


def test_wrong_audience_rejected(driver_run: subprocess.CompletedProcess):
    assert "PASS: POST /conversations with wrong-audience JWT returns 401" in driver_run.stdout


def test_expired_jwt_rejected(driver_run: subprocess.CompletedProcess):
    assert "PASS: POST /conversations with expired JWT returns 401" in driver_run.stdout


def test_unknown_kid_rejected(driver_run: subprocess.CompletedProcess):
    assert "PASS: POST /conversations with unknown kid returns 401" in driver_run.stdout


def test_valid_access_jwt_allowed_through(driver_run: subprocess.CompletedProcess):
    """A valid, correctly-signed, correct-audience Access JWT reaches the handler (201)."""
    assert "PASS: POST /conversations with valid Access JWT is allowed through (201)" in driver_run.stdout


def test_version_route_is_public(driver_run: subprocess.CompletedProcess):
    """GET /version requires no Access header (health check stays open)."""
    assert "PASS: GET /version with no Access header is public (200)" in driver_run.stdout


def test_ollama_status_route_is_public(driver_run: subprocess.CompletedProcess):
    assert "PASS: GET /ollama/status with no Access header is public (not 401)" in driver_run.stdout


def test_fails_closed_when_aud_unconfigured(driver_run: subprocess.CompletedProcess):
    """If CLOUDFLARE_ACCESS_AUD isn't configured, mutating routes fail closed (401), not open."""
    assert "PASS: POST /conversations when CLOUDFLARE_ACCESS_AUD unset returns 401 (fails closed)" in driver_run.stdout


def test_phase03_01_gate_access_jwt_verification_operational(driver_run: subprocess.CompletedProcess):
    """
    FF-P03-01 Gate: Cloudflare Access JWT verification gates mutating Worker
    routes (D-NEW-002 Option A).

    Verifies:
    - Mutating routes (POST /conversations here, representative of /projects,
      /file-issue, /messages, /text-response which share the same gate) reject
      missing, malformed, wrong-audience, expired, and unknown-kid JWTs with 401.
    - A valid Access JWT (correct signature, kid, audience, not expired) is let
      through to the handler.
    - Read-only/health routes (/version, /ollama/status) stay public.
    - Missing CLOUDFLARE_ACCESS_AUD configuration fails closed, not open.
    """
    assert driver_run.returncode == 0, driver_run.stdout + driver_run.stderr

    output = driver_run.stdout
    required_passes = [
        "POST /conversations with no Access header returns 401",
        "POST /conversations with malformed Access header returns 401",
        "POST /conversations with wrong-audience JWT returns 401",
        "POST /conversations with expired JWT returns 401",
        "POST /conversations with unknown kid returns 401",
        "POST /conversations with valid Access JWT is allowed through (201)",
        "GET /version with no Access header is public (200)",
        "GET /ollama/status with no Access header is public (not 401)",
        "POST /conversations when CLOUDFLARE_ACCESS_AUD unset returns 401 (fails closed)",
    ]
    for check in required_passes:
        assert f"PASS: {check}" in output, f"Missing expected pass: {check}\nFull output:\n{output}"

    print(
        "✓ Phase 03-01 Gate: Cloudflare Access JWT verification gates mutating routes, "
        "fails closed without config, leaves health routes public."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
