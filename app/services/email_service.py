import logging
import httpx
from typing import List, Optional
from app.core.config import settings

logger = logging.getLogger("email_service")
logging.basicConfig(level=logging.INFO)

RESEND_API_URL = "https://api.resend.com/emails"


class EmailService:
    @staticmethod
    def _is_resend_configured() -> bool:
        return bool(
            settings.RESEND_API_KEY
            and settings.RESEND_API_KEY.strip()
            and not settings.RESEND_API_KEY.startswith("re_test_dummy")
        )

    @classmethod
    def send_email(cls, to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
        """
        Sends an email using the Resend REST API.
        Never crashes the caller; returns True on success and False on failure with detailed logs.
        """
        if not cls._is_resend_configured():
            logger.warning(
                f"[EMAIL SERVICE] Real email transmission skipped for recipient '{to_email}'. "
                f"Reason: RESEND_API_KEY is missing or unconfigured. To enable real delivery, "
                f"provide a valid RESEND_API_KEY in .env or environment variables."
            )
            return False

        headers = {
            "Authorization": f"Bearer {settings.RESEND_API_KEY.strip()}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        if text_content:
            payload["text"] = text_content

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(RESEND_API_URL, json=payload, headers=headers)
                if response.status_code in (200, 201):
                    logger.info(f"[EMAIL SERVICE] Successfully sent email to {to_email}. Response: {response.json()}")
                    return True
                else:
                    logger.error(
                        f"[EMAIL SERVICE] Resend API error ({response.status_code}) sending email to {to_email}: {response.text}"
                    )
                    return False
        except Exception as e:
            logger.error(f"[EMAIL SERVICE] Network exception sending email to {to_email}: {str(e)}")
            return False

    @classmethod
    def send_booking_confirmation(
        cls,
        customer_email: str,
        customer_name: str,
        event_title: str,
        event_location: str,
        event_start_time: str,
        quantity: int,
        booking_id: int,
    ) -> bool:
        """
        Background Task 1: Sends booking confirmation email to customer.
        """
        subject = f"Booking Confirmation: {event_title} (Booking #{booking_id})"
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #2c3e50;">Booking Confirmation</h2>
                <p>Hello <strong>{customer_name}</strong>,</p>
                <p>Thank you for booking with us! Your reservation is confirmed.</p>
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 4px solid #3498db;">
                    <p><strong>Booking ID:</strong> #{booking_id}</p>
                    <p><strong>Event:</strong> {event_title}</p>
                    <p><strong>Location:</strong> {event_location}</p>
                    <p><strong>Date & Time:</strong> {event_start_time}</p>
                    <p><strong>Tickets Booked:</strong> {quantity}</p>
                </div>
                <p style="margin-top: 20px; font-size: 0.9em; color: #7f8c8d;">
                    Please present this confirmation email upon arrival at the event.
                </p>
            </body>
        </html>
        """
        text_content = (
            f"Hello {customer_name},\n\n"
            f"Your booking #{booking_id} for '{event_title}' has been confirmed!\n"
            f"Tickets: {quantity}\n"
            f"Location: {event_location}\n"
            f"Date & Time: {event_start_time}\n"
        )
        return cls.send_email(customer_email, subject, html_content, text_content)

    @classmethod
    def send_event_update_notifications(
        cls,
        recipients: List[dict],
        event_title: str,
        updated_fields: List[str],
        updated_event_details: dict,
    ) -> int:
        """
        Background Task 2: Fans out email notifications to all unique customers who booked this event.
        Avoids duplicates.
        """
        if not recipients:
            logger.info(f"[EMAIL SERVICE] No booked customers to notify for event '{event_title}'.")
            return 0

        # Deduplicate recipients by email
        seen_emails = set()
        unique_recipients = []
        for r in recipients:
            email = r.get("email")
            if email and email not in seen_emails:
                seen_emails.add(email)
                unique_recipients.append(r)

        sent_count = 0
        subject = f"Important Update: Your Event '{event_title}' Has Been Updated"
        updates_summary = ", ".join(updated_fields) if updated_fields else "Event details"

        for recipient in unique_recipients:
            customer_name = recipient.get("name", "Customer")
            customer_email = recipient.get("email")

            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #e67e22;">Event Update Notification</h2>
                    <p>Hello <strong>{customer_name}</strong>,</p>
                    <p>We are writing to inform you that the event <strong>{event_title}</strong> you have booked has been updated.</p>
                    <p><strong>Updated Fields:</strong> {updates_summary}</p>
                    <div style="background-color: #fef9e7; padding: 15px; border-radius: 6px; border-left: 4px solid #f39c12;">
                        <p><strong>Title:</strong> {updated_event_details.get('title')}</p>
                        <p><strong>Location:</strong> {updated_event_details.get('location')}</p>
                        <p><strong>Date & Time:</strong> {updated_event_details.get('start_time')}</p>
                        <p><strong>Description:</strong> {updated_event_details.get('description') or 'N/A'}</p>
                    </div>
                    <p style="margin-top: 20px; font-size: 0.9em; color: #7f8c8d;">
                        Your existing tickets remain valid. Contact the organizer if you have any questions.
                    </p>
                </body>
            </html>
            """
            text_content = (
                f"Hello {customer_name},\n\n"
                f"The event '{event_title}' you booked has been updated ({updates_summary}).\n"
                f"Location: {updated_event_details.get('location')}\n"
                f"Date & Time: {updated_event_details.get('start_time')}\n"
            )

            success = cls.send_email(customer_email, subject, html_content, text_content)
            if success:
                sent_count += 1

        logger.info(f"[EMAIL SERVICE] Finished sending updates to {len(unique_recipients)} customer(s). Sent: {sent_count}")
        return sent_count
