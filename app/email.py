"""Resend email helper."""
from __future__ import annotations

import logging
import os
import httpx

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def send_invite(to_email: str, to_name: str, invite_url: str) -> None:
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("EMAIL_FROM", "Living High Ops <noreply@livinghigh.com.au>")

    if not api_key:
        logger.warning("RESEND_API_KEY not set — skipping invite email to %s", to_email)
        return

    subject = "You've been invited to Living High Staff Dashboard"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px">
      <h2 style="color:#075E54;margin-bottom:8px">Living High Staff Dashboard</h2>
      <p>Hi {to_name or to_email},</p>
      <p>You've been invited to join the Living High staff dashboard — your central hub for
         managing tenant conversations.</p>
      <p style="margin:28px 0">
        <a href="{invite_url}"
           style="background:#25D366;color:#fff;padding:12px 24px;border-radius:8px;
                  text-decoration:none;font-weight:bold">
          Accept invite &amp; create account
        </a>
      </p>
      <p style="color:#888;font-size:12px">
        This link takes you straight to the sign-up form. If you weren't expecting this email,
        you can safely ignore it.
      </p>
    </div>
    """

    resp = httpx.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"from": from_addr, "to": [to_email], "subject": subject, "html": html},
        timeout=15,
    )

    if resp.is_success:
        logger.info("Invite email sent | to=%s | id=%s", to_email, resp.json().get("id"))
    else:
        logger.error("Resend error | %s | %s", resp.status_code, resp.text)
        resp.raise_for_status()
