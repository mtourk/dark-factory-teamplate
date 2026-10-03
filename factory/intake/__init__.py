"""
Dark Factory Phase 17 — Multi-Channel Intake

Top-level package for feature intake: web, Telegram, email, WhatsApp.

Modules:
  - channels: RawIntakeMessage + ChannelAdapter interface (multi-channel normalization)
  - local_sync: Syncs pending profiles from Intake Worker to local profiles
  - worker/: Cloudflare Worker backend (mints tokens, creates repos, files issues)
  - web/: Static frontend (HTML/CSS/JS, deployed to Cloudflare Pages)
"""

__version__ = "0.1.0"
