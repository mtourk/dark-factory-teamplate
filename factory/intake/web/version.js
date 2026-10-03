/**
 * Version/Build Info
 *
 * Retrieves the current build version and deployment timestamp from the Worker.
 * Used by the footer to display: "Version 1 · 2026-10-04 12:34:56 UTC"
 */

let versionCache = null;
let versionCacheTime = 0;
const VERSION_CACHE_TTL = 60000; // 1 minute

async function getVersionInfo() {
  const now = Date.now();

  // Use cache if available and fresh
  if (versionCache && (now - versionCacheTime) < VERSION_CACHE_TTL) {
    return versionCache;
  }

  try {
    const response = await fetch(`${WORKER_URL}/version`);
    if (response.ok) {
      versionCache = await response.json();
      versionCacheTime = now;
      return versionCache;
    }
  } catch (error) {
    console.warn("Failed to fetch version info:", error);
  }

  // Fallback if endpoint fails
  return {
    version: "unknown",
    deployed_at: new Date().toISOString(),
  };
}

async function updateVersionFooter() {
  const versionInfo = await getVersionInfo();
  const versionElement = document.getElementById("version-info");

  if (versionElement && versionInfo) {
    const deployedTime = new Date(versionInfo.deployed_at);
    const formattedTime = deployedTime.toLocaleString("en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });

    versionElement.textContent = `Version ${versionInfo.version} · ${formattedTime} UTC`;
  }
}
