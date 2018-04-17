#!/usr/bin/env python

from weakref import ref
from tornado.gen import coroutine, Return


THUMB_SIZE = 100


class Photo(object):
    """
    Representation of a photo in a gallery.
    """

    def __init__(self, gallery, fs_node):
        self._gallery = ref(gallery)
        self._fs_node = fs_node
        self._properties = None
        self._properties_mtime = 0

    def _get_property(self, key=None):
        file_mtime = self._fs_node.stat.st_mtime
        if file_mtime > self._properties_mtime:
            self._properties = self._resizer_pool.get_properties(
                    self._gallery().name,
                    self.name)
            self._properties_mtime = file_mtime
        if key is not None:
            return self._properties[key]
        return self._properties

    @property
    def name(self):
        return self._fs_node.base_name

    @property
    def width(self):
        return self._get_property('width')

    @property
    def height(self):
        return self._get_property('height')

    @property
    def ratio(self):
        return float(self.width)/float(self.height)

    @property
    def thumbwidth(self):
        ratio = self.ratio
        if ratio > 1.0:
            return THUMB_SIZE
        else:
            return int((THUMB_SIZE * ratio) + 0.5)

    @property
    def thumbheight(self):
        ratio = self.ratio
        if ratio > 1.0:
            return int((THUMB_SIZE / ratio) + 0.5)
        else:
            return THUMB_SIZE

    @property
    def annotation(self):
        try:
            return self._get_meta('.annotation')
        except KeyError:
            try:
                return self._gallery()._meta[self._fs_node.base_name]
            except KeyError:
                return None

    @property
    def description(self):
        try:
            return self._get_meta('.description')
        except KeyError:
            return None

    @property
    def preferred_width(self):
        try:
            return self._get_meta('.width')
        except KeyError:
            return None

    @property
    def preferred_height(self):
        try:
            return self._get_meta('.height')
        except KeyError:
            return None

    @property
    def prev(self):
        try:
            return self._gallery()._get_prev(self.name)
        except KeyError:
            pass

    @property
    def next(self):
        try:
            return self._gallery()._get_next(self.name)
        except KeyError:
            pass

    @property
    def _meta_node(self):
        # Return the metadata node for this photo.
        (photo_name, _) = self._fs_node.abs_path.rsplit('.',1)
        return self._gallery()._fs_cache['%s.txt' % photo_name]

    def _get_meta(self, key):
        # Metadata can either be in our own file with the same base name; or
        # part of the gallery's metadata.
        try:
            meta = self._meta_node
        except KeyError:
            # Retrieve from the parent
            return self._gallery()._meta[self.name, key]

        return self._gallery()._meta_cache[meta][key]

    # Gallery services
    @coroutine
    def get_resized(self, width=None, height=None, quality=60,
            rotation=0.0, img_format=None):
        result = yield self._gallery().get_resized(
                photo=self.name, width=width, height=height,
                quality=quality, rotation=rotation, img_format=img_format)
        raise Return(result)

    @property
    def _meta_cache(self):
        return self._gallery()._meta_cache

    @property
    def _fs_cache(self):
        return self._gallery()._fs_cache

    @property
    def _resizer_pool(self):
        return self._gallery()._resizer_pool
