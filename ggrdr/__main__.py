import os
import argparse
import webbrowser

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from . import auth


def lspretty(l):
	print('\n'.join(i['name'] for i in l))


def file_from_path(service, path, fields=[]):
	fields += ['parents', 'id', 'name']

	path = os.path.normpath(path).split('/')
	if path[0] in {'.', 'root'}:
		del path[0]

	depth = len(path)
	if depth == 0:
		return service.files().get(fileId='root', fields=','.join(fields)).execute()


	q = 'or'.join(f'(name="{name}" and trashed=false)' for name in path).replace('(', '("root" in parents and ', 1)

	files = service.files().list(
		q = q,
		fields = f'files({",".join(fields)})'
	).execute()['files']


	if depth == 1:
		assert len(files) == 1
		return files[0]


	for base in [i for i in files if i['name'] == path[-1]]:
		tree = [base]

		for count in reversed(range(-depth, -1)):
			try:
				parent = next(filter(lambda i: i['id'] in tree[-1]['parents'] and i['name'] == path[count], files))
				tree.append(parent)
				if parent['name'] == path[0]:
					# print(*tree, sep='\n')
					return tree[0]
			except StopIteration:
				break



def list_items(service, path, order='folder, name', trashed = False):
	fid = file_from_path(service, path)['id']
	results = service.files().list(
		q = f'"{fid}" in parents and trashed = {"true" if trashed else "false"}',
		orderBy = order,
	).execute()

	return results.get('files', [])


def make_directory(service, path):
	head, tail = os.path.split(path)
	parent_id = file_from_path(service, head)['id']

	fileId = service.files().create(
		body={
			'name': tail,
			'mimeType': 'application/vnd.google-apps.folder',
			'parents': [parent_id]
		},
		fields = 'id'
	).execute()

	return fileId


def trash(service, empty=False):
	results = service.files().list(
		q='trashed=true',
		fields='files(parents,name)'
	).execute().get('files', [])

	if len(results) == 0: return

	w = max(len(i['name']) for i in results)
	print('\n'.join(f'{r["name"].ljust(w)} | parents {r["parents"]}' for r in results))

	if empty and 'n' != input('remove files [Y/n]').lower():
		service.files().emptyTrash().execute()
		print('done')


def remove(service, path):
	fid = file_from_path(service, path)['id']
	service.files().update(fileId=fid, body={'trashed': True}).execute()

def open_dir(service, path):
	file = file_from_path(service, path, fields=['webViewLink'])
	webbrowser.open(file['webViewLink'])


def about(service):
	field = 'storageQuota'
	res = service.about().get(fields=field).execute()[field]
	w = max(len(k) for k in res.keys())
	print('\n'.join(f'{k.ljust(w)} {int(v)/1024**3:5.2f}' for k, v in res.items()))


def completion():
	with open(os.path.join(auth.datapath(), 'completion.bash')) as f:
		print(f.read())


def main():
	try:
		service = lambda:build('drive', 'v3', credentials=auth.core())

		parser = argparse.ArgumentParser()
		sub = parser.add_subparsers()

		p = sub.add_parser('mkdir')
		p.add_argument('path')
		p.set_defaults(handler=lambda args:make_directory(service(), args.path))

		p = sub.add_parser('ls')
		p.add_argument('path', nargs='?', default='root')
		p.add_argument('--trashed', action='store_true')
		p.set_defaults(handler=lambda args:lspretty(list_items(service(), args.path, trashed=args.trashed)))

		p = sub.add_parser('trash')
		p.add_argument('-E', '--empty', action='store_true')
		p.set_defaults(handler=lambda args:trash(service(), args.empty))

		p = sub.add_parser('rm')
		p.add_argument('path')
		p.set_defaults(handler=lambda args:remove(service(), args.path))

		p = sub.add_parser('open')
		p.add_argument('path', nargs='?', default='root')
		p.set_defaults(handler=lambda args:open_dir(service(), args.path))

		p = sub.add_parser('info')
		p.add_argument('path', nargs='?', default='root')
		p.add_argument('fields', nargs='*')
		p.set_defaults(handler=lambda args:print('\n'.join(
			f'{k}\t{v}' for k, v in file_from_path(service(), args.path, args.fields).items())
		))

		sub.add_parser('about').set_defaults(handler=lambda _:about(service()))

		sub.add_parser('completion').set_defaults(handler=lambda _:completion())

		auth.add_args(sub.add_parser('auth'))


		args = parser.parse_args()
		if hasattr(args, 'handler'):
			args.handler(args)

	except HttpError as error:
		# TODO(developer) - Handle errors from drive API.
		print(f'An error occurred: {error}')


if __name__ == '__main__':
	main()