from tornado.gen import coroutine, Return
from tornado.ioloop import IOLoop
from PIL import Image
from sys import exc_info
from io import BytesIO
from enum import Enum
from tornado.locks import Semaphore
import magic
import logging

try:
    import piexif
except ImportError:
    pass

from os import makedirs

import multiprocessing
from .pool import WorkerPool
from weakref import WeakValueDictionary

# Filename extension mappings
_FORMAT_EXT = {
        'image/jpeg':   'jpg',
        'image/png':    'png',
        'image/gif':    'gif'
}

# PIL formats
_FORMAT_PIL = {
        'image/jpeg':   'JPEG',
        'image/png':    'PNG',
        'image/gif':    'GIF'
}

class ImageFormat(Enum):
    JPEG    = 'image/jpeg'
    PNG     = 'image/png'
    GIF     = 'image/gif'

    @property
    def ext(self):
        return _FORMAT_EXT[self.value]

    @property
    def pil_fmt(self):
        return _FORMAT_PIL[self.value]


def calc_dimensions(raw_width, raw_height, width=None, height=None):
    """
    Given the raw dimensions of a photo, and optional target dimensions,
    return the dimensions of a photo that will fit in the target dimensions
    whilst respecting the aspect ratio of the photo.
    """
    # Simple case, neither given, do not scale.
    if (width is None) and (height is None):
        return (raw_width, raw_height)

    # Compute aspect ratio
    ratio = float(raw_width) / float(raw_height)

    # Simple case: one dimension only given
    if width is None:
        # Scale by height only.
        return (int(height * ratio), height)
    elif height is None:
        # Scale by width only.
        return (width, int(width / ratio))
    else:
        # Both dimensions, pick the one that fits!
        scaled_height = int(width / ratio)
        scaled_width = int(height * ratio)

        if scaled_width > width:
            # Scale-by-height is too wide, scale-by-width.
            return (width, scaled_height)
        else:
            # Scale-by-width is too tall, scale-by-height.
            return (scaled_width, height)


