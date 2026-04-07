import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def send_scan_digest(scan_id: str, leads: list[dict]):
    """Send an HTML email digest after a scan completes (requires SendGrid config)."""
    from app.config import settings

    if not settings.sendgrid_api_key or not settings.alert_email:
        return

    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        top_leads = sorted(leads, key=lambda l: l.get("relevance_score", 0), reverse=True)[:5]
        active = [l for l in leads if l.get("freshness") in ("active", "stale")]

        lead_rows = "".join(
            f"<tr><td>{l.get('title')}</td><td>{l.get('institution')}</td>"
            f"<td>{l.get('country')}</td><td>{l.get('relevance_score')}</td>"
            f"<td>{l.get('freshness')}</td></tr>"
            for l in top_leads
        )

        html = f"""
        <h2>Delphee Lead Hunter — Scan Complete</h2>
        <p><strong>Scan ID:</strong> {scan_id}</p>
        <p><strong>Total leads:</strong> {len(leads)} &nbsp;|&nbsp;
           <strong>Actionable:</strong> {len(active)}</p>
        <h3>Top 5 Leads</h3>
        <table border="1" cellpadding="4" cellspacing="0">
          <tr><th>Title</th><th>Institution</th><th>Country</th><th>Score</th><th>Freshness</th></tr>
          {lead_rows}
        </table>
        """

        message = Mail(
            from_email="noreply@delphee.de",
            to_emails=settings.alert_email,
            subject=f"Delphee Lead Hunter — {len(leads)} leads found",
            html_content=html,
        )

        sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        sg.send(message)
        logger.info("Digest email sent to %s", settings.alert_email)

    except Exception as e:
        logger.error("Failed to send digest email: %s", e)
