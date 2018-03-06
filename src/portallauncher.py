#!/usr/bin/python3
#
# portallauncher: Utility to help us deal with the OpenURI vs
# OpenFile methods, so that we can keep working in all the
# possible 4 scenarios derived of having to support running
# with either the old or the new versions of the legacy runtime
# and the xdg-desktop-portal D-Bus interfaces installed.
#
# Copyright (C) 2017 Endless Mobile, Inc.
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

import logging
import os
import sys

from urllib.parse import urlparse

from gi.repository import Gio
from gi.repository import GLib


class PortalLauncher():

   def __init__(self, target, callback=None, data=None):
      # Cache values commonly used
      parsed_url = urlparse(target)
      self._is_local_file = not parsed_url.scheme or parsed_url.scheme == 'file'
      self._path = parsed_url.path
      self._url = parsed_url.geturl()

      self._callback = callback
      self._data = data

      self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
      self._proxy = Gio.DBusProxy.new_sync(self._bus, Gio.DBusProxyFlags.NONE,
                                           None,
                                           'org.freedesktop.portal.Desktop',
                                           '/org/freedesktop/portal/desktop',
                                           'org.freedesktop.portal.OpenURI',
                                           None)

   def run(self):
      handle = None
      if self._is_local_file:
         try:
            logging.info('Detected file/URI pointing to a local path. Using OpenFile method...')
            handle = self._run_open_file_method()
         except GLib.GError as e:
            if not e.matches(Gio.dbus_error_quark(), Gio.DBusError.UNKNOWN_METHOD):
               logging.error("Could not open file at {}: {}".format(self._path, e.message))
               raise

            logging.warning("OpenFile method not available, falling back to OpenURI...")

      # Use OpenURI() for non-file URIs, as well as a fallback mechanism for file://
      # URIs when the OpenFile() method failed, for compatibility with old portals.
      if not handle:
         handle = self._run_open_uri_method()

      if handle:
         # OpenURI methods returns a handle to a 'request object', which stays
         # alive for the duration of the user interaction related to the method
         # call, so we connect to its Response signal to know when it's all over.
         self._bus.signal_subscribe('org.freedesktop.portal.Desktop',
                                    'org.freedesktop.portal.Request',
                                    'Response',
                                    handle,
                                    None,
                                    Gio.DBusSignalFlags.NO_MATCH_RULE,
                                    self._response_received,
                                    self._callback, self._data)
      else:
         logging.warning("Could not get a handle from the OpenURI portal!")

   def _response_received(self, connection, sender, path, interface, signal, params, callback, data):
      (response_code, results) = params.unpack()
      if response_code == 0:
         logging.info("OpenURI portal: success!")
      elif response_code == 1:
         logging.info("OpenURI portal: cancelled by the user")
      elif response_code == 2:
         logging.warning("OpenURI portal: An error happened")

      if callback:
         callback(data)

   def _run_open_file_method(self):
      logging.info("Opening path at {} (method: OpenURI.OpenFile)...".format(self._path))
      try:
         # We need to pass an Unix FD to pass to the OpenFile method
         fd = os.open(self._path, os.O_PATH | os.O_CLOEXEC)
      except FileNotFoundError as e:
         logging.error("Can't find path at {}: {}".format(self._path, e.strerror))
         raise

      result, _out_fd_list = self._proxy.call_with_unix_fd_list_sync('OpenFile',
                                                                     GLib.Variant('(sha{sv})',
                                                                                  ('', 0, None)),
                                                                     Gio.DBusCallFlags.NONE,
                                                                     -1,
                                                                     Gio.UnixFDList.new_from_array([fd]),
                                                                     None)
      handle, = result.unpack()
      return handle

   def _run_open_uri_method(self):
      uri = self._url if not self._is_local_file else 'file://{}'.format(self._path)
      logging.info("Opening URI at {} (method: OpenURI.OpenURI)...".format(uri))

      return self._proxy.OpenURI('(ssa{sv})', '', uri, None)
