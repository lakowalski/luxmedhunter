
import smtplib
import requests
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
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

    def _send_mail_ses(self, subject: str, message: str, recipients: str):
        """Send email using AWS SES."""
        ses_config = self.config['ses']
        session_config = ses_config.get('session', {})
        ses_client = boto3.Session(**session_config).client('ses')

        try:
            response = ses_client.send_email(
                Source=ses_config['sender'],
                Destination={
                    'ToAddresses': recipients.split(','),
                },
                Message={
                    'Subject': {
                        'Data': subject,
                    },
                    'Body': {
                        'Text': {
                            'Data': message,
                        },
                    },
                },
            )
            logger.info(f"Email sent via SES. Response: {response}")
        except NoCredentialsError:
            logger.error("Error: No AWS credentials found. Please configure your credentials.")
        except PartialCredentialsError:
            logger.error("Error: Incomplete AWS credentials configuration.")
        except Exception as e:
            logger.error(f"Error sending email via SES: {e}")

    def send_mail(self, subject: str, message: str):
        """Send email notifications about found appointments."""
        config = self.config
        recipients = config['recipients']

        if config['provider'] == "SMTP":
            return self._send_mail_smtp(subject, message, recipients)
        elif config['provider'] == "MAILGUN":
            return self._send_mail_mailgun(subject, message, recipients)
        elif config['provider'] == "SES":
            return self._send_mail_ses(subject, message, recipients)
        
        raise Exception(f"Unhandled email provider {config['provider']}")