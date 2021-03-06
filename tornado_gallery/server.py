#!/usr/bin/env python

import argparse
import logging
import uuid
import datetime
import json
import os.path


from tornado.web import Application, RequestHandler, \
        RedirectHandler, MissingArgumentError, StaticFileHandler
from tornado.httpclient import AsyncHTTPClient, HTTPError
from tornado.httpserver import HTTPServer
from tornado.locks import Semaphore
from tornado.gen import coroutine, TimeoutError
from tornado.ioloop import IOLoop


from .gallery import GalleryCollection, CACHE_DIR_NAME
from .photo import DEFAULT_WIDTH, DEFAULT_HEIGHT, \
        DEFAULT_QUALITY, DEFAULT_ROTATION


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
        self.render('index.thtml',
                site_name=self.application._site_name or \
                        '%s Galleries' % (self.request.host),
                static_uri=self.application._static_uri,
                site_uri=self.application._site_uri,
                page_query=self.request.query,
                galleries=list(self.application._collection.values())
        )


class GalleryHandler(RequestHandler):
    def get(self, gallery_name):
        gallery = self.application._collection[gallery_name]

        self.set_status(200)
        if bool(self.get_query_argument('generate', False)):
            self.render('generator.thtml',
                    static_uri=self.application._static_uri,
                    site_uri=self.application._site_uri,
                    page_query=self.request.query,
                    gallery=gallery
            )
            return

        self.render('gallery.thtml',
                site_name=self.application._site_name or \
                        '%s Galleries' % (self.request.host),
                static_uri=self.application._static_uri,
                site_uri=self.application._site_uri,
                page_query=self.request.query,
                gallery=gallery,
                photos=list(gallery.values())
        )


class GalleryMetaHandler(RequestHandler):
    @coroutine
    def get(self, gallery_name):
        gallery = self.application._collection[gallery_name]

        self.set_status(200)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(gallery.meta))


class ThumbnailHandler(RequestHandler):
    def get(self, gallery_name, photo_name):
        gallery = self.application._collection[gallery_name]
        photo = gallery[photo_name]

        self.redirect(
                ('%(site)s/%(gallery)s/%(photo)s/%(width)dx%(height)d'\
                 '@%(rotation)f/%(quality)d/jpeg') % {
                     'site': self.application._site_uri,
                     'gallery': gallery.name,
                     'photo': photo.name,
                     'width': photo.thumbwidth,
                     'height': photo.thumbheight,
                     'rotation': 0,
                     'quality': 25,
                 })


class PhotoHandler(RequestHandler):
    @coroutine
    def get(self, gallery_name, photo_name, width=None, height=None, rotation=None,
            quality=None, img_format=None):
        gallery = self.application._collection[gallery_name]
        photo = gallery[photo_name]

        if (width is not None) and (width != '-'):
            width = int(width or 0)
        else:
            width = None

        if (height is not None) and (height != '-'):
            height = int(height or 0)
        else:
            height = None

        (width, height) = photo.get_fit_size(width, height)

        if img_format is not None:
            img_format = 'image/%s' % img_format

        (img_format, cache_name, img_data) = \
                yield photo.get_resized(
                        width=width,
                        height=height,
                        quality=float(quality or 60.0),
                        rotation=float(rotation or 0.0),
                        img_format=img_format)
        self.set_status(200)
        self.set_header('Content-Type', img_format.value)
        self.write(img_data)


class PhotoMetaHandler(RequestHandler):
    @coroutine
    def get(self, gallery_name, photo_name):
        gallery = self.application._collection[gallery_name]
        photo = gallery[photo_name]

        # Figure out view width/height
        width=self.get_query_argument('width',
                min(photo.width, DEFAULT_WIDTH))
        height=self.get_query_argument('height',
                min(photo.height, DEFAULT_HEIGHT))

        if width:
            width = int(width)
        else:
            width = None

        if height:
            height = int(height)
        else:
            height = None

        (img_width, img_height) = photo.get_fit_size(width, height)

        self.set_status(200)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({
            'gallery': gallery.name,
            'photo': photo.meta,
            'src': self.application._site_uri + '/' + photo.get_rel_uri(
                img_width, img_height,
                             float(self.get_query_argument(
                                'rotation', DEFAULT_ROTATION)),
                             float(self.get_query_argument(
                                'quality', DEFAULT_QUALITY)),
                             self.get_query_argument('format', None)),
            'user_size': {
                'width': width,
                'height': height,
            },
            'view_size': {
                'width': img_width,
                'height': img_height
            }
        }))


