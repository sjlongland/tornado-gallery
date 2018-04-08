#!/usr/bin/env python

from cachefs import CacheFs
from weakref import WeakValueDictionary
from collections import OrderedDict

from time import time

from .metadata import MetadataCache
from .cache import Cache
from .photo import Photo
from .resizer import ResizerPool


class GalleryCollection(Cache):
    """
    Represents the collection of photo galleries.
    """

    def __init__(self, root_dir, num_proc=None, cache_expiry=300.0,
            cache_stat_expiry=1.0):
        super(GalleryCollection, self).__init__(cache_expiry=cache_expiry)
        self._fs_cache = CacheFs(cache_expory, cache_stat_expiry)
        self._meta_cache = MetadataCache(self._fs_cache, cache_expiry)
        self._root_node = self._fs_cache[root_dir]

    def _fetch(self, name):
        return Gallery(fs_cache=self._fs_cache,
                self._meta_cache, self._root_node.join_node(name))


class Gallery(object):
    """
    Representation of a photo gallery.
    """

    _INSTANCE = WeakValueDictionary()

    def __init__(self, fs_cache, meta_cache, gallery_node):
        self._fs_node = gallery_node
        self._title = None
        self._desc = None
        self._meta_cache = meta_cache
        self._meta_mtime = 0

        self._content = None
        self._content_mtime = 0

        assert self.name not in self._INSTANCE
        self._INSTANCE[self.name] = self

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
