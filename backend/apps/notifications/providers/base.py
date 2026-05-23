from typing import Any, Protocol


class SendResult:
    def __init__(self, *, success: bool, message_id: str = '', error: str = ''):
        self.success = success
        self.message_id = message_id
        self.error = error


class SmsProviderAdapter(Protocol):
    def send_template(
        self,
        phone_e164: str,
        template_id: str,
        variables: dict[str, Any],
        *,
        sender_id: str = '',
    ) -> SendResult:
        ...
