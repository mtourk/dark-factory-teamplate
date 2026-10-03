"""
Dark Factory Phase 17 — Intake Channel Adapter Interface

Defines the common RawIntakeMessage structure that all channels (web, Telegram, email, WhatsApp)
normalize their input into. This allows downstream processing (BMAD, filing, etc.) to be channel-agnostic.

Per master plan §17: "An item is channel-adapted into a RawIntakeMessage, then normalized
into a factory:ready GitHub Issue."

Phases:
  - 17.0: Web page (Pages + Worker)
  - 17.1: Telegram bot (long-polling)
  - 17.2: Email adapter (IMAP polling)
  - 17.3: WhatsApp (Cloud API webhook, via tunnel)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod


class Channel(str, Enum):
    """Supported intake channels."""
    WEB = "web"
    TELEGRAM = "telegram"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    UNKNOWN = "unknown"


class MessageType(str, Enum):
    """Type of content in the intake message."""
    TEXT = "text"
    VOICE = "voice"
    FILE = "file"
    AUDIO = "audio"
    MIXED = "mixed"


@dataclass
class RawIntakeMessage:
    """
    Normalized intake message, channel-agnostic.

    Every intake path (web, Telegram, email, WhatsApp) converts their
    native message format into this structure before any downstream processing.

    Fields:
        channel: which channel this came from (web, telegram, email, whatsapp)
        sender_id: opaque unique sender identifier (phone, email, GitHub user, etc.)
        sender_name: human-friendly sender name (optional)
        message_type: what kind of content (text, voice, file, etc.)
        text_content: the message body (if text-based)
        voice_transcript: if voice, the transcribed text (optional)
        attachments: list of file URIs or binary blobs (optional, for email/telegram)
        metadata: channel-specific metadata (e.g., Telegram chat_id, email message-id)
        timestamp: when the message was received
        raw_payload: the original, unmodified payload (for audit/debugging)
    """

    channel: Channel
    sender_id: str
    message_type: MessageType
    text_content: Optional[str] = None
    voice_transcript: Optional[str] = None
    attachments: List[str] = None  # URIs or file paths
    metadata: Dict[str, Any] = None
    timestamp: str = None
    sender_name: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate and normalize."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

        if self.attachments is None:
            self.attachments = []

        if self.metadata is None:
            self.metadata = {}

        # Coerce text from voice if available
        if not self.text_content and self.voice_transcript:
            self.text_content = self.voice_transcript

    @property
    def primary_content(self) -> str:
        """The main message content (text or voice transcript)."""
        return self.text_content or self.voice_transcript or ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage/API."""
        return {
            "channel": self.channel.value,
            "sender_id": self.sender_id,
            "message_type": self.message_type.value,
            "text_content": self.text_content,
            "voice_transcript": self.voice_transcript,
            "attachments": self.attachments,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "sender_name": self.sender_name,
        }


class ChannelAdapter(ABC):
    """
    Base class for channel adapters (web, Telegram, email, WhatsApp).

    Each adapter converts its native message format into RawIntakeMessage
    so downstream processing is channel-agnostic.
    """

    @abstractmethod
    async def normalize(self, raw_payload: Dict[str, Any]) -> RawIntakeMessage:
        """
        Convert a channel-specific message format into RawIntakeMessage.

        Args:
            raw_payload: the channel's native message dict

        Returns:
            RawIntakeMessage (normalized, ready for downstream processing)

        Raises:
            ValueError: if the payload cannot be normalized (e.g., missing required fields)
        """
        pass

    @abstractmethod
    def channel(self) -> Channel:
        """Identify which channel this adapter handles."""
        pass


class WebChannelAdapter(ChannelAdapter):
    """
    Adapter for web intake (Cloudflare Pages + Worker).

    Input: the Worker's /conversations endpoint structures (message, issue draft, etc.)
    Output: RawIntakeMessage for each user message
    """

    async def normalize(self, raw_payload: Dict[str, Any]) -> RawIntakeMessage:
        """
        Convert a web conversation message into RawIntakeMessage.

        Input schema:
        {
            "conversation_id": "...",
            "role": "user",
            "text": "I need a dashboard for tracking projects",
            "timestamp": "2026-10-03T..."
        }
        """
        if raw_payload.get("role") != "user":
            raise ValueError("Only user messages are intake; AI responses are internal")

        text = raw_payload.get("text", "").strip()
        if not text:
            raise ValueError("Message text is empty")

        return RawIntakeMessage(
            channel=Channel.WEB,
            sender_id=raw_payload.get("user_id", "web-user"),  # Placeholder; would be real user ID
            sender_name=raw_payload.get("user_name"),
            message_type=MessageType.TEXT,
            text_content=text,
            timestamp=raw_payload.get("timestamp"),
            metadata={
                "conversation_id": raw_payload.get("conversation_id"),
            },
            raw_payload=raw_payload,
        )

    def channel(self) -> Channel:
        return Channel.WEB


