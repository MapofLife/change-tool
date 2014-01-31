import os
import ee

from oauth2client.appengine import AppAssertionCredentials

#Global variables
EE_URL = 'https://earthengine.googleapis.com'
CDB_URL = 'http://mol.cartodb.com/api/v2/sql'
EE_ACCOUNT = ''

EE_PRIVATE_KEY_FILE = 'privatekey.pem'

# DEBUG_MODE will be True if running in a local development environment.
DEBUG_MODE = ('SERVER_SOFTWARE' in os.environ and
              os.environ['SERVER_SOFTWARE'].startswith('Dev'))

# Set up the appropriate credentials depending on where we're running.
if DEBUG_MODE:
    EE_CREDENTIALS = ee.ServiceAccountCredentials(EE_ACCOUNT, EE_PRIVATE_KEY_FILE)
else:
    # The OAuth scope URL for the Google Earth Engine API.
    SCOPES = ('https://www.googleapis.com/auth/earthengine.readonly', 
              'https://www.googleapis.com/auth/earthbuilder.readonly')
    SCOPES = ' '.join(SCOPES)
    EE_CREDENTIALS = AppAssertionCredentials(scope=SCOPES)

ee.Initialize(EE_CREDENTIALS)