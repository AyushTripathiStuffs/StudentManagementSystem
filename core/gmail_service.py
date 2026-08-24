import os
import base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_gmail_service():
    creds = None
    token_path = 'token.json'
    cred_path = 'credentials.json'

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

def send_gcp_email(to_email, subject, body_text):
    try:
        service = get_gmail_service()
        message = MIMEText(body_text)
        message['to'] = to_email
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        body = {'raw': raw_message}
        
        sent_message = service.users().messages().send(userId='me', body=body).execute()
        print(f"[GCP GMAIL API SUCCESS] Message ID: {sent_message['id']}")
        return True
    except Exception as e:
        print(f"[GCP GMAIL API ERROR] Failed to send email: {e}")
        return False