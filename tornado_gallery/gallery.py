#!/usr/bin/env python

from cachefs import CacheFs
from weakref import ref
from collections import OrderedDict

from time import time

from .metadata import MetadataCache
from .cache import Cache
from .photo import Photo
from .resizer import ResizerPool

from tornado.gen import coroutine, Return

GALLERY_META_FILE = 'info.txt'
CACHE_DIR_NAME = 'cache'


class GalleryCollection(Cache):
    """
    Represents the collection of photo galleries.
    """

    def __init__(self, root_dir, cache_subdir=CACHE_DIR_NAME,
            num_proc=None, cache_expiry=300.0,
            cache_stat_expiry=1.0):
        super(GalleryCollection, self).__init__(cache_duration=cache_expiry)
        self._fs_cache = CacheFs(cache_expiry, cache_stat_expiry)
        self._meta_cache = MetadataCache(self._fs_cache, cache_expiry)
        self._root_node = self._fs_cache[root_dir]
        self._resizer_pool = ResizerPool(
                self._root_node, cache_subdir=cache_subdir,
                num_proc=num_proc)
        self._cache_subdir = cache_subdir

    def __iter__(self):
        for entry in self._root_node:
            if entry == self._cache_subdir:
                continue
            node = self._root_node[entry]
            if not node.is_dir:
                continue

            try:
                if not node[GALLERY_META_FILE].is_file:
                    continue
                yield entry
            except KeyError:
                continue

    def _fetch(self, name):
        return Gallery(collection=self,
                gallery_node=self._root_node.join_node(name))


class Gallery(object):
    """
    Representation of a photo gallery.
    """

    def __init__(self, collection, gallery_node):
        self._collection = ref(collection)
        self._fs_node = gallery_node

        self._content = None
        self._content_mtime = 0

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
        return self._meta_cache[self._fs_node.join(GALLERY_META_FILE)]

    @coroutine
    def get_resized(self, photo, width=None, height=None, quality=60,
            rotation=0.0, img_format=None):
        if isinstance(photo, Photo):
            photo = photo.name

        result = yield self._resizer_pool.get_resized(
                gallery=self.name, photo=photo, width=width, height=height,
                quality=quality, rotation=rotation, img_format=img_format)
        raise Return(result)

    # Collection services
    @property
    def _meta_cache(self):
        return self._collection()._meta_cache

    @property
    def _resizer_pool(self):
        return self._collection()._resizer_pool
