#!/usr/bin/env python

from os.path import realpath
from time import time


def parse_meta(filename):
    """
    Parse a raw metadata file and return the output.
    """
    return dict([
        line.split('\t',1)
        for line in open(filename, mode='rt')
    ])


class MetadataCache(object):
    """
    Store the metadata for lots of files and keep them cached.
    """

    def __init__(self, cache_duration=300.0, fs_cache=None):
        self._cache_duration = float(cache_duration)
        self._file = {}
        self._fs_cache = None

    def __getitem__(self, filename):
        """
        Retrieve the content of the given metadata file.
        """
        filename = realpath(filename)

        # Retrieve the modification time of the file
        if self._fs_cache is not None:
            mtime_now = self._fs_cache[filename].stat.st_mtime
        else:
            mtime_now = 0

        try:
            (_, mtime_last, data) = self._file[filename]

            if mtime_last == mtime_now:
                # File is still being used, refresh expiry.
                self._store_file(filename, mtime_last, data)
                return data
        except KeyError:
            pass

        # Not in cache, try to read it in.
        data = parse_meta(filename)
        self._store_file(filename, mtime_now, data)
        return data

    def _store_file(self, filename, mtime, data):
        self._file[filename] = (time() + self._cache_duration, mtime, data)

    def purge(self):
        """
        Purge the cache of expired content.
        """
        for filename, (expiry, _, _) in list(self._file.items()):
            if expiry < time():
                self._file.pop(filename, None)
