#!/usr/bin/python
from setuptools import setup
from tornado_gallery import __version__

setup (name='tornado_gallery',
        version=__version__,
        install_requires = [
            'tornado',
            'pillow',
            'filemagic',
            'cachefs',
        ],
        entry_points = {
            'console_scripts': [
                'tornado-gallery=tornado_gallery.server:main',
            ]
        },
	packages = [
            'tornado_gallery',
            'tornado_gallery.static',
        ],
        include_package_data=True
)
