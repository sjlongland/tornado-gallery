#!/usr/bin/env python

import logging
import os.path

from cachefs import CacheFs
from weakref import ref
from collections import OrderedDict, Mapping

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
            cache_stat_expiry=1.0, log=None):
        if log is None:
            log = logging.getLogger(self.__class__.__module__)

        super(GalleryCollection, self).__init__(
                cache_duration=cache_expiry, log=log)
        self._fs_cache = CacheFs(cache_expiry, cache_stat_expiry)
        self._meta_cache = MetadataCache(self._fs_cache, cache_expiry,
                log=log.getChild('meta'))
        self._root_node = self._fs_cache[root_dir]
        self._resizer_pool = ResizerPool(
                self._root_node, cache_subdir=cache_subdir,
                num_proc=num_proc, log=log.getChild('resizer'))
        self._cache_subdir = cache_subdir

        self._content = None
        self._content_mtime = None

    def __iter__(self):
        content_mtime = self._root_node.stat.st_mtime
        if (self._content_mtime is None) or \
                (content_mtime > self._content_mtime):
            content = []
            for entry in self._root_node:
                if entry == self._cache_subdir:
                    continue
                node = self._root_node[entry]
                if not node.is_dir:
                    continue

                try:
                    if not node[GALLERY_META_FILE].is_file:
                        continue
                    content.append(entry)
                except KeyError:
                    continue

            content.sort()
            self._content = content
            self._content_mtime = content_mtime
        return iter(self._content)
    def _fetch(self, name):
        return Gallery(collection=self,
                gallery_node=self._root_node.join_node(name))


class Gallery(Mapping):
    """
    Representation of a photo gallery.
    """

    def __init__(self, collection, gallery_node):
        self._collection = ref(collection)
        self._fs_node = gallery_node

        self._content_mtime = None
        self._content = None
        self._links = None
        self._content_prev_order = None
        self._content_next_order = None

    @property
    def name(self):
        return self._fs_node.base_name

    @property
    def title(self):
        return self._meta['.title']

    @property
    def desc(self):
        return self._meta['.desc']

    def __iter__(self):
        return iter(self._get_content().keys())

    def __getitem__(self, item):
        try:
            return self._get_content()[item]
        except KeyError:
            # Maybe a link?  Redirect!
            (gallery_name, photo_name) = self._links[item]
            return self._collection()[gallery_name][photo_name]

    def __len__(self):
        return len(self._get_content())

    def _get_content(self):
        content_mtime_now = self._fs_node.stat.st_mtime
        if (self._content_mtime is None) or \
                (self._content_mtime < content_mtime_now):
            content = {}
            links = {}
            for name in self._fs_node:
                # Grab the file extension and analyse
                if '.' not in name:
                    continue
                (_, ext) = name.rsplit('.',1)
                if ext.lower() not in ('jpg', 'jpe', 'jpeg', 'gif',
                                        'png', 'tif', 'tiff', 'bmp',):
                    continue

                node = self._fs_node[name]
                if node.is_link:
                    if not os.path.exists(node.abs_target):
                        # Broken link
                        continue

                    # Symbolic link, get the destination relative to the
                    # root directory.
                    (gallery_name, photo_name) = os.path.split(
                            os.path.relpath(node.abs_target,
                                self._fs_node.parent.abs_path))

                    # Check the gallery actually exists!
                    if not gallery_name:
                        # In the root itself, not valid!
                        continue

                    if os.path.sep in gallery_name:
                        # Deeply nested or above the root, not valid!
                        continue

                    if gallery_name == os.path.pardir:
                        # In directory above root, not valid!
                        continue

                    # All good
                    links[name] = (gallery_name, photo_name)
                    continue

                # This is a photo.
                content[name] = Photo(self, self._fs_node[name])
            self._links = links
            self._content = OrderedDict(sorted(content.items(),
                key=lambda i : i[0]))
            self._content_mtime = content_mtime_now
            self._content_prev_order = None
            self._content_next_order = None
        return self._content

    def _get_prev(self, name):
        if self._content_prev_order is None:
            content = list(self._get_content().keys())
            self._content_prev_order = dict(zip(
                content[1:], content[:-1]))
        return self._content_prev_order[name]

    def _get_next(self, name):
        if self._content_next_order is None:
            content = list(self._get_content().keys())
            self._content_next_order = dict(zip(
                content[:-1], content[1:]))
        return self._content_next_order[name]

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

    @property
    def first(self):
        return list(self._get_content().keys())[0]

    @property
    def last(self):
        return list(self._get_content().keys())[-1]

    @property
    def meta(self):
        return {
                'name': self.name,
                'title': self.title,
                'desc': self.desc,
                'content': list(self.keys())
        }

    # Collection services
    @property
    def _meta_cache(self):
        return self._collection()._meta_cache

    @property
    def _fs_cache(self):
        return self._collection()._fs_cache

    @property
    def _resizer_pool(self):
        return self._collection()._resizer_pool
