from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pickle, os
from email.mime.text import MIMEText
import base64

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_gmail_service():
    creds = None
    # Load existing token
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If no valid creds, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)  # Opens browser for login
        # Save creds
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)
    return service

def send_email(to, subject, body):
    service = get_gmail_service()
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    message_obj = {'raw': raw}

    sent = service.users().messages().send(userId='me', body=message_obj).execute()
    print(f"Email sent to {to}, ID: {sent['id']}")

if __name__ == "__main__":
    to = input("Enter recipient email: ")
    subject = "Test Email"
    body = "This is a test email from Gmail API."
    send_email(to, subject, body)