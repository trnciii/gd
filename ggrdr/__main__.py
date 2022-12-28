import os
import argparse
import webbrowser
import io
from concurrent.futures import ThreadPoolExecutor
import readline

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from . import auth


def create_service():
	return build('drive', 'v3', credentials=auth.core())

def lspretty(l):
	print('\n'.join(i['name'] for i in l))


def file_from_path(path, fields=[], service=None):
	if not service:
		service = create_service()


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
		if len(files) == 1:
			return files[0]
		else:
			return None


	for base in [i for i in files if i['name'] == path[-1]]:
		tree = [base]

		for count in reversed(range(-depth, -1)):
			try:
				parent = next(filter(lambda i: i['id'] in tree[-1]['parents'] and i['name'] == path[count], files))
				tree.append(parent)
				if parent['name'] == path[0]:
					return tree[0]
			except StopIteration:
				break


def path_from_file(fileId, service=None):
	if not service:
		service = create_service()

	path = ''
	while True:
		ret = service.files().get(fileId=fileId, fields='name,parents').execute()

		if 'parents' not in ret.keys():
			return f'root{path}'

		path = f'/{ret["name"]}{path}'
		fileId = ret['parents'][0]


def list_items(path, order='folder, name', trashed = False, service=None):
	if not service:
		service = create_service()

	fid = file_from_path(path, service=service)['id']
	results = service.files().list(
		q = f'"{fid}" in parents and trashed = {"true" if trashed else "false"}',
		orderBy = order,
	).execute()

	return results.get('files', [])


def make_directory(path, service=None):
	if not service:
		service = create_service()

	head, tail = os.path.split(path)
	parent_id = file_from_path(head, service=service)['id']

	fileId = service.files().create(
		body={
			'name': tail,
			'mimeType': 'application/vnd.google-apps.folder',
			'parents': [parent_id]
		},
		fields = 'id'
	).execute()

	return fileId


def trash(empty=False, info=False):
	service = create_service()

	results = service.files().list(
		q='trashed=true',
		fields='files(parents,name)'
	).execute().get('files', [])

	if len(results) == 0: return

	w = max(len(i['name']) for i in results)

	if info:
		item = lambda i: i['name'].ljust(w) + '\n'.ljust(w).join(' | ' + path_from_file(create_service(), p) for p in i['parents'])
		with ThreadPoolExecutor() as e:
			futures = [e.submit(item, i) for i in results]
			for f in futures:
				print(f.result())

	else:
		print('\n'.join(f'{r["name"].ljust(w)} | parents {r["parents"]}' for r in results))

	if empty and 'n' != input('remove files [Y/n]').lower():
		service.files().emptyTrash().execute()
		print('done')


def remove(path):
	service = create_service()
	fid = file_from_path(path, service=service)['id']
	service.files().update(fileId=fid, body={'trashed': True}).execute()

def open_dir(path):
	file = file_from_path(path, fields=['webViewLink'])
	webbrowser.open(file['webViewLink'])


def update_download_path(path, default):
	if os.path.isdir(path):
		return update_download_path(os.path.join(path, default), default)

	if os.path.isfile(path):
		new = input('File already exists. Press enter to overwrite or choose a different name: ')
		if new:
			return update_download_path(new, default)
		else:
			return path

	par = os.path.split(os.path.abspath(path))[0]
	if not os.path.isdir(par):
		new = input(f"'{par}' is not a directory. Choose a different name: ")
		return update_download_path(new, default)

	return path


def download_core(fileId, service):
	request = service.files().get_media(fileId=fileId)
	raw = io.BytesIO()
	downloader = MediaIoBaseDownload(raw, request)
	done = False
	while done is False:
		status, done = downloader.next_chunk()
		print(f'\rprogress {int(status.progress() * 100):3}%', end='', flush=True)
	print()
	return raw.getvalue()


def download(path, out):
	service = create_service()

	fo = file_from_path(path, service=service)

	out = update_download_path(out, fo['name'])

	value = download_core(fo['id'], service)

	with open(out, 'wb') as f:
		f.write(value)
	print(f'saved, {out}')


def about():
	field = 'storageQuota'
	res = create_service().about().get(fields=field).execute()[field]
	w = max(len(k) for k in res.keys())
	print('\n'.join(f'{k.ljust(w)} {int(v)/1024**3:5.2f}' for k, v in res.items()))


def completion():
	with open(os.path.join(auth.datapath(), 'completion.bash')) as f:
		print(f.read())


def main():
	try:
		readline.parse_and_bind('tab: complete')

		parser = argparse.ArgumentParser()
		sub = parser.add_subparsers()

		p = sub.add_parser('mkdir')
		p.add_argument('path')
		p.set_defaults(handler=lambda args:make_directory(args.path))

		p = sub.add_parser('ls')
		p.add_argument('path', nargs='?', default='root')
		p.add_argument('--trashed', action='store_true')
		p.set_defaults(handler=lambda args:lspretty(list_items(args.path, trashed=args.trashed)))

		p = sub.add_parser('path')
		p.add_argument('id')
		p.set_defaults(handler=lambda args:print(path_from_file(args.id)))

		p = sub.add_parser('trash')
		p.add_argument('-E', '--empty', action='store_true')
		p.add_argument('-i', '--info', action='store_true')
		p.set_defaults(handler=lambda args:trash(args.empty, args.info))

		p = sub.add_parser('rm')
		p.add_argument('path')
		p.set_defaults(handler=lambda args:remove(args.path))

		p = sub.add_parser('open')
		p.add_argument('path', nargs='?', default='root')
		p.set_defaults(handler=lambda args:open_dir(args.path))

		p = sub.add_parser('info')
		p.add_argument('path', nargs='?', default='root')
		p.add_argument('fields', nargs='*')
		p.set_defaults(handler=lambda args:print('\n'.join(
			f'{k}\t{v}' for k, v in file_from_path(args.path, args.fields).items())
		))

		p = sub.add_parser('download')
		p.add_argument('path')
		p.add_argument('-o', default='.')
		p.set_defaults(handler=lambda args:download(args.path, args.o))

		sub.add_parser('about').set_defaults(handler=lambda _:about())

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