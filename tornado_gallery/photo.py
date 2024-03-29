#!/usr/bin/env python

from weakref import ref
from tornado.gen import coroutine, Return
from .resizer import calc_dimensions

try:
    import piexif
except ImportError:
    pass


DEFAULT_WIDTH = 720
DEFAULT_HEIGHT = 540
DEFAULT_QUALITY = 60.0
DEFAULT_ROTATION = 0.0
THUMB_SIZE = 100


class Photo(object):
    """
    Representation of a photo in a gallery.
    """

    def __init__(self, gallery, fs_node):
        self._gallery = ref(gallery)
        self._fs_node = fs_node
        self._properties = None
        self._properties_mtime = None

    def _get_property(self, *args):
        file_mtime = self._fs_node.stat.st_mtime
        if (self._properties_mtime is None) or \
                (file_mtime > self._properties_mtime):
            self._properties = self._resizer_pool.get_properties(
                    self._gallery().name,
                    self.name)
            self._properties_mtime = file_mtime

        value = self._properties
        for key in args:
            value = value[key]
        return value

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
    def orientation(self):
        try:
            return self._get_property('exif', '0th', 'Orientation')
        except KeyError:
            return 0

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
    def preferred_quality(self):
        try:
            return self._get_meta('.quality')
        except KeyError:
            return DEFAULT_QUALITY

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
    def meta(self):
        """
        Return all the photo metadata.
        """
        meta = {
                'name': self.name,
                'original_size': {
                    'width': self.width,
                    'height': self.height,
                },
                'ratio': self.ratio,
                'thumbnail_size': {
                    'width': self.thumbwidth,
                    'height': self.thumbheight,
                },
                'preferred_size': {
                    'width': self.preferred_width,
                    'height': self.preferred_height,
                },
                'order': {
                    'prev': self.prev,
                    'next': self.next
                },
        }

        # Display EXIF data if available
        try:
            meta['exif'] = self._get_property('exif')
        except KeyError:
            pass

        return meta

    def get_fit_size(self, width=None, height=None):
        """
        Get the actual size of a photo that fits in the bounding box given.
        """
        return calc_dimensions(self.width, self.height, width, height)

    def get_rel_uri(self, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT,
            rotation=DEFAULT_ROTATION, quality=None, img_format=None):
        """
        Return the URI of the given photo relative to the site URI
        """
        # Base gallery and image name
        uri = '%s/%s' % (self._gallery().name, self.name)

        # Dimensions and orientation
        uri += '/%sx%s' % (width or '-', height or '-')
        if rotation:
            uri += '@%f' % float(rotation)

        # Quality
        uri += '/%f' % float(quality or self.preferred_quality)

        # Format; if given
        if img_format is not None:
            uri += '/%s' % (img_format.rsplit('/',1).lower())

        return uri

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
    def get_resized(self, width=None, height=None, quality=None,
            rotation=0.0, img_format=None):
        result = yield self._gallery().get_resized(
                photo=self.name, width=width, height=height,
                quality=quality or self.preferred_quality,
                rotation=rotation, img_format=img_format,
                orientation=self.orientation)
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