class PhotoPageHandler(RequestHandler):
    @coroutine
    def get(self, gallery_name, photo_name):
        gallery = self.application._collection[gallery_name]
        photo = gallery[photo_name]

        # Figure out view width/height
        width=self.get_query_argument('width',
                min(photo.width, DEFAULT_WIDTH))
        height=self.get_query_argument('height',
                min(photo.height, DEFAULT_HEIGHT))

        if width:
            width = int(width)
        else:
            width = None

        if height:
            height = int(height)
        else:
            height = None

        (img_width, img_height) = photo.get_fit_size(width, height)

        show_photo = self.get_query_argument('show', False) == 'on'
        if show_photo:
            self.redirect(
                    ('%s/%s') % (
                         self.application._site_uri,
                         photo.get_rel_uri(
                             img_width, img_height,
                             float(self.get_query_argument(
                                'rotation', DEFAULT_ROTATION)),
                             float(self.get_query_argument(
                                'quality', DEFAULT_QUALITY)),
                             self.get_query_argument('format', None)
                         )
                     )
            )
            return

        self.set_status(200)
        self.render('photo.thtml',
                site_name=self.application._site_name or \
                        '%s Galleries' % (self.request.host),
                static_uri=self.application._static_uri,
                site_uri=self.application._site_uri,
                page_query=self.request.query,
                gallery=gallery,
                photo=photo,
                width=img_width,
                height=img_height,
                settings={
                    'width': width,
                    'height': height,
                    'quality': self.get_query_argument(
                        'quality', DEFAULT_QUALITY),
                    'rotation': self.get_query_argument(
                        'rotation', DEFAULT_ROTATION),
                    'img_format': self.get_query_argument('format', None),
                }
        )


class GalleryApp(Application):
    def __init__(self, root_dir, static_uri, static_path,
            site_name, site_uri,
            cache_subdir=CACHE_DIR_NAME,
            num_proc=None, cache_expiry=300.0,
            cache_stat_expiry=1.0, **kwargs):
        self._static_uri = static_uri[:-1] if static_uri.endswith('/') \
                            else static_uri
        self._site_name = site_name
        self._site_uri = site_uri
        self._collection = GalleryCollection(
                root_dir=root_dir,
                cache_subdir=cache_subdir,
                num_proc=num_proc, cache_expiry=cache_expiry,
                cache_stat_expiry=cache_stat_expiry)
        super(GalleryApp, self).__init__([
            (r"/.debug", DebugHandler),
            (r"/([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+\.[a-zA-Z]+)/(\d+|-)x(\d+|-)(?:@(\d*\.?\d*))?(?:/(\d*\.?\d*))?(?:/([a-z\-]+))?",
                PhotoHandler),
            (r"/([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+\.[a-zA-Z]+)/thumb.jpg",
                ThumbnailHandler),
            (r"/([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+\.[a-zA-Z]+)(?:/?[a-z]*\.html)?",
                PhotoPageHandler),
            (r"/meta/([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+\.[a-zA-Z]+)",
                PhotoMetaHandler),
            (r"/([a-zA-Z0-9_\-]+)/?", GalleryHandler),
            (r"/meta/([a-zA-Z0-9_\-]+)",
                GalleryMetaHandler),
            (r"/raw/([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+\.[a-zA-Z]+)",
                StaticFileHandler, {"path": root_dir}),
            (r"/", RootHandler),
        ],
        static_url_prefix=static_uri,
        static_path=static_path,
        **kwargs)


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
    parser.add_argument('--template-path', dest='template_path', type=str,
            help='Directory containing template files', default=os.path.realpath(
                os.path.join(os.path.dirname(__file__), 'static')))
    parser.add_argument('--site-name', dest='site_name', type=str,
            help='Photo Galleries')
    parser.add_argument('--site-uri', dest='site_uri', type=str,
            help='Site URI', default='')
    parser.add_argument('--static-uri', dest='static_uri', type=str,
            help='Static resource URI', default='/static/')
    parser.add_argument('--static-path', dest='static_path', type=str,
            help='Static resource path', default=os.path.realpath(
                os.path.join(os.path.dirname(__file__), 'static')))

    args = parser.parse_args(*args, **kwargs)

    # Start logging
    logging.basicConfig(level=args.log_level,
            format='%(asctime)s %(levelname)10s '\
                    '%(name)16s %(process)d/%(threadName)s: %(message)s')

    application = GalleryApp(root_dir=args.root_dir,
            static_uri=args.static_uri,
            static_path=args.static_path,
            site_name=args.site_name,
            site_uri=args.site_uri,
            template_path=args.template_path,
            num_proc=args.process_count)
    http_server = HTTPServer(application)
    http_server.listen(port=args.listen_port, address=args.listen_address)
    IOLoop.current().start()

if __name__ == '__main__':
    main()
