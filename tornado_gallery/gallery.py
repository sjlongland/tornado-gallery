#!/usr/bin/env python

from weakref import WeakValueDictionary
from collections import OrderedDict

from time import time

from .metadata import parse_meta
from .photo import Photo


class Gallery(object):
    """
    Representation of a photo gallery.
    """

    _INSTANCE = WeakValueDictionary()

    def __init__(self, fs_cache, meta_cache, path):
        self._fs_cache = fs_cache
        self._fs_node = self._fs_cache[path]
        self._title = None
        self._desc = None
        self._meta_cache = meta_cache
        self._meta_mtime = 0

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
        return self._fs_node.abs_path

    @property
    def name(self):
        return self._fs_node.base_name

    @property
    def title(self):
        return self._meta['.title']

    @property
    def desc(self):
        return self._meta['.desc']

    @property
    def content(self):
        content_mtime_now = self._fs_node.mtime
        if self._content_mtime < content_mtime_now:
            content = {}
            for name in self._fs_node:
                # Grab the file extension and analyse
                (_, ext) = name.rsplit('.',1)
                if ext.lower() not in ('jpg', 'jpe', 'jpeg', 'gif',
                                        'png', 'tif', 'tiff', 'bmp',):
                    continue
                # This is a photo.
                content[name] = Photo(self, self._fs_node[name])
            self._content = OrderedDict(sorted(content.items(),
                key=lambda i : i[0]))
            self._content_mtime = content_mtime_now
        return self._content.copy()

    @property
    def _meta(self):
        return self._meta_cache[self._fs_node.join('info.txt')]
