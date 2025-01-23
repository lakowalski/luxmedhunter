
import smtplib
import requests
from loguru import logger

class MailHandler:
    def __init__(self, config):
        logger.info("Initializing MailHandler.")
        self.config = config

    def _send_mail_mailgun(self, subject: str, message: str, recipients: str):
        mailgun_config = self.config['mailgun']
        response = requests.post(
            f"https://api.mailgun.net/v3/{mailgun_config['domain']}/messages",
            auth=("api", mailgun_config["apikey"]),
            data={
                "from": f"mailgun@{mailgun_config['domain']}",
                "to": recipients,
                "subject": subject,
                "text": message
            }
        )
        response.raise_for_status()
        logger.info(f"Email sent by Mailgun. Status Code: {response.status_code}, Response: {response.text}")

    def _send_mail_smtp(self, subject: str, message: str, recipments: str):
        """Send email notifications about found appointments."""
        email_config = self.config["smtp"]
        with smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"]) as server:
            server.starttls()
            server.login(email_config["email"], email_config["password"])
            server.sendmail(
                from_addr=email_config["email"],
                to_addrs=recipments,
                msg=f"Subject: {subject}\n\n{message}"
            )
        logger.info("Email notification sent.")

    def send_mail(self, subject: str, message: str):
        """Send email notifications about found appointments."""
        config = self.config
        recipients = config['recipients']

        if config['provider'] == "SMTP":
            return self._send_mail_smtp(subject, message, recipients)
        elif config['provider'] == "MAILGUN":
            return self._send_mail_mailgun(subject, message, recipients)
        
        raise Exception(f"Unhandled email provider {config['provider']}")