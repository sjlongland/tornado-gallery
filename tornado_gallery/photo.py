#!/usr/bin/env python

from weakref import ref
from tornado.gen import coroutine, Return

try:
    import piexif
except ImportError:
    pass


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

            try:
                exif = piexif.load(self._fs_node.abs_path,
                        key_is_name=True)
            except:
                # Maybe EXIF is not supported?  Or maybe piexif isn't loaded.
                exif = None

            if exif is not None:
                # Decode the EXIF data¸ stripping the blobs
                # This is an ugly workaround to
                # https://github.com/hMatoba/Piexif/issues/58
                def _strip_blobs(obj):
                    if isinstance(obj, bytes):
                        return obj.decode('UTF-8')
                    if isinstance(obj, dict):
                        out = {}
                        for key, value in obj.items():
                            try:
                                out[key] = _strip_blobs(value)
                            except:
                                pass
                        return out
                    if isinstance(obj, list) or isinstance(obj, tuple):
                        out = []
                        for value in obj:
                            try:
                                out.append(_strip_blobs(value))
                            except:
                                pass
                        return out
                    return obj
                self._properties['exif'] = _strip_blobs(exif)

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
        if self.orientation in (5, 6, 7, 8):
            return self._get_property('height')
        return self._get_property('width')

    @property
    def height(self):
        if self.orientation in (5, 6, 7, 8):
            return self._get_property('width')
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
        orig_width = self.width
        orig_height = self.height
        if not width:
            if height:
                width = int((height * self.ratio) + 0.5)
            else:
                width = orig_width

        if not height:
            if width:
                height = int((width / self.ratio) + 0.5)
            else:
                height = orig_height

        return (width, height)

    def get_rel_uri(self, width=720, height=None, rotation=0.0, quality=60.0,
            img_format=None):
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
        uri += '/%f' % float(quality or 60.0)

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
    def get_resized(self, width=None, height=None, quality=60,
            rotation=0.0, img_format=None):
        result = yield self._gallery().get_resized(
                photo=self.name, width=width, height=height,
                quality=quality, rotation=rotation,
                img_format=img_format,
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
