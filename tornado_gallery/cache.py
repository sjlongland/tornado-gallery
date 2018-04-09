#!/usr/bin/env python

from time import time
from collections import Mapping


class Cache(object):
    """
    A key-value cache object that expires entries after a period.
    """

    def __init__(self, cache_duration=300.0):
        self._cache_duration = float(cache_duration)
        self._items = {}

    def __getitem__(self, key):
        """
        Retrieve the content of the given key.
        """
        try:
            (_, value) = self._items[key]
        except KeyError:
            value = self._fetch(key)
        self._items[key] = (time() + self._cache_duration, value)
        return value

    def __iter__(self):
        now = time.time()
        for key, (ex, _) in self._items.item():
            if ex > now:
                yield key

    def __len__(self):
        return len(list(self.__iter__()))

    def purge(self):
        """
        Purge the cache of expired content.
        """
        for key, (expiry, _) in list(self._items.items()):
            if expiry < time():
                self._items.pop(key, None)

    @property
    def next_expiry(self):
        """
        Return the time of the next expiry, if any.
        """
        expiries = [ex for (ex, _) in self._items.values()]
        if len(expiries):
            return min(expiries)
        return None
