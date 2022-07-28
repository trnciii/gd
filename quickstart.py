from __future__ import print_function

import os.path
import pprint

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']


def auth():
	"""Shows basic usage of the Drive v3 API.
	Prints the names and ids of the first 10 files the user has access to.
	"""
	creds = None
	# The file token.json stores the user's access and refresh tokens, and is
	# created automatically when the authorization flow completes for the first
	# time.
	if os.path.exists('token.json'):
		creds = Credentials.from_authorized_user_file('token.json', SCOPES)
	# If there are no (valid) credentials available, let the user log in.
	if not creds or not creds.valid:
		if creds and creds.expired and creds.refresh_token:
			creds.refresh(Request())
		else:
			flow = InstalledAppFlow.from_client_secrets_file(
				'credentials.json', SCOPES)
			creds = flow.run_local_server(port=0)
		# Save the credentials for the next run
		with open('token.json', 'w') as token:
			token.write(creds.to_json())

	return creds

def fileId_from_path(service, path):
	path = os.path.normpath(path).split('/')

	q = ' or '.join( f'name = "{name}"' for name in path )
	results = service.files().list(
		q = q,
		fields = 'files(parents, id, name)'
	).execute()

	files = results['files']

	trees = []
	depth = len(path)
	for base in [i for i in files if i['name'] == path[-1]]:
		tree = [base]

		for count in reversed(range(-depth, -1)):
			try:
				parent = next(filter(lambda i: i['id'] in tree[-1]['parents'] and i['name'] == path[count], files))
				tree.append(parent)
				if parent['name'] == path[0]:
					# print(*tree, sep='\n')
					return tree[0]['id']
			except StopIteration:
				break



def list_items(service):
	# Call the Drive v3 API
	results = service.files().list(pageSize=30).execute()
	items = results.get('files', [])
	if not items:
		print('No files found.')
		return

	for item in items:
		w = max(len(k) for k in item.keys())
		for k, v in item.items():
			print(u'{}: {}'.format(k.ljust(w), v))
		print()


def make_directory(service):
	return service.files().create(
		body={
			'name': 'creted-by-quickstart',
			'mimeType': 'application/vnd.google-apps.folder',
		},
		fields = 'id'
	).execute()


def main():
	try:
		service = build('drive', 'v3', credentials=auth())
		fileid = fileId_from_path(service, 'mf/slides/20210707.pptx')
		print(fileid)
		# list_items(service)

		# file = make_directory(service)
		# print('folder ID:', file.get('id'))


	except HttpError as error:
		# TODO(developer) - Handle errors from drive API.
		print(f'An error occurred: {error}')


if __name__ == '__main__':
	main()