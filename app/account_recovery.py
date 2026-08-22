"""Entrega de códigos de recuperação sem expor credenciais no navegador."""

import os
import smtplib
import ssl
from email.message import EmailMessage


class RecoveryDeliveryUnavailable(RuntimeError):
    pass


def send_recovery_code(email: str, code: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender:
        raise RecoveryDeliveryUnavailable("Envio de recuperação por e-mail não configurado")

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    use_ssl = os.getenv("SMTP_SSL", "false").lower() in {"1", "true", "yes"}
    use_starttls = os.getenv("SMTP_STARTTLS", "true").lower() not in {"0", "false", "no"}

    message = EmailMessage()
    message["Subject"] = "Código de segurança do BRCom ERP"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "Recebemos uma solicitação para desbloquear seu acesso ao BRCom ERP.\n\n"
        f"Código: {code}\n\n"
        "O código expira em 10 minutos. Se você não fez esta solicitação, "
        "avise um administrador."
    )

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=12, context=ssl.create_default_context()) as smtp:
                if username:
                    smtp.login(username, password)
                smtp.send_message(message)
            return
        with smtplib.SMTP(host, port, timeout=12) as smtp:
            smtp.ehlo()
            if use_starttls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise RecoveryDeliveryUnavailable("Não foi possível enviar o código de recuperação") from exc
