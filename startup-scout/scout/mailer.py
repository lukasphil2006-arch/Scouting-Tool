"""Versand per SMTP. Zugangsdaten kommen aus Umgebungsvariablen (GitHub Secrets)."""
import os
import smtplib
from email.message import EmailMessage


def send(subject: str, body: str, attachment_path: str) -> bool:
    host, to = os.environ.get("SMTP_HOST"), os.environ.get("MAIL_TO")
    if not host or not to:
        print("Mailversand übersprungen (SMTP_HOST/MAIL_TO nicht gesetzt).")
        return False
    port = int(os.environ.get("SMTP_PORT", "587"))
    user, pw = os.environ.get("SMTP_USER", ""), os.environ.get("SMTP_PASS", "")
    sender = os.environ.get("MAIL_FROM", user)

    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, to
    msg.set_content(body)
    with open(attachment_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application",
                           subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           filename=os.path.basename(attachment_path))
    smtp = smtplib.SMTP_SSL(host, port) if port == 465 else smtplib.SMTP(host, port)
    with smtp as s:
        if port != 465:
            s.starttls()
        if user:
            s.login(user, pw)
        s.send_message(msg)
    print(f"Mail gesendet an {to}")
    return True
