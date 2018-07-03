# eos-dropbox-app

**DEPRECATED**: This repository has now been deprecated in favour of having
this flatpak application directly built in FlatHub, where development will
continue. See https://github.com/flathub/com.dropbox.Client for details.

## Description

This package is used by EOS to package Dropbox as a flatpak, to provide
the "client side" entry point to the sandboxed application.

## Detailed description

This package provides a launcher script (`eos-dropbox-app`) that will be
pointed from the Exec line in the exported .desktop file so that the file
manager opens in the Dropbox directory when clicking on the app's icon.

As this will be running inside the flatpak's sandbox, it will use the
flatpak's OpenURI portal to communicate with the host and open the URI.

## License

eos-dropbox-app is Copyright (C) 2017 Endless Mobile, Inc. and
is licensed under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of
the License, or (at your option) any later version.

See the COPYING file for the full version of the GNU GPLv2 license
