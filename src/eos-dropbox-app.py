#!/usr/bin/python3
#
# eos-dropbox-app: launcher script to launch Dropbox
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

import argparse
import glob
import json
import logging
import os
import portallauncher
import psutil
import shutil
import sys
import threading


from gi.repository import Gio
from gi.repository import GLib


DROPBOX_AUTOUPDATE_DIR = '~/.dropbox-dist'
DROPBOX_CONFIG = '~/.dropbox/info.json'
DROPBOX_LAUNCHER  = '/app/extra/.dropbox-dist/dropboxd'
DROPBOX_DEFAULT_DIR  = '~/Dropbox'
DROPBOX_DAEMON_NAME  = 'dropbox'


def get_processes_by_name(name):
    "Return a list of processes matching 'name'."
    process_list = []
    for p in psutil.process_iter(attrs=['name']):
        if p.info['name'] == name:
            process_list.append(p)
    return process_list


def find_dropbox_daemon():
    matching_processes = get_processes_by_name(DROPBOX_DAEMON_NAME)
    if len(matching_processes) > 0:
        # There is only one process, so pick the first element in the list
        return matching_processes[0]

    return None


def get_default_dropbox_directory():
    default_dir = os.path.expanduser(DROPBOX_DEFAULT_DIR)

    if os.path.isdir(default_dir):
        return default_dir

    # No 'Dropbox' directory found, our last attempt will be to look for a Dropbox
    # team folder, used in 'business' accounts (e.g. 'Dropbox (Endless Team)')
    team_dir = glob.glob(default_dir + ' (*)')
    if team_dir:
        return team_dir[0]

    # If no Dropbox folder found, that means that the user has not
    # configured Dropbox yet, so there's not much we can do now
    return None


def get_dropbox_directory():
    dropbox_dir = None
    config_path = os.path.expanduser(DROPBOX_CONFIG)

    logging.info("Looking for Dropbox configuration...")
    if not os.path.exists(config_path):
        logging.info("Dropbox configuration not found")
        return None

    with open(config_path, 'r') as config:
        logging.info("Found Dropbox configuration at {}".format(config_path))

        path = None
        account_type = None

        data = config.read()
        try:
            json_data = json.loads(data)
        except ValueError as e:
            logging.warning("Error loading JSON data from {}: {}".format(DROPBOX_CONFIG, str(e)))

        # Search for valid user configuration (containing 'path')
        # and for the type of account (for logging purposes)
        for type_name in json_data:
            if 'path' in json_data[type_name]:
                path = json_data[type_name]['path']
                account_type = type_name
                break

        if path:
            try:
                dropbox_dir = os.path.expanduser(path)
                logging.info("Found configured Dropbox directory at {} ({} account)"
                             .format(dropbox_dir, account_type))
            except KeyError:
                logging.warning("Could not find Dropbox directory in user's configuration")
        else:
            logging.warning("Could not find user's configuration in Dropbox's configuration file")

    if not dropbox_dir:
        logging.warning("Could not find a valid Dropbox directory in the configuration. Falling back to defaults...")
        dropbox_dir = get_default_dropbox_directory()

    return dropbox_dir


