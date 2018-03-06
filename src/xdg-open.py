#!/usr/bin/python3
#
# xdg-open: Wrapper of xdg-open for Dropbox, to fix "Open Dropbox folder"
#
# Copyright (C) 2018 Endless Mobile, Inc.
# Authors:
#  Mario Sanchez Prada <mario@endlessm.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import argparse
import logging
import portallauncher
import sys

from gi.repository import GLib


def done_callback(mainloop):
   mainloop.quit()


def open_url_on_idle(url, mainloop):
   launcher = portallauncher.PortalLauncher(url, done_callback, mainloop)
   launcher.run()


if __name__ == '__main__':
   parser = argparse.ArgumentParser(prog='xdg-open',
                                    description='Dropbox-specific version of xdg-open, that'
                                    'manually deals with the OpenURI vs OpenFile methods so'
                                    'that we can keep working in all the possible 4 scenarios'
                                    'derived of having either the old or new version of the'
                                    'com.endless.Platform runtime and the portals isntalled.')
   parser.add_argument('--debug', dest='debug', action='store_true')
   parser.add_argument('target', action='store', help='{ file | URL }')

   parsed_args = parser.parse_args()
   if parsed_args.debug:
      logging.basicConfig(level=logging.INFO)

   mainloop = GLib.MainLoop()
   GLib.idle_add(open_url_on_idle, parsed_args.target, mainloop)
   mainloop.run()
   sys.exit(0)
