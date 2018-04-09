#!/usr/bin/env python

import argparse
import logging
import uuid
import datetime
import pytz
import json

from tornado.web import Application, RequestHandler, \
        RedirectHandler, MissingArgumentError
from tornado.httpclient import AsyncHTTPClient, HTTPError
from tornado.httpserver import HTTPServer
from tornado.locks import Semaphore
from tornado.gen import coroutine, TimeoutError
from tornado.ioloop import IOLoop


from .gallery import GalleryCollection, CACHE_DIR_NAME


class DebugHandler(RequestHandler):
    def get(self):
        self.set_status(200)
        self.set_header('Content-Type', 'text/plain')
        self.write('''Debug handler
-----------------------------------------------------------------------
URI:    %s
Host:   %s
Path:   %s
Query:  %s
Headers:
%s
Body:
%s
''' % (
    self.request.uri,
    self.request.host,
    self.request.path,
    self.request.query,
    '\n'.join([
        '\t%s=%s' % (h, v)
        for h, v
        in self.request.headers.items()
    ]),
    self.request.body
))


class RootHandler(RequestHandler):
    def get(self):
        self.set_status(200)
        self.set_header('Content-Type', 'text/plain')
        self.write('''Root handler
-----------------------------------------------------------------------
''' + '\n'.join([
    '%-24s: %s' % (g.name, g.title)
    for g in self.application._collection.values()
]))


class GalleryHandler(RequestHandler):
    def get(self, gallery_name):
        gallery = self.application._collection[gallery_name]

        self.set_status(200)
        self.set_header('Content-Type', 'text/plain')
        self.write('''Gallery handler
-----------------------------------------------------------------------
''' + '\n'.join([
    '%-24s: %s' % (p.name, p.annotation)
    for p in gallery.values()
]))


class PhotoHandler(RequestHandler):
    @coroutine
    def get(self, gallery_name, photo_name):
        gallery = self.application._collection[gallery_name]
        photo = gallery[photo_name]

        show_photo = self.get_query_argument('show', False) == 'on'
        if show_photo:
            (img_format, cache_name, img_data) = \
                    yield photo.get_resized(
                            width=self.get_query_argument('width', 720),
                            height=self.get_query_argument('height', None),
                            quality=self.get_query_argument('quality', 60.0),
                            rotation=self.get_query_argument('rotation', 0.0),
                            img_format=self.get_query_argument('format', None))
            self.set_status(200)
            self.set_header('Content-Type', img_format.value)
            self.write(img_data)
            return

        self.set_status(200)
        self.set_header('Content-Type', 'text/plain')
        self.write('''Photo handler
-----------------------------------------------------------------------
Photo: %s
Annotation: %s
''' % (photo.name, photo.annotation))


class GalleryApp(Application):
    def __init__(self, root_dir, cache_subdir=CACHE_DIR_NAME,
            num_proc=None, cache_expiry=300.0,
            cache_stat_expiry=1.0):
        self._collection = GalleryCollection(
                root_dir=root_dir,
                cache_subdir=cache_subdir,
                num_proc=num_proc, cache_expiry=cache_expiry,
                cache_stat_expiry=cache_stat_expiry)
        super(GalleryApp, self).__init__([
            (r"/.debug", DebugHandler),
            (r"/([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+\.[a-zA-Z]+)(?:\.html)?",
                PhotoHandler),
            (r"/([a-zA-Z0-9_\-]+)/?", GalleryHandler),
            (r"/", RootHandler),
        ])


def main(*args, **kwargs):
    """
    Console entry point.
    """
    parser = argparse.ArgumentParser(
            description='Tornado Photo Gallery')
    parser.add_argument('--listen-address', dest='listen_address',
            default='', help='Interface address to listen on.')
    parser.add_argument('--listen-port', dest='listen_port', type=int,
            default=3000, help='Port number (TCP) to listen on.')
    parser.add_argument('--log-level', dest='log_level',
            default='INFO', help='Logging level')
    parser.add_argument('--process-count', dest='process_count', type=int,
            default=None, help='Size of image processing pool.')
    parser.add_argument('--root-dir', dest='root_dir', type=str,
            help='Root directory containing photo galleries')

    args = parser.parse_args(*args, **kwargs)

    # Start logging
    logging.basicConfig(level=args.log_level,
            format='%(asctime)s %(levelname)10s '\
                    '%(name)16s %(process)d/%(threadName)s: %(message)s')

    application = GalleryApp(root_dir=args.root_dir)
    http_server = HTTPServer(application)
    http_server.listen(port=args.listen_port, address=args.listen_address)
    IOLoop.current().start()

if __name__ == '__main__':
    main()
