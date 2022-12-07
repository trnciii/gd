from setuptools import setup, find_packages

setup(
	name="ggrdr",
	version="0.0.1",
	packages={'ggrdr':['ggrdr']},
	package_data={'ggrdr':['data/*']},
	install_requires=[
		'google-api-python-client',
		'google-auth-httplib2',
		'google-auth-oauthlib',
	],
	entry_points={
		'console_scripts': [
			'gd = ggrdr.__main__:main'
		]
	}
)