class ResizerPool(object):
    def __init__(self, root_dir_node, cache_subdir, num_proc=None, log=None):
        if log is None:
            log = logging.getLogger(self.__class__.__module__)

        if num_proc is None:
            num_proc = multiprocessing.cpu_count()

        self._log = log
        self._pool = WorkerPool(num_proc)
        self._fs_node = root_dir_node
        self._cache_node = self._fs_node[cache_subdir]
        self._mutexes = WeakValueDictionary()

    @coroutine
    def get_resized(self, gallery, photo,
            width=None, height=None, quality=60,
            rotation=0.0, img_format=None, orientation=0):
        """
        Retrieve the given photo in a resized format.
        """
        # Determine the path to the original file.
        orig_node = self._fs_node.join_node(gallery, photo)

        if img_format is None:
            # Detect from original file and quality setting.
            with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
                mime_type = m.id_filename(orig_node.abs_path)
                self._log.debug('%s/%s detected format %s',
                        gallery, photo, mime_type)
                if mime_type == 'image/gif':
                    img_format = ImageFormat.GIF
                else:
                    if quality == 100:
                        # Assume PNG
                        img_format = ImageFormat.PNG
                    else:
                        # Assume JPEG
                        img_format = ImageFormat.JPEG
        else:
            # Use the format given by the user
            img_format = ImageFormat(img_format)

        self._log.debug('%s/%s using %s format',
                gallery, photo, img_format.name)

        # Sanitise dimensions given by user.
        width, height = self.get_dimensions(gallery, photo, width, height)
        self._log.debug('%s/%s target dimensions %d by %d',
                gallery, photo, width, height)

        # Determine where the file would be cached
        (cache_dir, cache_name) = self._get_cache_name(gallery, photo,
                width,height, quality, rotation, img_format)

        # Do we have this file?
        data = self._read_cache(orig_node, cache_dir, cache_name)
        if data is not None:
            raise Return((img_format, cache_name, data))

        # Locate the lock for this photo.
        mutex_key = (gallery, photo, width, height, quality, rotation,
                img_format)
        try:
            mutex = self._mutexes[mutex_key]
        except KeyError:
            mutex = Semaphore(1)
            self._mutexes[mutex_key] = mutex

        resize_args = (gallery, photo, width, height, quality,
                    rotation, img_format.value, orientation)
        try:
            self._log.debug('%s/%s waiting for mutex',
                    gallery, photo)
            yield mutex.acquire()

            # We have the semaphore, call our resize routine.
            self._log.debug('%s/%s retrieving resized image (args=%s)',
                    gallery, photo, resize_args)
            (img_format, file_name, file_data) = yield self._pool.apply(
                func=self._do_resize,
                args=resize_args)
            raise Return((img_format, file_name, file_data))
        except Return:
            raise
        except:
            self._log.exception('Error resizing photo; gallery: %s, photo: %s, '\
                    'width: %d, height: %d, quality: %f, rotation: %f, format: %s',
                    gallery, photo, width, height, quality, rotation, img_format)
            raise
        finally:
            mutex.release()

    def _get_cache_name(self, gallery, photo, width, height, quality,
            rotation, img_format):
        """
        Determine what the name of a cached resized image would be.
        """
        # Determine the name of the cache file.
        photo_noext = '.'.join(photo.split('.')[:-1])
        cache_name = ('%(gallery)s-%(photo)s-'\
                '%(width)dx%(height)d-'\
                '%(quality)d-%(rotation).6f.%(ext)s') % {
                    'gallery': gallery,
                    'photo': photo_noext,
                    'width': width,
                    'height': height,
                    'quality': quality,
                    'rotation': rotation,
                    'ext': img_format.ext
                }
        cache_dir = self._cache_node.join(gallery, photo_noext)
        return (cache_dir, cache_name)

    def _read_cache(self, orig_node, cache_dir, cache_name):
        # Do we have this file now?
        cache_path = self._cache_node.join(cache_dir, cache_name)
        try:
            cache_node = self._cache_node[cache_path]
            # We do, is it same age/newer and non-zero sized?
            if (cache_node.stat.st_size > 0) and \
                    (cache_node.stat.st_mtime >= orig_node.stat.st_mtime):
                # This will do.  Re-use the existing file.
                return open(cache_node.abs_path, 'rb').read()
        except KeyError:
            # We do not, press on!
            pass

    def _do_resize(self, gallery, photo, width, height, quality,
            rotation, img_format, orientation):
        """
        Perform a resize of the image, and return the result.
        """
        img_format = ImageFormat(img_format)
        (cache_dir, cache_name) = self._get_cache_name(gallery, photo,
                width,height, quality, rotation, img_format)

        log = self._log.getChild('%s/%s@%dx%d' \
                % (gallery, photo, width, height))
        log.debug('Resizing photo; quality %f, '\
                'rotation %f, format %s, orientation %s; save as %s in %s',
                quality, rotation, img_format.name, orientation,
                cache_name, cache_dir)

        # Determine the path to the original file.
        orig_node = self._fs_node.join_node(gallery, photo)

        # Ensure the directory exists
        makedirs(cache_dir, exist_ok=True)

        # Do we have this file now?
        data = self._read_cache(orig_node, cache_dir, cache_name)
        if data is not None:
            return (img_format, cache_name, data)

        # Open the image
        img = Image.open(open(orig_node.abs_path,'rb'))

        # Credit: http://piexif.readthedocs.io/en/stable/sample.html
        if orientation == 2:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            img = img.transpose(Image.ROTATE_180)
        elif orientation == 4:
            img = img.transpose(Image.ROTATE_180).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 5:
            img = img.transpose(Image.ROTATE_270).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 6:
            img = img.transpose(Image.ROTATE_270)
        elif orientation == 7:
            img = img.transpose(Image.ROTATE_90).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 8:
            img = img.transpose(Image.ROTATE_90)

        # Rotate if asked:
        if rotation != 0:
            img = img.rotate(rotation, expand=1)

        # Resize!
        img = img.resize((width, height), Image.LANCZOS)

        # Convert to RGB colourspace if not GIF
        if img_format != ImageFormat.GIF:
            img = img.convert('RGB')

        # Write out the new file.
        cache_path = self._cache_node.join(cache_dir, cache_name)
        img.save(open(cache_path,'wb'), img_format.pil_fmt)

        # Return to caller
        log.info('Returning resized result')
        return (img_format, cache_name,
                open(cache_path, 'rb').read())

    def get_dimensions(self, gallery, photo, width=None, height=None):
        img_node = self._fs_node.join_node(gallery, photo)
        img = Image.open(open(img_node.abs_path,'rb'))

        if (width is None) and (height is None):
            return img.size

        return calc_dimensions(*(img.size + (width, height)))

    def get_properties(self, gallery, photo):
        """
        Return the raw properties of the photo.
        """
        log = self._log.getChild('%s/%s' % (gallery, photo))
        img_node = self._fs_node.join_node(gallery, photo)
        (width, height) = self.get_dimensions(gallery, photo)
        meta = dict(width=width, height=height)

        log.debug('Raw dimensions %dx%d', width, height)

        try:
            exif = piexif.load(img_node.abs_path,
                    key_is_name=True)
            log.debug('Loaded EXIF data')
        except:
            # Maybe EXIF is not supported?  Or maybe piexif isn't loaded.
            exif = None
            log.debug('No EXIF data available', exc_info=1)

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
            meta['exif'] = _strip_blobs(exif)

            try:
                if meta['exif']['0th']['Orientation'] in (5, 6, 7, 8):
                    log.debug('Swapping width/height due to orientation')
                    meta['height'] = width
                    meta['width'] = height
            except KeyError:
                pass

        return meta
