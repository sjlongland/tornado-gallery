#!/usr/bin/env python

from time import time


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


class MetadataCache(object):
    """
    Store the metadata for lots of files and keep them cached.
    """

    def __init__(self, fs_cache, cache_duration=300.0):
        self._cache_duration = float(cache_duration)
        self._file = {}
        self._fs_cache = fs_cache

    def __getitem__(self, filename):
        """
        Retrieve the content of the given metadata file.
        """
        node = self._fs_cache[filename]

        try:
            # Refresh expiry before returning.
            return self._store_file(node)
        except KeyError:
            pass

        # Not in cache, try to read it in.
        return self._store_file(node)

    def _store_file(self, node):
        path = node.abs_path
        if path in self._file:
            (_, meta) = self._file[path]
        else:
            meta = MetadataFile(node)

        self._file[path] = (time() + self._cache_duration, meta)
        return meta

    def purge(self):
        """
        Purge the cache of expired content.
        """
        for filename, (expiry, _) in list(self._file.items()):
            if expiry < time():
                self._file.pop(filename, None)
