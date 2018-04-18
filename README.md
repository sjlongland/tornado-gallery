Photo gallery built on Tornado/Pillow
=====================================

This is a simple photo gallery application built on
[Tornado](http://tornadoweb.org) and
[Pillow](https://pillow.readthedocs.io/en/5.1.x/).  It is intended to replace
the CGI/ClearSilver based photo gallery application I wrote in C some time
back.

Installation
============

```
$ python setup.py install --user
```

should do what you're after.  Or you can install it system-wide.  Your choice.

Deployment
==========

To deploy you need:

1. A front-end server of some kind to do HTTP/HTTPS termination,
   etc, such as `nginx` or Apache.
2. A root directory where your photo galleries will be kept.
3. A writeable directory within that root called `cache` into which,
   the resized images will be placed on demand.
4. Some supervisor daemon that will launch the server at boot.  `systemd` can
   do this, or for a stand-alone solution, look at `supervisord`.

The photos/galleries themselves need not be writeable by the daemon.  The
daemon process may run as any user you like.

Configure your supervisor daemon to launch the gallery application at boot,
passing in the following arguments:

- Mandatory options:
  - `--root-dir`: *the directory containing your photo galleries*.
  - `--listen-port`; the port number to listen on (default is `8000`)
- Optional:
  - `--listen-address`; the IP address of the listening socket (I suggest `::1`)
  - `--log-level`; the logging level to use (default is `INFO`)
  - `--process-count`; the number of resizer processes to spawn
    (default: CPU count)
  - `--template-path`; the path where customised templates should be loaded form
  - `--static-path`; the directory where static resources are stored in
  - `--static-uri`; the URI where the static resources appear; default is `/static`

Now, point your server's reverse proxy at the port number you specified.

You may want to use your web server to host the `/static` directory by pointing
it at the `/static` sub-directory of the installed package.  e.g. on my Gentoo
system installing it in my home directory, I would point `/static` my server at
`~/.local/lib64/python3.4/site-packages/tornado_gallery-${VERSION}-${PYVER}.egg/tornado_gallery/static/`.

Gallery format
==============

A gallery is a directory with a number of images (in PNG or JPEG format) and a
`info.txt` describing the gallery itself.

`info.txt` has the following format:

```
.title	Title Of Gallery Here
.desc	Description of Gallery Here
```

The key and value *must* be separated by a single tab character.

Individual photos may be annotated two ways.

Annotating photos in `info.txt`
-------------------------------

To annotate photos in `info.txt`, list the photos and their descriptions
separated by a tab:

```
photo1.jpg	Brief Description of photo1
photo2.jpg	Brief Description of photo2
```

Separate annotations
--------------------

The annotations can also be stored in a separate file with the file extension
replaced with `.txt`.  This also lets you set parameters such as default
width/height.  If your photo is named `photo1.jpg`, create a file `photo1.txt`:

```
.annotation	Brief Description of photo1
.description	Further description of photo1
```

Other options that can be given here; `.width` and `.height` set the default
dimensions of the photo.

Customising appearance
======================

The photo gallery look and feel can be changed by specifying your own templates.

Copy the stock templates to a directory, customise, then point `--template-path`
at that directory.  Likewise, static elements such as CSS stylesheets, images
and JavaScript may be customised by copying these to a separate directory and
specifying `--static-path`.
