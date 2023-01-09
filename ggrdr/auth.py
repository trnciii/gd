from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

import os


# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']


def datapath():
	import ggrdr
	return os.path.join(ggrdr.__path__[0], 'data')

def init():
	data = datapath()
	os.makedirs(data, exist_ok=True)

	print('enter credentials:')
	s = ''.join(iter(lambda:input(), ''))
	with open(os.path.join(data, 'credentials.json'), 'w') as f:
		f.write(s)

	return _core()


def reset():
	os.remove(os.path.join(datapath(), 'token.json'))
	return _core()


def _core():
	"""Shows basic usage of the Drive v3 API.
	Prints the names and ids of the first 10 files the user has access to.
	"""
	creds = None
	# The file token.json stores the user's access and refresh tokens, and is
	# created automatically when the authorization flow completes for the first
	# time.
	data = datapath()

	if os.path.exists(os.path.join(data, 'token.json')):
		creds = Credentials.from_authorized_user_file(os.path.join(data, 'token.json'), SCOPES)
	# If there are no (valid) credentials available, let the user log in.
	if not creds or not creds.valid:
		if creds and creds.expired and creds.refresh_token:
			creds.refresh(Request())
		else:
			flow = InstalledAppFlow.from_client_secrets_file(
				os.path.join(data, 'credentials.json'), SCOPES)
			creds = flow.run_local_server(port=0)
		# Save the credentials for the next run
		with open(os.path.join(data, 'token.json'), 'w') as token:
			token.write(creds.to_json())

	return creds


def core():
	try:
		return _core()
	except:
		if os.path.isfile(os.path.join(datapath(), 'credentials.json')):
			return reset()
		else:
			return init()


def add_args(parser):
	sub = parser.add_subparsers()

	sub.add_parser('init').set_defaults(handler=lambda _:init())
	sub.add_parser('reset').set_defaults(handler=lambda _:reset())