#!/usr/bin/env python

from weakref import ref


class Photo(object):
    """
    Representation of a photo in a gallery.
    """

    def __init__(self, gallery, fs_node):
        self._gallery = ref(gallery)
        self._fs_node = fs_node

    @property
    def name(self):
        return self._fs_node.base_name

    @property
    def annotation(self):
        try:
            return self._meta_node['.annotation']
        except KeyError:
            try:
                return self._gallery()._meta[self._fs_node.basename]
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
            return self._gallery._meta[self.name, key]

        return self._gallery()._meta_cache[meta][key]
