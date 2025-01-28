import os
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import gspread

load_dotenv()

def get_google_auth():
    
    """
    Get credentials for Google API & return the authorized client.
    """

    google_creds = {
        "type": os.getenv('GOOGLE_SERVICE_ACCOUNT_TYPE'),
        "project_id": os.getenv('GOOGLE_PROJECT_ID'),
        "private_key_id": os.getenv('GOOGLE_PRIVATE_KEY_ID'),
        "private_key": os.getenv('GOOGLE_PRIVATE_KEY').replace('\\n', '\n'),
        "client_email": os.getenv('GOOGLE_CLIENT_EMAIL'),
        "client_id": os.getenv('GOOGLE_CLIENT_ID'),
        "auth_uri": os.getenv('GOOGLE_AUTH_URI'),
        "token_uri": os.getenv('GOOGLE_TOKEN_URI'),
        "auth_provider_x509_cert_url": os.getenv('GOOGLE_AUTH_PROVIDER_X509_CERT_URL'),
        "client_x509_cert_url": os.getenv('GOOGLE_CLIENT_X509_CERT_URL')
    }

    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/analytics.readonly']
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
    gc = gspread.authorize(credentials)
    return gc