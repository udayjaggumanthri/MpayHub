import logging
from typing import Any

from apps.notifications.providers.base import SendResult

logger = logging.getLogger(__name__)


class ConsoleAdapter:
    """Development fallback: log SMS payload instead of calling MSG91."""

    def send_template(
        self,
        phone_e164: str,
        template_id: str,
        variables: dict[str, Any],
        *,
        sender_id: str = '',
    ) -> SendResult:
        logger.info(
            '[SMS] phone=%s template=%s sender=%s vars=%s',
            phone_e164,
            template_id,
            sender_id,
            variables,
        )
        print(
            f'[SMS] phone={phone_e164} template={template_id} sender={sender_id} vars={variables}'
        )
        return SendResult(success=True, message_id='console')
