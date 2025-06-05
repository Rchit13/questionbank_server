from typing import Optional

from fastapi import FastAPI

from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI()

SERVICE_ACCOUNT_FILE = 'service-account.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('drive', 'v3', credentials=credentials)
    return service

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/files")
def list_files():
    service = get_drive_service()
    results = service.files().list(pageSize=10).execute()
    files = results.get('files', [])
    return files