class DropboxLauncher():

    def __init__(self):
        self._mainloop = GLib.MainLoop()
        self._config_monitor = None
        self._dir_monitor = None
        self._bus_owner_id = 0
        self._quit_if_name_lost = False

        # Shell script provider by Dropbox as the unified entry
        # point to launch the daemon. (class: psutil.Popen).
        self._launcher = None

        # The actual daemon provided by Dropbox that will take over
        # after the launcher is invoked (class: psutil.Popen).
        self._daemon = None

    def run(self):
        self._try_own_bus_name()
        self._mainloop.run()

    def _try_own_bus_name(self, replace=False):
        if self._bus_owner_id != 0:
            Gio.bus_unown_name(self._bus_owner_id)

        flags = Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT
        if replace:
            flags |= Gio.BusNameOwnerFlags.REPLACE
            self._quit_if_name_lost = True
            logging.info("Trying to own the dropbox dbus name (this time "
                         "replacing existing ones)...")
        else:
            logging.info("Trying to own the dropbox dbus name...")

        self._bus_owner_id = Gio.bus_own_name(Gio.BusType.SESSION,
                                              'com.dropbox.Client',
                                              flags,
                                              None, # Bus Acquired callback
                                              self._name_acquired,
                                              self._name_lost)

    def _name_acquired(self, *args):
        logging.info("No instance of dropbox already running")
        self._quit_if_name_lost = True
        self._launch_dropbox()

    def _name_lost(self, *args):
        if self._quit_if_name_lost:
            logging.info("Lost the DBus name ownership; quitting...")
            self._quit()
            return

        if not get_dropbox_directory():
            logging.info("Another instance of dropbox is already running but no "
                         "Dropbox folder was found; launching the daemon again")
            self._try_own_bus_name(replace=True)
        else:
            logging.info("Another instance of dropbox is already running")
            self._open_dropbox_when_created()

    def _exitOnError(self, message):
        logging.error(message)
        self._quit(1)

    def _quit(self, retcode=0):
        if self._launcher:
            self._launcher.terminate()
        if self._daemon:
            self._daemon.terminate()

        self._mainloop.quit()
        sys.exit(retcode)

    def _directory_handled(self, unused):
        # If we own a launcher or a daemon, it means we are the main
        # instance, and so we need to keep running until it terminates.
        if self._launcher or self._daemon:
            return

        # Dropbox launcher already running as a different process,
        # so we can quit here after having handled the URI request
        logging.info("Not the main launcher instance. Exiting")
        self._quit()

    def _open_dropbox_directory(self):
        directory = get_dropbox_directory()
        logging.info("Attempting to open Dropbox directory at {}...".format(directory))

        if not directory:
            logging.warning("User has not configured Dropbox yet")
            return
        elif not os.path.isdir(directory):
            self._exitOnError("{} is not a directory!".format(directory))

        path = os.path.expanduser(directory)
        launcher = portallauncher.PortalLauncher(path, self._directory_handled, None)
        launcher.run()

    def _launch_dropbox(self):
        self._disable_auto_updates()
        self._launch_dropbox_daemon()
        self._setup_config_monitor()

    def _disable_auto_updates(self):
        # We ship updates to the dropbox app ourselves, so disable
        # them by making the auto-update directory unreadable to
        # prevent weird bugs from happening when mixing versions.
        orig_dir = os.path.expanduser(DROPBOX_AUTOUPDATE_DIR)
        if os.path.exists(orig_dir) and not os.access(orig_dir, os.W_OK):
            logging.info("{} is already unaccessible. Nothing to do".format(orig_dir))
            return

        backup_dir = "{}.backup".format(orig_dir)
        logging.info("Found auto-update directory in {}. Backing it up in {}".format(orig_dir, backup_dir))
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir, ignore_errors=True)
        if os.path.exists(orig_dir):
            shutil.move(orig_dir, backup_dir)

        logging.info("Disabling auto-updates by making {} unwritable".format(orig_dir))
        os.mkdir(orig_dir, mode=0)

    def _setup_config_monitor(self):
        config = Gio.File.new_for_path(os.path.expanduser(os.path.expanduser(DROPBOX_CONFIG)))
        self._config_monitor = config.monitor(Gio.FileMonitorFlags.NONE)
        self._config_monitor.connect('changed', self._on_config_changed)

    def _monitorLauncherThreadFunc(self):
        logging.info("Monitoring launcher with PID {}...".format(self._launcher.pid))
        # We start the launcher from Dropbox, which internally gets
        # replaced by another shell script which ends up launching
        # the actual daemon, so we need to wait for it to finish.
        if self._launcher.is_running():
            self._launcher.wait()
        self._launcher = None

        # Now we can query the process for the actual daemon,
        # which we need to monitor to know when to quit the app.
        self._daemon = find_dropbox_daemon()
        if self._daemon:
            logging.info("Monitoring daemon with PID {}...".format(self._daemon.pid))
            self._daemon.wait()
            self._daemon = None
        else:
            logging.warning("Could not find the PID for the dropbox binary. Ignoring...")

        logging.info("Dropbox background service terminated. Quitting the app...")
        self._quit()

    def _launch_dropbox_daemon(self):
        logging.info("Running Dropbox's launcher at {}...".format(DROPBOX_LAUNCHER))
        try:
            self._launcher = psutil.Popen([DROPBOX_LAUNCHER])
            # Monitor the launcher to make sure we finish the app when needed,
            # but do it from a separate thread since Popen.wait() is blocking.
            thread = threading.Thread(target=self._monitorLauncherThreadFunc)
            thread.start()
        except FileNotFoundError as e:
            self._exitOnError("Can't find launcher script at {}".format(DROPBOX_LAUNCHER))

    def _on_config_changed(self, monitor, file_obj, other_file, event_type):
        logging.info("Config file monitor {}: {}".format(file_obj.get_path(), event_type))
        if event_type != Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            if event_type == Gio.FileMonitorEvent.DELETED and self._dir_monitor:
                self._dir_monitor.cancel()
            return
        self._config_monitor.cancel()
        if os.path.exists(file_obj.get_path()):
            logging.info("Configuration for Dropbox created; opening folder when created...")
            self._open_dropbox_when_created()

    def _open_dropbox_when_created(self):
        dropbox_dir = get_dropbox_directory()
        if dropbox_dir is None:
            logging.warning("No Dropbox folder configured yet. Cannot open or monitor it!")
            return
        if os.path.exists(dropbox_dir):
            self._open_dropbox_directory()
            return
        logging.info("Setting up monitor for folder {}...".format(dropbox_dir))
        dir_obj = Gio.File.new_for_path(dropbox_dir)
        self._dir_monitor = dir_obj.monitor(Gio.FileMonitorFlags.NONE)
        self._dir_monitor.connect('changed', self._on_dir_changed)

    def _on_dir_changed(self, monitor, file_obj, other_file, event_type):
        logging.info("Dropbox dir monitor {}: {}".format(file_obj.get_path(), event_type))
        if event_type != Gio.FileMonitorEvent.CREATED:
            return
        logging.info("Dropbox folder created; opening now...")
        self._open_dropbox_directory()
        self._dir_monitor.cancel()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', dest='debug', action='store_true')

    parsed_args = parser.parse_args()
    if parsed_args.debug:
        logging.basicConfig(level=logging.INFO)

    DropboxLauncher().run()
