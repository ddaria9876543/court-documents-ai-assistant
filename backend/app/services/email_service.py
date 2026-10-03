import mimetypes
import smtplib

from email.message import EmailMessage
from pathlib import Path

from app.core.config import settings


def send_document_email(
    recipient: str,
    subject: str,
    body: str,
    attachment_path: Path,
    attachment_name: str | None = None,
) -> None:
    """
    Отправляет письмо ответственному сотруднику через SMTP.

    Настройки SMTP берутся из app.core.config.settings,
    который загружает backend/.env.
    """

    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    smtp_username = settings.SMTP_USERNAME
    smtp_password = settings.SMTP_PASSWORD
    smtp_from = (
        settings.SMTP_FROM
        or smtp_username
    )

    use_ssl = settings.SMTP_USE_SSL
    use_tls = settings.SMTP_USE_TLS

    if not smtp_host:
        raise ValueError(
            "SMTP_HOST is not configured"
        )

    if not smtp_username:
        raise ValueError(
            "SMTP_USERNAME is not configured"
        )

    if not smtp_password:
        raise ValueError(
            "SMTP_PASSWORD is not configured"
        )

    if not smtp_from:
        raise ValueError(
            "SMTP_FROM is not configured"
        )

    if not attachment_path.exists():
        raise FileNotFoundError(
            f"Attachment not found: {attachment_path}"
        )

    message = EmailMessage()

    message["From"] = smtp_from
    message["To"] = recipient
    message["Subject"] = subject

    message.set_content(
        body
    )

    mime_type, _ = mimetypes.guess_type(
        attachment_path.name
    )

    if mime_type:
        main_type, sub_type = mime_type.split(
            "/",
            1,
        )
    else:
        main_type = "application"
        sub_type = "octet-stream"

    with attachment_path.open("rb") as file:
        file_content = file.read()

    message.add_attachment(
        file_content,
        maintype=main_type,
        subtype=sub_type,
        filename=(
            attachment_name
            or attachment_path.name
        ),
    )

    if use_ssl:
        with smtplib.SMTP_SSL(
            smtp_host,
            smtp_port,
            timeout=30,
        ) as smtp:
            smtp.login(
                smtp_username,
                smtp_password,
            )
            smtp.send_message(
                message
            )

        return

    with smtplib.SMTP(
        smtp_host,
        smtp_port,
        timeout=30,
    ) as smtp:

        smtp.ehlo()

        if use_tls:
            smtp.starttls()
            smtp.ehlo()

        smtp.login(
            smtp_username,
            smtp_password,
        )

        smtp.send_message(
            message
        )