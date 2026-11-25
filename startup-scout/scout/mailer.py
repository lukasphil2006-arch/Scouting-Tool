"""Versand per SMTP. Zugangsdaten kommen aus Umgebungsvariablen (GitHub Secrets).
Verbindung wird per IPv4 aufgebaut, weil GitHub-Runner kein IPv6 haben."""
import os
import smtplib
import socket
from email.message import EmailMessage


def _connect_v4(host, port, timeout):
    ip = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
    return socket.create_connection((ip, port), timeout if isinstance(timeout, (int, float)) else 30)


class _SMTP4(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        return _connect_v4(host, port, timeout)


class _SMTP4SSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        return self.context.wrap_socket(_connect_v4(host, port, timeout), server_hostname=self._host)


def send(subject: str, body: str, attachment_path: str) -> bool:
    host, to = os.environ.get("SMTP_HOST"), os.environ.get("MAIL_TO")
    if not host or not to:
        print("Mailversand übersprungen (SMTP_HOST/MAIL_TO nicht gesetzt).")
        return False
    port = int(os.environ.get("SMTP_PORT") or "587")
    user, pw = os.environ.get("SMTP_USER", ""), os.environ.get("SMTP_PASS", "")
    sender = os.environ.get("MAIL_FROM") or user

    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, to
    msg.set_content(body)
    with open(attachment_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application",
                           subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           filename=os.path.basename(attachment_path))
    smtp = _SMTP4SSL(host, port, timeout=30) if port == 465 else _SMTP4(host, port, timeout=30)
    with smtp as s:
        if port != 465:
            s.starttls()
        if user:
            s.login(user, pw)
        s.send_message(msg)
    print(f"Mail gesendet an {to}")
    return True
