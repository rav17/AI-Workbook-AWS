"""Multi-channel communication service — SMS channel for R1, stubs for R2."""

import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

OPT_OUT_KEYWORDS = {"stop", "cancel", "unsubscribe", "quit", "end"}
OPT_OUT_FOOTER = "\nReply STOP to opt out."
PHONE_PATTERN = re.compile(r"^\+1\d{10}$")


class Channel(ABC):
    """Base class for communication channels."""

    @abstractmethod
    def send(self, recipient: str, message: str, **kwargs: Any) -> dict[str, Any]:
        ...

    @abstractmethod
    def validate_recipient(self, recipient: str) -> bool:
        ...


class SMSChannel(Channel):
    """SMS channel via AWS End User Messaging SMS (pinpoint-sms-voice-v2).

    In production, uses the send_text_message API.
    In dev/test, injected with MockSMSService which mimics the same interface.
    """

    def __init__(self, sms_client: Any, origination_identity: str = ""):
        self._sms = sms_client
        self._origination_identity = origination_identity
        self._tz = ZoneInfo("America/New_York")

    def send(self, recipient: str, message: str, **kwargs: Any) -> dict[str, Any]:
        include_opt_out = kwargs.get("include_opt_out", True)
        body = message + OPT_OUT_FOOTER if include_opt_out else message

        response = self._sms.send_text_message(
            DestinationPhoneNumber=recipient,
            MessageBody=body,
            MessageType="TRANSACTIONAL",
            OriginationIdentity=self._origination_identity,
        )
        return {
            "success": True,
            "message_id": response.get("MessageId", ""),
            "delivery_status": "SENT",
            "timestamp": datetime.now(self._tz).isoformat(),
        }

    def validate_recipient(self, recipient: str) -> bool:
        return bool(PHONE_PATTERN.match(recipient))


class CommunicationService:
    """Facade over channel implementations. R1 = SMS only."""

    def __init__(self, sms_channel: SMSChannel):
        self._sms = sms_channel

    def send_sms(
        self,
        phone_number: str,
        message: str,
        team_id: str,
        work_order_id: str,
        include_opt_out: bool = True,
    ) -> dict[str, Any]:
        if not self._sms.validate_recipient(phone_number):
            return {"success": False, "error": f"Invalid phone number: {phone_number}"}
        return self._sms.send(
            recipient=phone_number,
            message=message,
            include_opt_out=include_opt_out,
            team_id=team_id,
            work_order_id=work_order_id,
        )

    @staticmethod
    def check_opt_out_keyword(message: str) -> bool:
        return message.strip().lower() in OPT_OUT_KEYWORDS

    @staticmethod
    def validate_phone_number(phone: str) -> bool:
        return bool(PHONE_PATTERN.match(phone))
