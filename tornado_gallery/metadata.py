#!/usr/bin/env python

from time import time
from .cache import Cache
from cachefs.node import Node


class MetadataFile(object):
    """
    A representation of a metadata file.
    """
    def __init__(self, fs_node):
        self._fs_node = fs_node
        self._last_mtime = 0
        self._root_data = None
        self._children_data = None

    def _refresh(self):
        meta_mtime = self._fs_node.stat.st_mtime
        if meta_mtime > self._last_mtime:
            child = None
            root_data = {}
            children_data = {}
            for line in open(self._fs_node.abs_path, 'rt'):
                (key, value) = line.split('\t', 1)
                if key.startswith('.'):
                    # Either belongs to the root, or the last child.
                    if child is None:
                        dest = root_data
                    else:
                        dest = children_data.setdefault(child, {})
                else:
                    # Name of a child; anything starting with . here
                    # now belongs to the child.
                    dest = root_data
                    child = key

                if key in dest:
                    dest[key] += value
                else:
                    dest[key] = value

            self._root_data = root_data
            self._children_data = children_data
            self._last_mtime = meta_mtime

    def __getitem__(self, key):
        # Refresh metadata if needed
        self._refresh()

        # If key is a tuple, then it names a specific child.
        if isinstance(key, tuple):
            (child, key) = key
        else:
            # We are referencing the root
            child = None

        if child is None:
            return self._root_data[key]
        else:
            return self._children_data[child][key]


class MetadataCache(Cache):
    """
    Store the metadata for lots of files and keep them cached.
    """

    def __init__(self, fs_cache, cache_duration=300.0):
        super(MetadataCache, self).__init__(cache_duration=cache_duration)
        self._fs_cache = fs_cache

    def _fetch(self, filename):
        return MetadataFile(self._fs_cache[filename])

    def __getitem__(self, filename):
        if isinstance(filename, Node):
            filename = node.abs_path
        return super(MetadataCache, self).__getitem__(filename)
