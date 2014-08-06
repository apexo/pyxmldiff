#!/usr/bin/env python

from distutils.core import setup

setup(
	name='pyxmldiff',
	version='0.1.1',
	description='yet another XML diff tool',
	license='GPLv3',
	author='Christian Schubert',
	author_email='mail@apexo.de',
	url='https://github.com/apexo/pyxmldiff',
	packages=['pyxmldiff'],
	scripts=['bin/pyxmldiff'],
)
