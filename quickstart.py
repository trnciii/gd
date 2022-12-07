from __future__ import print_function

import os.path
import argparse

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
	depth = len(path)
	if path[0] == '.':
		print('path cannot be root')
		return


	q = '("root" in parents and ' + ') or ('.join( f'name = "{name}"' for name in path ) + ')'

	files = service.files().list(
		q = q,
		fields = 'files(parents, id, name)'
	).execute()['files']


	if depth == 1:
		assert len(files) == 1
		return files[0]['id']


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



def list_items(service, path, order='folder, name', trashed = False):
	fid = 'root' if path == 'root' else fileId_from_path(service, path)
	results = service.files().list(
		q = f'"{fid}" in parents and trashed = {"true" if trashed else "false"}'.format(),
		orderBy = order,
	).execute()

	return results.get('files', [])


def make_directory(service, path):
	head, tail = os.path.split(path)
	parent_id = fileId_from_path(service, head)

	fileId = service.files().create(
		body={
			'name': tail,
			'mimeType': 'application/vnd.google-apps.folder',
			'parents': [f"{parent_id}"] if parent_id else []
		},
		fields = 'id'
	).execute()

	return fileId


def main():
	try:
		service = build('drive', 'v3', credentials=auth())

		parser = argparse.ArgumentParser()
		sub = parser.add_subparsers()

		p = sub.add_parser('mkdir')
		p.add_argument('path')
		p.set_defaults(handler=lambda args:make_directory(service, args.path))

		p = sub.add_parser('ls')
		p.add_argument('path')
		p.add_argument('--trashed', action='store_true')
		p.set_defaults(handler=lambda args:print('\n'.join(i['name'] for i in list_items(service, args.path, trashed=args.trashed))))


		args = parser.parse_args()
		args.handler(args)

	except HttpError as error:
		# TODO(developer) - Handle errors from drive API.
		print(f'An error occurred: {error}')


if __name__ == '__main__':
	main()