class TelegramChannelAdapter(ChannelAdapter):
    """
    Adapter for Telegram bot intake (Phase 17.1).

    Input: Telegram Bot API message object
    Output: RawIntakeMessage
    """

    async def normalize(self, raw_payload: Dict[str, Any]) -> RawIntakeMessage:
        """
        Convert a Telegram message into RawIntakeMessage.

        Input schema (Telegram message object):
        {
            "message_id": 123,
            "from": {"id": 456, "first_name": "Alice"},
            "chat": {"id": 789},
            "text": "Build a dashboard",
            "voice": {...},
            "date": 1234567890
        }
        """
        message = raw_payload.get("message", {})
        from_user = message.get("from", {})

        # Handle text
        text = message.get("text", "").strip()

        # Handle voice (if present, transcribe via Gemini)
        voice_transcript = None
        if "voice" in message:
            # In real implementation, download voice file and send to Gemini
            voice_transcript = message.get("voice_transcript")  # Placeholder

        if not text and not voice_transcript:
            raise ValueError("Message has no text or voice content")

        return RawIntakeMessage(
            channel=Channel.TELEGRAM,
            sender_id=str(from_user.get("id")),
            sender_name=from_user.get("first_name"),
            message_type=MessageType.VOICE if "voice" in message else MessageType.TEXT,
            text_content=text,
            voice_transcript=voice_transcript,
            timestamp=message.get("date"),
            metadata={
                "chat_id": str(message.get("chat", {}).get("id")),
                "message_id": message.get("message_id"),
            },
            raw_payload=raw_payload,
        )

    def channel(self) -> Channel:
        return Channel.TELEGRAM


class EmailChannelAdapter(ChannelAdapter):
    """
    Adapter for email intake (Phase 17.2).

    Input: parsed email message (from IMAP)
    Output: RawIntakeMessage
    """

    async def normalize(self, raw_payload: Dict[str, Any]) -> RawIntakeMessage:
        """
        Convert an email message into RawIntakeMessage.

        Input schema:
        {
            "uid": "1",
            "from": "alice@example.com",
            "subject": "New feature idea",
            "body": "We need a project dashboard",
            "date": "...",
            "attachments": [...]
        }
        """
        text = raw_payload.get("body", "").strip()
        if not text:
            raise ValueError("Email body is empty")

        return RawIntakeMessage(
            channel=Channel.EMAIL,
            sender_id=raw_payload.get("from", "unknown"),
            sender_name=raw_payload.get("from_name"),
            message_type=MessageType.FILE if raw_payload.get("attachments") else MessageType.TEXT,
            text_content=text,
            attachments=raw_payload.get("attachments", []),
            timestamp=raw_payload.get("date"),
            metadata={
                "uid": raw_payload.get("uid"),
                "subject": raw_payload.get("subject"),
                "message_id": raw_payload.get("message_id"),
            },
            raw_payload=raw_payload,
        )

    def channel(self) -> Channel:
        return Channel.EMAIL


# ============ Future: WhatsApp (Phase 17.3) ============

class WhatsAppChannelAdapter(ChannelAdapter):
    """
    Adapter for WhatsApp Cloud API intake (Phase 17.3).

    Input: WhatsApp Cloud API webhook message
    Output: RawIntakeMessage
    """

    async def normalize(self, raw_payload: Dict[str, Any]) -> RawIntakeMessage:
        """Placeholder for Phase 17.3 implementation."""
        raise NotImplementedError("WhatsApp adapter is planned for Phase 17.3")

    def channel(self) -> Channel:
        return Channel.WHATSAPP


# ============ Adapter Registry ============

ADAPTERS = {
    Channel.WEB: WebChannelAdapter(),
    Channel.TELEGRAM: TelegramChannelAdapter(),
    Channel.EMAIL: EmailChannelAdapter(),
    Channel.WHATSAPP: WhatsAppChannelAdapter(),
}


def get_adapter(channel: Channel) -> Optional[ChannelAdapter]:
    """Retrieve adapter for a given channel."""
    return ADAPTERS.get(channel)
