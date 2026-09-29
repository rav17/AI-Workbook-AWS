"""Email notifier with root cause analysis and approval link.

Sends HTML emails via Amazon SES with:
- Root cause analysis of the alert
- Proposed remediation action
- One-click approval link to trigger the agent
- Expiry notice (if not clicked, operator handles manually)
"""

import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.approval_handler import ApprovalHandler, PendingApproval

logger = logging.getLogger(__name__)

SES_FROM_ADDRESS = os.environ.get("SES_FROM_ADDRESS", "aiops@example.com")
OPERATOR_EMAIL = os.environ.get("OPERATOR_EMAIL", "ops-team@example.com")


def build_rca_email(approval: PendingApproval, approval_link: str) -> dict:
    """Build the HTML email body with root cause and approval link.

    Returns:
        Dict with 'subject', 'html_body', and 'text_body'.
    """
    severity_color = {
        "P1": "#dc3545",  # red
        "critical": "#dc3545",
        "P2": "#fd7e14",  # orange
        "warning": "#fd7e14",
        "P3": "#ffc107",  # yellow
        "info": "#17a2b8",  # blue
    }.get(approval.severity, "#6c757d")

    subject = (
        f"[{approval.severity.upper()}] {approval.alert_name} on "
        f"{approval.affected_host} — Action Required"
    )

    html_body = f"""\
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">

<div style="border-left: 4px solid {severity_color}; padding: 12px 16px; background: #f8f9fa; margin-bottom: 20px;">
    <h2 style="margin: 0 0 8px 0; color: #212529;">
        🚨 Alert: {approval.alert_name}
    </h2>
    <p style="margin: 0; color: #495057; font-size: 14px;">
        Severity: <strong style="color: {severity_color};">{approval.severity.upper()}</strong>
        &nbsp;|&nbsp; Host: <strong>{approval.affected_host}</strong>
        &nbsp;|&nbsp; Service: <strong>{approval.service_name}</strong>
    </p>
</div>

<h3 style="color: #212529;">📋 Root Cause Analysis</h3>
<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 4px; padding: 12px; margin-bottom: 20px;">
    <p style="margin: 0; color: #856404;">{approval.root_cause}</p>
</div>

<h3 style="color: #212529;">🔧 Proposed Remediation</h3>
<table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
    <tr style="background: #e9ecef;">
        <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Action</strong></td>
        <td style="padding: 8px; border: 1px solid #dee2e6;">{approval.proposed_action}</td>
    </tr>
    <tr>
        <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Playbook</strong></td>
        <td style="padding: 8px; border: 1px solid #dee2e6;"><code>{approval.playbook_path}</code></td>
    </tr>
    <tr style="background: #e9ecef;">
        <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Target</strong></td>
        <td style="padding: 8px; border: 1px solid #dee2e6;">{approval.affected_host}</td>
    </tr>
    <tr>
        <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Incident ID</strong></td>
        <td style="padding: 8px; border: 1px solid #dee2e6;"><code>{approval.incident_id}</code></td>
    </tr>
</table>

<div style="text-align: center; margin: 30px 0;">
    <a href="{approval_link}"
       style="display: inline-block; background: #28a745; color: white; padding: 14px 32px;
              text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: bold;">
        ✅ Approve Auto-Remediation
    </a>
</div>

<div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px; padding: 12px; margin-top: 20px;">
    <p style="margin: 0; color: #721c24; font-size: 13px;">
        ⏰ <strong>This link expires at {approval.expires_at}</strong><br>
        If not clicked before expiry, no automated action will be taken and the operator
        is expected to resolve the issue manually.
    </p>
</div>

<hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
<p style="color: #6c757d; font-size: 12px;">
    This is an automated notification from the AIOps Self-Healing Infrastructure.<br>
    Incident: {approval.incident_id} | Generated: {approval.expires_at}
</p>

</body>
</html>"""

    text_body = f"""\
ALERT: {approval.alert_name} [{approval.severity.upper()}]
Host: {approval.affected_host} | Service: {approval.service_name}

ROOT CAUSE:
{approval.root_cause}

PROPOSED REMEDIATION:
  Action: {approval.proposed_action}
  Playbook: {approval.playbook_path}
  Target: {approval.affected_host}

APPROVE AUTO-REMEDIATION: {approval_link}

⏰ Link expires at {approval.expires_at}
If not clicked, the operator must resolve manually.

Incident ID: {approval.incident_id}
"""

    return {
        "subject": subject,
        "html_body": html_body,
        "text_body": text_body,
    }


class EmailNotifier:
    """Sends RCA emails with approval links via Amazon SES."""

    def __init__(
        self,
        approval_handler: ApprovalHandler,
        ses_client=None,
        from_address: str = SES_FROM_ADDRESS,
        operator_email: str = OPERATOR_EMAIL,
    ) -> None:
        self._approval_handler = approval_handler
        self._ses = ses_client or boto3.client("ses")
        self._from_address = from_address
        self._operator_email = operator_email

    def send_approval_email(self, approval: PendingApproval) -> bool:
        """Send the RCA + approval link email.

        Returns:
            True if email sent successfully, False otherwise.
        """
        approval_link = self._approval_handler.get_approval_link(approval)
        email_content = build_rca_email(approval, approval_link)

        try:
            self._ses.send_email(
                Source=self._from_address,
                Destination={
                    "ToAddresses": [self._operator_email],
                },
                Message={
                    "Subject": {
                        "Data": email_content["subject"],
                        "Charset": "UTF-8",
                    },
                    "Body": {
                        "Html": {
                            "Data": email_content["html_body"],
                            "Charset": "UTF-8",
                        },
                        "Text": {
                            "Data": email_content["text_body"],
                            "Charset": "UTF-8",
                        },
                    },
                },
            )
            logger.info(
                "Approval email sent for incident %s to %s",
                approval.incident_id,
                self._operator_email,
            )
            return True
        except (ClientError, BotoCoreError) as e:
            logger.error("Failed to send approval email: %s", e)
            return False

    def send_expiry_notification(self, approval: PendingApproval) -> bool:
        """Send notification that approval expired (operator must fix manually)."""
        subject = (
            f"[EXPIRED] {approval.alert_name} on {approval.affected_host} "
            f"— Manual Resolution Required"
        )
        body = (
            f"The auto-remediation approval for incident {approval.incident_id} "
            f"has expired without being clicked.\n\n"
            f"Alert: {approval.alert_name}\n"
            f"Host: {approval.affected_host}\n"
            f"Service: {approval.service_name}\n\n"
            f"The operator is expected to resolve this issue manually.\n"
            f"Refer to runbooks for guidance."
        )

        try:
            self._ses.send_email(
                Source=self._from_address,
                Destination={"ToAddresses": [self._operator_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                },
            )
            return True
        except (ClientError, BotoCoreError) as e:
            logger.error("Failed to send expiry notification: %s", e)
            return False
