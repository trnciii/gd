import os
import argparse
import webbrowser
import io
from concurrent.futures import ThreadPoolExecutor
import readline

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

from . import auth
from .ayame import terminal, zen


def create_service():
	return build('drive', 'v3', credentials=auth.core())


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


def ls(path, order='folder, name', trashed = False, fields=[], askeys=False, trim=True):
	service = create_service()

	fid = file_from_path(path, service=service)['id']
	results = service.files().list(
		q = f'"{fid}" in parents and trashed = {"true" if trashed else "false"}',
		orderBy = order,
		fields=f'files({",".join({"name", "mimeType"} | set(fields))})'
	).execute()


	if askeys:
		print('\n'.join(i['name'] for i in results.get('files', [])))

	else:
		display_fields = ['name'] + fields

		files = results.get('files', [])
		widths = {k:max(zen.display_length(i[k]) for i in files) for k in display_fields}

		if trim:
			total = sum(i+3 for i in widths.values()) - 3
			exceed = total - os.get_terminal_size()[0]
			if exceed > 0:
				widths = {k:v - int(exceed * v/total + 1) for k, v in widths.items()}

		print(' | '.join(f.ljust(widths[f]) for f in display_fields))
		print('-'*(sum(i + 3 for i in widths.values()) - 3))
		for i in files:
			if i['mimeType'] == 'application/vnd.google-apps.folder':
				i['name'] = terminal.mod(i['name'], terminal.color('blue'), terminal.bold())

			print(' | ' .join(
				zen.ljust(zen.trim(i[f], widths[f]), widths[f])
				for f in display_fields
			))


def make_directory(path, service=None):
	if not service:
		service = create_service()

	while True:
		par, chi = os.path.split(path)

		par_fo = file_from_path(par, fields=['mimeType'], service=service)
		if (not par_fo) or (par_fo['mimeType'] != 'application/vnd.google-apps.folder'):
			path = input(f"'{par}' is not a directory. Choose different path: ")
			continue

		chi_fo = file_from_path(path, service=service)
		if chi_fo:
			path = input(f"'{path}' already exists. Choose different name or press enter to allow duplication: ")
			continue

		break

	fileId = service.files().create(
		body={
			'name': chi,
			'mimeType': 'application/vnd.google-apps.folder',
			'parents': [par_fo['id']]
		},
		fields = 'id'
	).execute()

	return fileId


def trash(empty=False, parentpath=False):
	service = create_service()

	results = service.files().list(
		q='trashed=true',
		fields='files(parents,name)'
	).execute().get('files', [])

	if len(results) == 0: return

	if parentpath:
		with ThreadPoolExecutor() as e:
			parents = list(e.map(
				lambda i:[path_from_file(p, service=create_service()) for p in i['parents']],
				results
			))
	else:
		parents = [i['parents'] for i in results]

	full = os.get_terminal_size()[0]
	w = max(30, full - max(max(len(j) for j in i) for i in parents+['parents']) - 3)
	print('files'.ljust(w) + ' | parents')
	print('-'*full)
	for name, parents in zip((r['name'] for r in results), parents):
		print(zen.ljust(zen.trim(name, w), w) + '\n'.ljust(w).join(' | ' + p for p in parents))

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


def download_core(fileId, silent=False, service=None):
	request = service.files().get_media(fileId=fileId)
	raw = io.BytesIO()
	downloader = MediaIoBaseDownload(raw, request, chunksize=1024*512)
	while True:
		status, done = downloader.next_chunk()

		if done:
			break

		if not silent:
			print(f'\rprogress {int(status.progress() * 100):3}%', end='', flush=True)

	terminal.clean_row()

	return raw.getvalue()


def download(path, out):
	service = create_service()

	fo = file_from_path(path, service=service)

	out = update_download_path(out, fo['name'])
	value = download_core(fo['id'], service=service)

	with open(out, 'wb') as f:
		f.write(value)
	print(f'saved {out}')


def cat(path):
	service = create_service()
	fo = file_from_path(path, fields=['mimeType'], service=service)

	printable = {'text', 'json'}
	mimeType = fo['mimeType']
	if all(i not in mimeType for i in printable):
		if 'n' == input(f'{mimeType=} may not be printable. Continue? (Y/n)').lower():
			return
		else:
			print()

	value = download_core(fo['id'], silent=True, service=service)
	print(value.decode('utf-8'))


def update_upload_path(path, default):
	fo = file_from_path(path, fields=['mimeType'])
	if fo:
		if fo['mimeType'] == 'application/vnd.google-apps.folder':
			return update_upload_path(os.path.join(path, default), default)
		else:
			new = input(f"'{path}' already exists. Choose different name or press enter to allow duplication: ")
			if new:
				return update_upload_path(new, default)
			else:
				first, second = os.path.split(path)
				return file_from_path(first), second
	else:
		first, second = os.path.split(path)
		parent = file_from_path(first)
		if parent:
			return parent, second
		else:
			new = input(f"'{first}' does not exit. Choose different path: ")
			return update_upload_path(new, default)


def upload(local, remote):
	if not os.path.isfile(local):
		print(f"'{local}' is not a file")
		return

	service = create_service()

	parent, file = update_upload_path(remote, os.path.basename(local))

	meta = {
		'name': file,
		'parents': [parent['id']]
	}

	media = MediaFileUpload(local)
	service.files().create(body=meta, media_body=media).execute()



def about():
	field = 'storageQuota'
	res = create_service().about().get(fields=field).execute()
	quota = {k:int(v) for k, v in res[field].items()}

	quota['free'] = quota['limit'] - quota['usage']

	w = max(len(k) for k in quota.keys())
	print('\n'.join(f'{k.ljust(w)} {v/1024**3:5.2f}' for k, v in quota.items()))


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
		p.add_argument('--fields', nargs='*', default=[])
		p.add_argument('--keys', action='store_true')
		p.add_argument('--no-trim', action='store_false')
		p.set_defaults(handler=lambda args:ls(
			args.path,
			trashed=args.trashed,
			fields=args.fields,
			askeys=args.keys,
			trim=args.no_trim
		))

		p = sub.add_parser('path')
		p.add_argument('id')
		p.set_defaults(handler=lambda args:print(path_from_file(args.id)))

		p = sub.add_parser('trash')
		p.add_argument('-E', '--empty', action='store_true')
		p.add_argument('-i', '--path', action='store_true')
		p.set_defaults(handler=lambda args:trash(args.empty, args.path))

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

		p = sub.add_parser('upload')
		p.add_argument('src')
		p.add_argument('dst', nargs='?', default='root')
		p.set_defaults(handler=lambda args:upload(args.src, args.dst))

		p = sub.add_parser('cat')
		p.add_argument('path')
		p.set_defaults(handler=lambda args:cat(args.path))

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