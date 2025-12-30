import os
import json
import webbrowser
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv('YAHOO_CLIENT_ID')
CLIENT_SECRET = os.getenv('YAHOO_CLIENT_SECRET')
REDIRECT_URI = os.getenv('YAHOO_REDIRECT_URI')

AUTHORIZATION_BASE_URL = 'https://api.login.yahoo.com/oauth2/request_auth'
TOKEN_URL = 'https://api.login.yahoo.com/oauth2/get_token'

# Allow HTTP for local testing
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

def get_tokens():
    yahoo = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
    
    # 1. Get the auth URL
    authorization_url, state = yahoo.authorization_url(AUTHORIZATION_BASE_URL)
    
    print("--------------------------------------------------")
    print("   MANUAL AUTHENTICATION MODE")
    print("--------------------------------------------------")
    print("1. I will open the browser to Yahoo.")
    print("2. Log in and click 'Agree'.")
    print("3. You will likely see a 'Connection Refused' or 'Site can't be reached' error.")
    print("   *** THIS IS EXPECTED AND OKAY! ***")
    print("4. Copy the ENTIRE URL from your browser's address bar.")
    print("--------------------------------------------------")
    
    webbrowser.open(authorization_url)
    
    # 2. Manual Input
    print("\nWaiting for you to paste the URL below...")
    redirect_response = input("PASTE THE FULL URL HERE: ").strip()
    
    # 3. Fetch Token
    try:
        token = yahoo.fetch_token(
            TOKEN_URL,
            authorization_response=redirect_response,
            client_secret=CLIENT_SECRET
        )
        
        # 4. Save Token
        with open('yahoo_token.json', 'w') as f:
            json.dump(token, f, indent=4)
            
        print("\nSUCCESS! Token saved to 'yahoo_token.json'.")
        
    except Exception as e:
        print(f"\nError fetching token: {e}")

if __name__ == '__main__':
    get_tokens()