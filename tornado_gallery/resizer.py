from tornado.gen import coroutine, Future, Return
from tornado.ioloop import IOLoop
from PIL import Image
from sys import exc_info
from io import BytesIO
from enum import Enum
from tornado.locks import Semaphore
import magic
import logging

import multiprocessing
import multiprocessing.pool
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


class ResizerPool(object):
    def __init__(self, root_dir_node, cache_subdir, num_proc=None, log=None):
        if log is None:
            log = logging.getLogger(self.__class__.__module__)

        if num_proc is None:
            num_proc = multiprocessing.cpu_count()

        self._log = log
        self._pool = multiprocessing.pool.ThreadPool(num_proc)
        self._fs_node = root_dir_node
        self._cache_node = self._fs_node[cache_subdir]
        self._mutexes = WeakValueDictionary()

    @coroutine
    def get_resized(self, gallery, photo,
            width=None, height=None, quality=60,
            rotation=0.0, img_format=None):
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

        # Do we need to compute full dimensions?
        if (width is None) or (height is None):
            raw_width, raw_height = yield self.get_dimensions(gallery, photo)
            ratio = float(raw_width) / float(raw_height)

            if (ratio >= 1.0) or (height is None):
                # Fit to width
                height = int(width / ratio)
            else:
                # Fit to height
                width = int(height * ratio)

            self._log.debug('%s/%s target dimensions %d by %d',
                    gallery, photo, width, height)

        # Locate the lock for this photo.
        mutex_key = (gallery, photo, width, height, quality, rotation,
                img_format)
        try:
            mutex = self._mutexes[mutex_key]
        except KeyError:
            mutex = Semaphore(1)
            self._mutexes[mutex_key] = mutex

        resize_args = (gallery, photo, width, height, quality,
                    rotation, img_format.value)
        try:
            self._log.debug('%s/%s waiting for mutex',
                    gallery, photo)
            yield mutex.acquire()

            # We have the semaphore, call our resize routine.
            future = Future()
            self._log.debug('%s/%s retrieving resized image (args=%s)',
                    gallery, photo, resize_args)
            self._pool.apply_async(
                func=self._do_resize,
                args=resize_args,
                callback=future.set_result,
                error_callback=future.set_exception)
            (img_format, file_name, file_data) = yield future
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

    def _do_resize(self, gallery, photo, width, height, quality,
            rotation, img_format):
        """
        Perform a resize of the image, and return the result.
        """
        img_format = ImageFormat(img_format)

        log = self._log.getChild('%s/%s@%dx%d' \
                % (gallery, photo, width, height))
        log.debug('Resizing photo; quality %f, '\
                'rotation %f, format %s',
                quality, rotation, img_format.name)

        # Determine the path to the original file.
        orig_node = self._fs_node.join_node(gallery, photo)

        # Determine the name of the cache file.
        cache_name = self._cache_node.join(
                ('%(gallery)s-%(photo)s-'\
                '%(width)dx%(height)d-'\
                '%(quality)d-%(rotation).6f.%(ext)s') % {
                    'gallery': gallery,
                    'photo': photo,
                    'width': width,
                    'height': height,
                    'quality': quality,
                    'rotation': rotation,
                    'ext': img_format.ext
                })
        log.debug('Resized file: %s', cache_name)

        # Do we have this file?
        cache_path = self._cache_node.join(cache_name)
        try:
            cache_node = self._cache_node[cache_name]
            # We do, is it same age/newer and non-zero sized?
            if (cache_node.stat.st_size > 0) and \
                    (cache_node.stat.st_mtime >= orig_node.stat.st_mtime):
                # This will do.  Re-use the existing file.
                log.info('Returning cached result')
                return (img_format, cache_name,
                        open(cache_node.abs_path, 'rb').read())
        except KeyError:
            # We do not, press on!
            pass

        # Resize!
        orig = Image.open(open(orig_node.abs_path,'rb'))
        resized = orig.resize((width, height), Image.LANCZOS)

        # Write out the new file.
        resized.save(open(cache_path,'wb'), img_format.pil_fmt)

        # Return to caller
        log.info('Returning resized result')
        return (img_format, cache_name,
                open(cache_path, 'rb').read())

    def get_properties(self, gallery, photo):
        """
        Return the raw properties of the photo.
        """

        img_node = self._fs_node.join_node(gallery, photo)
        img = Image.open(open(img_node.abs_path,'rb'))
        (width, height) = img.size
        return dict(width=width, height=height)
