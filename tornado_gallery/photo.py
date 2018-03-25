#!/usr/bin/env python

from weakref import ref

import os.path
from time import time

from .metadata import parse_meta
from .photo import Photo


class Photo(object):
    """
    Representation of a photo in a gallery.
    """

    def __init__(self, gallery, name):
        self._gallery = ref(gallery)
        self._name = name

        self._title = None
        self._desc = None
        self._meta_cache = meta_cache
        self._meta_mtime = 0
        self._fs_cache = fs_cache

        self._content = None
        self._content_mtime = 0

        assert self.name not in self._INSTANCE
        self._INSTANCE[self.name] = self

    @property
    def fs_cache(self):
        return self._fs_cache

    @property
    def meta_cache(self):
        return self._meta_cache

    @property
    def dir(self):
        return self._dir

    @property
    def name(self):
        return os.path.basename(self.dir)

    @property
    def title(self):
        self._parse_metadata()
        return self._title

    @property
    def desc(self):
        self._parse_metadata()
        return self._desc

    @property
    def content(self):
        content_mtime_now = self._content_mtime_now
        if self._content_mtime < content_mtime_now:
            content = {}
            for name in self._fs_cache[self.dir]:
                # Grab the file extension and analyse
                (_, ext) = name.rsplit('.',1)
                if ext.lower() not in ('jpg', 'jpe', 'jpeg', 'gif',
                                        'png', 'tif', 'tiff'):
                    continue
                # This is a photo.
                content[name] = Photo(self, name)
            self._content = OrderedDict(sorted(content.items(),
                key=lambda i : i[0]))
            self._content_mtime = content_mtime_now
        return self._content.copy()

    @property
    def _meta_file(self):
        return os.path.join(self.dir, 'info.txt')

    @property
    def _meta_mtime_now(self):
        return self._fs_cache[self._meta_file].stat.st_mtime

    @property
    def _dir_mtime_now(self):
        return self._fs_cache[self.dir].stat.st_mtime

    def _parse_metadata(self):
        meta_mtime_now = self._meta_mtime_now
        if meta_mtime_now > self._meta_mtime:
            data = self._meta_cache[meta_file]
            self._title = data.get('.title', self.name)
            self._desc = data.get('.desc', 'No description given')
            self._meta_mtime = meta_mtime_now
