#!/usr/bin/env python
# -*- coding: utf8 -*-
#
# Copyright (C) 2016 Vangelis Tasoulas <vangelis@tasoulas.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# apt-get install python-progressbar python-pgmagick python-wand

import os
import sys
import re
import argparse
import logging
import subprocess
import datetime
import math
import urllib2
import socket
import progressbar
import multiprocessing
import Queue
import threading
import time
import ConfigParser
import pgmagick
from pgmagick import Image as gmImage
from collections import OrderedDict

__all__ = [
    'quick_regexp', 'print_', 'is_number',
    'trim_list', 'split_strip', 'xfrange',
    'executeCommand', 'LOG', 'stitch_osm_tiles',
    'get_physical_cores'
]

# TODO: Add -l -r -t -b for left, right, top, bottom tiles to be downloaded (if the user doesn't want to provide the coordinates)

PROGRAM_NAME = 'stitch-osm-tiles'
VERSION = '1.0.0'
AUTHOR = 'Vangelis Tasoulas'

LOG = logging.getLogger('default.' + __name__)

#----------------------------------------------------------------------
# Define the providers and the layer available by each provider in an ordered dict!
#    Individual layers can override the following parameters: 'tileservers', 'extension', 'zoom_levels'
PROVIDERS = OrderedDict([
    ('Mapquest', {
        'attribution':'Tiles Courtesy of MapQuest',
        'url':'http://www.mapquest.com',
        'tile_servers': [ 'https://{alts:a,b,c,d}.tiles.mapbox.com/v4/{layer}/{z}/{x}/{y}.{ext}?access_token=pk.eyJ1IjoibWFwcXVlc3QiLCJhIjoiY2Q2N2RlMmNhY2NiZTRkMzlmZjJmZDk0NWU0ZGJlNTMifQ.mPRiEubbajc6a5y9ISgydg' ], # The tile servers that serve the tiles for this provider.
        'extension': 'png',     # The default extension support by this provider
        'zoom_levels': '0-18',  # The zoom levels supported by this provider
        'layers': OrderedDict([
            ('mapquest.streets', {
                'desc': 'Default MapQuest Style for US'
            }),
            ('mapquest.satellite', {
                'desc': 'Satellite MapQuest Style for US'
            }),
            ('mapquest.dark', {
                'desc': 'Dark MapQuest Style for US'
            }),
            ('mapquest.streets-mb', {
                'desc': 'Default MapQuest Style for the rest of the world (Non-US)'
            }),
            ('mapquest.satellite-mb', {
                'desc': 'Satellite MapQuest Style for the rest of the world (Non-US)'
            }),
            ('mapquest.dark-mb', {
                'desc': 'Dark MapQuest Style for the rest of the world (Non-US)'
            })
        ])
    }),

    ('Stamen', {
        'attribution':'Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under ODbL',
        'url':'http://maps.stamen.com',
        'tile_servers': [ 'http://{alts:a,b,c,d}.sm.mapstack.stamen.com/{layer}/{z}/{x}/{y}.{ext}' ],
        'extension': 'png',
        'zoom_levels': '0-18',
        'layers': OrderedDict([
            ('toner', {
                'desc': "Toner default"
            }),
            ('toner-hybrid', {'desc': ''}),
            ('toner-labels', {'desc': ''}),
            ('toner-lines', {'desc': ''}),
            ('toner-background', {'desc': ''}),
            ('toner-lite', {'desc': ''}),
            ('watercolor', {'desc': ''})
        ])
    }),

    ('Mapbox', {
        'attribution':'Mapbox, OpenStreeMap',
        'url':'https://www.mapbox.com',
        'tile_servers': [ 'http://{alts:a,b,c,d}.tiles.mapbox.com/v4/{layer}/{z}/{x}/{y}.{ext}?access_token=pk.eyJ1IjoidGF0aWFuYSIsImEiOiJjaWs1bzRiZGQwMDdjcHRrc285bTdwcWU5In0.0EWPVHyjaE9jTzNvOiIO-w' ],
        'extension': 'png',
        'zoom_levels': '0-18',
        'layers': OrderedDict([
            ('mapbox.outdoors', {
                'desc': "Sample: http://api.mapbox.com/v4/mapbox.outdoors.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627"
            }),
            ('mapbox.run-bike-hike', {
                'desc': "Sample: http://api.mapbox.com/v4/mapbox.run-bike-hike.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627"
            }),
            ('mapbox.streets', {
                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.streets.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
            }),
            ('mapbox.streets-basic', {
                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.streets-basic.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
            }),
            ('mapbox.emerald', {
                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.emerald.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
            }),
            ('mapbox.dark', {
                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.dark.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
            }),
            ('mapbox.light', {
                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.light.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
            }),
            ('mapbox.high-contrast', {
                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.high-contrast.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
            }),
            ('mapbox.satellite', {
                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.satellite.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
            }),
#            ('mapbox.streets-satellite', {
#                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.streets-satellite.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
#            }),
            ('mapbox.wheatpaste', {
                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.wheatpaste.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
            }),
            ('mapbox.comic', {
                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.comic.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
            }),
            ('mapbox.pirates', {
                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.pirates.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
            }),
            ('mapbox.pencil', {
                'desc': 'Sample: http://api.mapbox.com/v4/mapbox.pencil.html?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpbTgzcHQxMzAxMHp0eWx4bWQ1ZHN2NGcifQ.WVwjmljKYqKciEZIC3NfLA#14/37.9870/23.6627'
            })
        ])
    }),

    # For more maps of Norway take a look here: https://kartkatalog.geonorge.no
    #                                 and here: https://www.norgeskart.no
    ('Statkart', {
        'attribution':'http://www.kartverket.no/kart/gratis-kartdata/wms-tjenester/',
        'url':'http://www.kartverket.no',
        'tile_servers':['http://opencache.statkart.no/gatekeeper/gk/gk.open_gmaps?layers={layer}&zoom={z}&x={x}&y={y}'],
        'extension': 'png',
        'zoom_levels': '0-17',
        'layers': OrderedDict([
            ('topo2', {
                'desc': 'High Quality Topo Maps of Norway'
            }),
            ('topo2graatone', {
                'desc': 'Same as topo2 in Grayscale'
            }),
            ('toporaster3', {
                'desc': 'High Quality TopoRaster Maps of Norway'
            }),
            ('europa', {
                'desc': 'Main Roads of Whole Europe'
            }),
# The following URL Works with WMTS
#            ('norges_grunnkart', {
#                'desc': 'High Quality Base Maps of Norway',
#                'tile_servers': ['https://gatekeeper2.geonorge.no/BaatGatekeeper/gk/gk.cache_wmts?gkt=3D162D6480FF44742FF6C4E8599E43690FC759A18E1D6DF38DF829231A08590ADB1584C7A1E10204A7002ACA2E9D21402F15CFFEDCBD29AA8D018F0853CD0DA1&SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=norges_grunnkart&STYLE=default&TILEMATRIXSET=EPSG:32633&TILEMATRIX=EPSG:32633:{z}&TILEROW={y}&TILECOL={x}&FORMAT=image/{ext}']
#            }),
            ('norges_grunnkart_graatone', {
                'desc': 'High Quality Base Maps of Norway in Grayscale'
            }),
            ('kartdata2', {
                'desc': 'Only Maps for Norway'
            }),
#            ('fjellskygge', {
#                'desc': 'Mountain shadows'
#            }),
            ('sjo_hovedkart2', {
                'desc': 'Sea Map of Norway'
            }),
            ('sjokartraster', {
                'desc': 'Sea Raster Map of Norway'
            }),
# The following URL Works with WMTS
#            ('Geocache_UTM33_WGS84', {
#                'desc': '',
#                'tile_servers': ['http://services.geodataonline.no/arcgis/rest/services/Geocache_UTM33_WGS84/GeocacheBasis/MapServer/tile/{z}/{y}/{x}'],
#                'extension': 'jpg'
#            })

        ])
    }),

    ('ArcGIS', {
        'attribution':'',
        'url':'http://www.arcgis.com/',
        'tile_servers': ['http://server.arcgisonline.com/ArcGIS/rest/services/{layer}/MapServer/tile/{z}/{y}/{x}'],
        'extension': 'jpg',
        'zoom_levels': '0-17',
        'layers': OrderedDict([
            ('World_Topo_Map', {
                'desc': 'World Topo Map'
            }),
            ('World_Street_Map', {
                'desc': 'World Street Map'
            })
        ])
    })

])

#----------------------------------------------------------------------
def error_and_exit(message):
    """
    Prints the "message" and exits with status 1
    """
    print("\nERROR:\n" + message + "\n")
    exit(1)

#----------------------------------------------------------------------
def print_(value_to_be_printed, print_indent=0, spaces_per_indent=4, endl="\n"):
    """
    This function, among anything else, it will print dictionaries (even nested ones) in a good looking way

    # value_to_be_printed: The only needed argument and it is the
                           text/number/dictionary to be printed
    # print_indent: indentation for the printed text (it is used for
                    nice looking dictionary prints) (default is 0)
    # spaces_per_indent: Defines the number of spaces per indent (default is 4)
    # endl: Defines the end of line character (default is \n)

    More info here:
    http://stackoverflow.com/questions/19473085/create-a-nested-dictionary-for-a-word-python?answertab=active#tab-top
    """

    if(isinstance(value_to_be_printed, dict)):
        for key, value in value_to_be_printed.iteritems():
            if(isinstance(value, dict)):
                print_('{0}{1!r}:'.format(print_indent * spaces_per_indent * ' ', key))
                print_(value, print_indent + 1)
            else:
                print_('{0}{1!r}: {2}'.format(print_indent * spaces_per_indent * ' ', key, value))
    else:
        string = ('{0}{1}{2}'.format(print_indent * spaces_per_indent * ' ', value_to_be_printed, endl))
        sys.stdout.write(string)

#----------------------------------------------------------------------
def trim_list(string_list):
    """
    This function will parse all the elements from a list of strings (string_list),
    and trim leading or trailing white spaces and/or new line characters
    """
    return [s.strip() for s in string_list]

#----------------------------------------------------------------------
def split_strip(string, separator=","):
    """
    splits the given string in 'sep' and trims the whitespaces or new lines

    returns a list of the splitted stripped strings

    If the 'string' is not a string, -1 will be returned
    """
    if(isinstance(string, str)):
        return trim_list(string.split(separator))
    else:
        return -1

#----------------------------------------------------------------------
def xfrange(start = None, stop = None, step = None):
    """ xfrange([start,] stop[, step]) -> generator of floats """
    if step == None:
        step = 1.0

    if stop == None and start != None:
        stop = start
        start = 0.0

    if stop == None and start == None:
        print("At least 'stop' should be passed to this function")
        raise KeyError

    if is_number(start) and is_number(stop) and is_number(step):
        while start < stop:
            # yield returns a generator object
            yield start
            start += float(step)
    else:
        print("Non numeric value. Only numeric values are accepted.")
        raise KeyError

#----------------------------------------------------------------------
def is_number(s, is_int=False):
    """
    If is_int=True, returns True if 's' is a valid integer number (positive or negative)
    If is_int=False, returns True if 's' is a valid float number (positive or negative)
    Returns False if it is not a valid number
    """
    try:
        if is_int:
            int(s)
        else:
            float(s)
        return True
    except ValueError:
        return False

#----------------------------------------------------------------------
def get_physical_cores():
    """
    Returns the number of actual physical cores, in contrast to
    multiprocessing.cpu_count() that return the number of cpu threads.

    If hyperthreading is enabled, multiprocessing.cpu_count() will return
    twice as many cores than what our system actually has
    """

    if sys.platform == "win32":
        # If it is windows, use the multiprocessing because
        # I don't have windows to test the implementation.
        return multiprocessing.cpu_count()
    elif sys.platform == "darwin":
        # If it is OSX, use the multiprocessing because
        # I don't have a MAC to test the implementation.
        return multiprocessing.cpu_count()
    elif sys.platform.startswith('linux'):
        # If it is posix based OS, read /proc/cpuinfo (Linux falls under
        # this case and that's the only supported posix OS for the moment)
        phys_ids_encountered = []
        total_cores = 0
        cmd = executeCommand(['grep', 'physical id\|cpu cores', '/proc/cpuinfo'])
        r = quick_regexp()
        for line_no in xrange(len(cmd.getStdout())):
            if r.search('physical id\s+:\s+(\d+)', cmd.getStdout()[line_no]):
                if not r.groups[0] in phys_ids_encountered:
                    phys_ids_encountered.append(r.groups[0])
                    line_no += 1
                    r.search('cpu cores\s+:\s+(\d+)', cmd.getStdout()[line_no])
                    total_cores += int(r.groups[0])
                else:
                    line_no += 2

    return total_cores

#----------------------------------------------------------------------
def instantiate_threadpool(threadpool_name, threads, worker, args):
    """
    Instantiates a threadpool with 'threads' number 'worker' threads
    with the given 'args'.

    args must be a tuple.
    """

    for i in xrange(threads):
        thread_worker = threading.Thread(target=worker, args=(args))
        thread_worker.setName('{}-{}'.format(threadpool_name, i))
        thread_worker.setDaemon(True)
        thread_worker.start()

#----------------------------------------------------------------------
class quick_regexp(object):
    """
    Quick regular expression class, which can be used directly in if() statements in a perl-like fashion.

    #### Sample code ####
    r = quick_regexp()
    if(r.search('pattern (test) (123)', string)):
        print(r.groups[0]) # Prints 'test'
        print(r.groups[1]) # Prints '123'
    """
    #----------------------------------------------------------------------
    def __init__(self):
        self.groups = None
        self.matched = False

    #----------------------------------------------------------------------
    def search(self, pattern, string, flags=0):
        match = re.search(pattern, string, flags)
        if match:
            self.matched = True
            if(match.groups()):
                self.groups = re.search(pattern, string, flags).groups()
            else:
                self.groups = True
        else:
            self.matched = False
            self.groups = None

        return self.matched

#----------------------------------------------------------------------
class executeCommand(object):
    """
    Custom class to execute a shell command and
    provide to the user, access to the returned
    values
    """

    def __init__(self, args=None, isUtc=True):
        self._stdout = None
        self._stderr = None
        self._returncode = None
        self._timeStartedExecution = None
        self._timeFinishedExecution = None
        self._args = args
        self.isUtc = isUtc
        if(self._args != None):
            self.execute()

    def execute(self, args=None):
        if(args != None):
            self._args = args

        if(self._args != None):
            if(self.isUtc):
                self._timeStartedExecution = datetime.datetime.utcnow()
            else:
                self._timeStartedExecution = datetime.datetime.now()
            p = subprocess.Popen(self._args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if(self.isUtc):
                self._timeFinishedExecution = datetime.datetime.utcnow()
            else:
                self._timeFinishedExecution = datetime.datetime.now()
            self._stdout, self._stderr = p.communicate()
            self._returncode = p.returncode
            return 1
        else:
            self._stdout = None
            self._stderr = None
            self._returncode = None
            return 0

    def getStdout(self, getList=True):
        """
        Get the standard output of the executed command

        getList: If True, return a list of lines.
                 Otherwise, return the result as one string
        """

        if getList:
            return self._stdout.split('\n')

        return self._stdout

    def getStderr(self, getList=True):
        """
        Get the error output of the executed command

        getList: If True, return a list of lines.
                 Otherwise, return the result as one string
        """

        if getList:
            return self._stderr.split('\n')

        return self._stderr

    def getReturnCode(self):
        """
        Get the exit/return status of the command
        """
        return self._returncode

    def getTimeStartedExecution(self, inMicroseconds=False):
        """
        Get the time when the execution started
        """
        if(isinstance(self._timeStartedExecution, datetime.datetime)):
            if(inMicroseconds):
                return int(str(calendar.timegm(self._timeStartedExecution.timetuple())) + str(self._timeStartedExecution.strftime("%f")))
        return self._timeStartedExecution

    def getTimeFinishedExecution(self, inMicroseconds=False):
        """
        Get the time when the execution finished
        """
        if(isinstance(self._timeFinishedExecution, datetime.datetime)):
            if(inMicroseconds):
                return int(str(calendar.timegm(self._timeFinishedExecution.timetuple())) + str(self._timeFinishedExecution.strftime("%f")))
        return self._timeFinishedExecution

#----------------------------------------------------------------------

########################################
###### Configure logging behavior ######
########################################
# No need to change anything here

def _configureLogging(loglevel):
    """
    Configures the default logger.

    If the log level is set to NOTSET (0), the
    logging is disabled

    # More info here: https://docs.python.org/2/howto/logging.html
    """
    numeric_log_level = getattr(logging, loglevel.upper(), None)
    try:
        if not isinstance(numeric_log_level, int):
            raise ValueError()
    except ValueError:
        error_and_exit('Invalid log level: %s\n'
        '\tLog level must be set to one of the following:\n'
        '\t   CRITICAL <- Least verbose\n'
        '\t   ERROR\n'
        '\t   WARNING\n'
        '\t   INFO\n'
        '\t   DEBUG    <- Most verbose'  % loglevel)

    defaultLogger = logging.getLogger('default')

    # If numeric_log_level == 0 (NOTSET), disable logging.
    if(not numeric_log_level):
        numeric_log_level = 1000
    defaultLogger.setLevel(numeric_log_level)

    logFormatter = logging.Formatter()

    defaultHandler = logging.StreamHandler()
    defaultHandler.setFormatter(logFormatter)

    defaultLogger.addHandler(defaultHandler)

#######################################################
###### Add command line options in this function ######
#######################################################
# Add the user defined command line arguments in this function

class SmartFormatter(argparse.HelpFormatter):

    def _split_lines(self, text, width):
        # this is the RawTextHelpFormatter._split_lines
        if text.startswith('R|'):
            return text[2:].splitlines()
        return argparse.HelpFormatter._split_lines(self, text, width)
#----------------------------------------------------------------------

# TODO: Implement the --retry-failed functionality.
def _command_Line_Options():
    """
    Define the accepted command line arguments in this function

    Read the documentation of argparse for more advanced command line
    argument parsing examples
    http://docs.python.org/2/library/argparse.html
    """
    parser = argparse.ArgumentParser(description=PROGRAM_NAME + " version " + VERSION, formatter_class=SmartFormatter)
    parser.add_argument("-v", "--version",
                        action="version", default=argparse.SUPPRESS,
                        version=VERSION,
                        help="show program's version number and exit")

    loggingGroupOpts = parser.add_argument_group('Logging Options', 'List of optional logging options')
    loggingGroupOpts.add_argument("-q", "--quiet",
                                  action="store_true",
                                  default=False,
                                  dest="isQuiet",
                                  help="Disable logging in the console. Nothing will be printed.")
    loggingGroupOpts.add_argument("--log-level",
                                  action="store",
                                  default="INFO",
                                  dest="loglevel",
                                  metavar="LOG_LEVEL",
                                  help="LOG_LEVEL might be set to: CRITICAL, ERROR, WARNING, INFO, DEBUG. (Default: INFO)")

    parser.add_argument("-p", "--project-folder",
                        action="store",
                        default='maps_project',
                        dest="project_folder",
                        help="Choose a project name. The downloaded data and stitching operations will all be made under this folder.\n"
                        "Default project folder: 'maps_project'")
    parser.add_argument("-z", "--zoom-level",
                        action="store",
                        dest="zoom_level",
                        required=True,
                        help="The tile zoom level for download. Accepts an integer or a range like '1-10' or '1,4,7-9', for downloading multiple zoom levels for the given coordinates.")
    parser.add_argument("-w", "--long1",
                        action="store",
                        type=float,
                        dest="long1",
                        metavar="W_DEGREES",
                        required=True,
                        help="The western (W) longtitude of the bounding box for tile downloading. Accepted values: -180 to 179.999.")
    parser.add_argument("-e", "--long2",
                        action="store",
                        type=float,
                        dest="long2",
                        metavar="E_DEGREES",
                        required=True,
                        help="The eastern (E) longtitude of the bounding box for tile downloading. Accepted values: -180 to 179.999.")
    parser.add_argument("-n", "--lat1",
                        action="store",
                        type=float,
                        dest="lat1",
                        metavar="N_DEGREES",
                        required=True,
                        help="The northern (N) latitude of the bounding box for tile downloading. Accepted values: -85.05112 to 85.05113.")
    parser.add_argument("-s", "--lat2",
                        action="store",
                        type=float,
                        dest="lat2",
                        metavar="S_DEGREES",
                        required=True,
                        help="The southern (S) latitude of the bounding box for tile downloading. Accepted values: -85.05112 to 85.05113.")
    parser.add_argument("-o", "--custom-osm-server",
                        action="store",
                        dest="custom_osm_server",
                        metavar="OSM_SERVER_URL",
                        help="R|The URL of your private tile server. If the URL\n"
                        "contains the {z}/{x}/{y} placeholders for\n"
                        "substitution, these will be substituted with the\n"
                        "corresponding 'zoom level', 'x' and 'y' tiles during\n"
                        "downloading. If not, '{z}/{x}/{y}.png' will be appended\n"
                        "after the end of the provided URL. Example custom URL:\n"
                        "'http://your.osm.server.com/osm/{z}/{x}/{y}.png?token=12345'")
    parser.add_argument("-m", "--max-stitch-size-per-side",
                        action="store",
                        type=int,
                        default=10000,
                        dest="max_resolution_px",
                        metavar="PIXELS",
                        help="The horizontal or vertical resolution of the stitched tiles should not exceed the resolution provided by this option in pixels.\n"
                        "Default size: 10000 px")
    parser.add_argument("--save-tile-format",
                        action="store",
                        dest="tile_format",
                        choices=["png", "jpg", "original"],
                        default="original",
                        metavar="IMG_FMT",
                        help="R|The format to save the downloaded tiles.\n"
                        "  Available choices:\n"
                        "     'png'\n"
                        "     'jpg'\n"
                        "     'original' <- This is the default and it will\n"
                        "                   just save the tiles in the format\n"
                        "                   provided by the provider.")
    parser.add_argument("-r", "--retry-failed",
                        action="store_true",
                        dest="retry_failed",
                        help="When the tiles are downloaded, a log file with the tiles that failed to be downloaded is generated."
                        " If --retry-failed option is used, after the tiles have been downloaded the script will go through"
                        " this log file and retry to download the failed tiles until the download is successful. - NOT YET IMPLEMENTED")
    parser.add_argument("-d", "--skip-downloading",
                        action="store_true",
                        dest="skip_downloading",
                        help="Skip downloading of the original tiles. Use this option ONLY if you are sure that"
                        " all of the original tiles for the given coordinates have been downloaded successfully."
                        "The downloading function is also checking the integrity of the files, so it"
                        " is always a good idea to NOT skip the downloading. Keep in mind that the"
                        " downloading function will not re-download already downloaded (cached) tiles,"
                        " so you can always resume downloads.")
    parser.add_argument("-k", "--skip-stitching",
                        action="store_true",
                        dest="skip_stitching",
                        help="Skip the stitching of the original tiles onto large tiles.")
    parser.add_argument("-c", "--only-calibrate",
                        action="store_true",
                        dest="only_calibrate",
                        help="When this option is enabled, the script will not download or stitch any tiles. Only OziExplorer calibration files will be generated.")
    parser.add_argument("--prepare-printout-maps",
                        action="store_true",
                        dest="printout",
                        help="Generates paper friendly maps with a grid and a scale indicator.")
    parser.add_argument("--download-threads",
                        action="store",
                        type=int,
                        default=10,
                        metavar="DOWN_THREADS",
                        dest="download_threads",
                        help="The downloading of the tiles is threaded to speed up the download significantly."
                        " This option defines the number of concurrent download threads. Default number of download threads: 10")
    parser.add_argument("--stitching-threads",
                        action="store",
                        type=int,
                        default=get_physical_cores(),
                        metavar="STITCH_THREADS",
                        dest="stitching_threads",
                        help="The stitching of the tiles is threaded."
                        " This option defines the number of concurrent stitching threads. Default number of sitching"
                        " threads corresponds to the number of available cores in your system: {}".format(get_physical_cores()))
    parser.add_argument("-t", "--tile-server-provider",
                        action="store",
                        dest="tile_server_provider",
                        metavar="PROVIDER",
                        default=PROVIDERS.keys()[0],
                        help="R|Choose one of the predefined tile server providers:\n" + '\n'.join(["   * " + s for s in PROVIDERS]))
    parser.add_argument("-l", "--tile-server-provider-layer",
                        action="store",
                        dest="tile_server_provider_layer",
                        metavar="LAYER",
                        help="R|Choose one of the available layers for the chosen\n"
                        "provider. If none is chosen, the first one will be\n"
                        "used. Layers per provider:\n" + '\n'.join(["   * " + s + '\n' + "\n".join(['      - ' + l + ' \t# ' + PROVIDERS[s]['layers'][l]['desc'] for l in PROVIDERS[s]['layers']]) for s in PROVIDERS]))

    opts = parser.parse_args()

    if(opts.isQuiet):
        opts.loglevel = "NOTSET"

    return opts

##################################################
############### WRITE MAIN PROGRAM ###############
##################################################

#----------------------------------------------------------------------
def expand_zoom_levels(zoom_levels):
    """
    The zoom levels is a string composed of comma separated integers
    and ranges of integers designated with hyphens.

    This function parses this kind of string and returns an array of
    all the zoom levels
    """
    provided_zoom_levels = split_strip(zoom_levels)
    expanded_zoom_levels = []
    for z in provided_zoom_levels:
        zoom = split_strip(z, '-')
        if len(zoom) == 1:
            if is_number(zoom[0], is_int=True):
                expanded_zoom_levels.append(int(zoom[0]))
            else:
                error_and_exit("Provided zoom level is not a valid integer")
        elif len(zoom) == 2:
            if is_number(zoom[0], is_int=True) and is_number(zoom[1], is_int=True):
                z1 = int(zoom[0])
                z2 = int(zoom[1])
                if (z2 > z1):
                    expanded_zoom_levels.extend(range(z1, z2 + 1))
                else:
                    expanded_zoom_levels.extend(range(z2, z1 + 1))
            else:
                error_and_exit("Provided zoom level is not a valid integer")
        else:
            # This else will basically run if the user provides something
            # stupid like -z 0-1-6 (essentially when len(zoom) > 2)
            error_and_exit("Error when parsing zoom level.")

    # Use the OrderedDict to return unique zoom levels.
    return list(OrderedDict.fromkeys(sorted(expanded_zoom_levels)))

#----------------------------------------------------------------------
def validate_arguments(options):
    """
    Validate and prepare the command line arguments.
    All the changes are returned in the passed "options" variable
    """

    # Check if the project dir exists. If no, try to create it.
    options.project_folder = os.path.abspath(options.project_folder)

    if not os.path.isdir(options.project_folder):
        os.mkdir(options.project_folder)

    # Validate and expand the given zoom level(s)
    options.zoom_level = expand_zoom_levels(options.zoom_level)

    # Validate the coordinates (we do not need to check if the coordinates are valid numbers. Argparse is already doing this for us)
    if (options.long1 < -180 or options.long1 > 179.999) or (options.long2 < -180 or options.long2 > 179.999):
        error_and_exit("Longtitude value for 'West' or 'East' should be between -180.0 and 179.999")

    if (options.lat1 < -85.05112 or options.lat1 > 85.05113) or (options.lat2 < -85.05112 or options.lat2 > 85.05113):
        error_and_exit("Latitude value for 'North' or 'South' should be between -85.05112 and 85.05113 in the mercator projection.")

    if options.long1 > options.long2:
        error_and_exit("Longtitude 1 (West) coordinate should be smaller than longitude 2 (East).")

    if options.lat1 < options.lat2:
        error_and_exit("Latitude 1 (North) coordinate should be larger than latitude 2 (South).")

    # Check if the custom_osm_server is provided
    # If yes, check if the {z}/{x}/{y} placeholders are present and configure accordingly.
    if options.custom_osm_server:
        r = quick_regexp()
        if(not r.search('\{z\}', options.custom_osm_server) or not r.search('\{x\}', options.custom_osm_server) or not r.search('\{y\}', options.custom_osm_server)):
            if options.custom_osm_server.endswith("/"):
                options.custom_osm_server = options.custom_osm_server + "{z}/{x}/{y}.png"
            else:
                options.custom_osm_server = options.custom_osm_server + "/{z}/{x}/{y}.png"

        options.tile_server_provider = options.custom_osm_server
        options.tile_server_provider_layer = None
        options.tile_servers = [options.custom_osm_server]
    else:
        # If the custom server is not provided, use one of the available providers.
        if not options.tile_server_provider.lower() in [p.lower() for p in PROVIDERS.keys()]:
            error_and_exit("Provider {} is not defined.".format(options.tile_server_provider))
        else:
            # If we run in this 'else' statement, we know that the provided provider exists.
            # but the user provided string might not be matching exactly the PROVIDER key (it
            # may be all lowercase characters what the user provided).
            # So we have to find the actual key in the PROVIDER dict in order to continue.
            for p in PROVIDERS.keys():
                if options.tile_server_provider.lower() == p.lower():
                    options.tile_server_provider = p
                    # If the user provided a layer for this provider, check if the layer exists.
                    # Otherwise, use the first available layer.
                    if options.tile_server_provider_layer and not options.tile_server_provider_layer in [l for l in PROVIDERS[p]['layers']]:
                        error_and_exit("Layer '{}' is not a valid layer for provider '{}'.".format(options.tile_server_provider_layer, p))
                    else:
                        if not options.tile_server_provider_layer:
                            options.tile_server_provider_layer = PROVIDERS[p]['layers'].keys()[0]

                    # At this point we have alraedy matched the provider, so break the look
                    # (no need to iterate through all of the providers)
                    break


            # Check if the chosen provider/layer designates the available zoom_levels.
            # If the yes, and the user has chosen a non-supported zoom level, exit with an error.
            if 'zoom_levels' in PROVIDERS[options.tile_server_provider]['layers'][options.tile_server_provider_layer]:
                accepted_zoom_levels = expand_zoom_levels(PROVIDERS[options.tile_server_provider]['layers'][options.tile_server_provider_layer]['zoom_levels'])
            else:
                accepted_zoom_levels = expand_zoom_levels(PROVIDERS[options.tile_server_provider]['zoom_levels'])

            for z in options.zoom_level:
                if z not in accepted_zoom_levels:
                    error_and_exit("Provider {}->{} supports only the following zoom levels:\n   {}\n\n"
                                   "Chosen zoom levels:\n   {}\n".format(options.tile_server_provider,
                                                                         options.tile_server_provider_layer,
                                                                         accepted_zoom_levels,
                                                                         options.zoom_level))

        # Expand the alternative tile_servers for the specific layer
        if 'tile_servers' in PROVIDERS[options.tile_server_provider]['layers'][options.tile_server_provider_layer]:
            tile_servers_to_expand = PROVIDERS[options.tile_server_provider]['layers'][options.tile_server_provider_layer]['tile_servers']
        else:
            tile_servers_to_expand = PROVIDERS[options.tile_server_provider]['tile_servers']

        if 'extension' in PROVIDERS[options.tile_server_provider]['layers'][options.tile_server_provider_layer]:
            layer_extension = PROVIDERS[options.tile_server_provider]['layers'][options.tile_server_provider_layer]['extension']
        elif 'extension' in PROVIDERS[options.tile_server_provider]:
            layer_extension = PROVIDERS[options.tile_server_provider]['extension']
        else:
            layer_extension = None

        options.tile_servers = []
        r = quick_regexp()
        for server_string in tile_servers_to_expand:
            # Add the layer in the URL
            # If the 'name' key is defined in the layer, use the name of the layer in the url.
            # Otherwise, use the 'layer' key itself.
            if 'name' in PROVIDERS[options.tile_server_provider]['layers'][options.tile_server_provider_layer]:
                layer = PROVIDERS[options.tile_server_provider]['layers'][options.tile_server_provider_layer]['name']
            else:
                layer = options.tile_server_provider_layer

            server_string = re.sub('\{layer\}', layer, server_string)
            # Add the extension in the URL
            if layer_extension:
                server_string = re.sub('\{ext\}', layer_extension, server_string)

            # If the user hasn't provided a tile format (using original), and the is no layer_extension,
            # fallback to the default png file format.
            if options.tile_format == 'original':
                if layer_extension:
                    options.tile_format = layer_extension
                else:
                    options.tile_format = 'png'

            if r.search('\{alts:([^\}]*)\}', server_string):
                for alternative in split_strip(r.groups[0]):
                    options.tile_servers.append(re.sub('\{alts:[^\}]*\}', alternative, server_string))
            else:
                options.tile_servers.append(server_string)

#----------------------------------------------------------------------
def read_zoom_config(zoom, options):
    """
    This function has to be called after the command line arguments have been validated,
    and for a specific zoom level.

    It will read the corresponding zoom level configuration file (if any) and make sure
    that the user is not mixing different tiles or different layer etc.

    Returns the zoom configuration file path and the main configuration section for the
    current zoom level/file
    """
    zoom_conf = os.path.join(options['project_folder'].keys().pop(), 'zoom-{}.conf'.format(zoom))
    main_config_section = "Zoom-{}-Settings".format(zoom)

    try:
        with open(zoom_conf):
            LOG.debug("\nReading configuration from file '{}".format(zoom_conf))
            config = ConfigParser.ConfigParser()
            config.read(zoom_conf)

            if(config.has_section(main_config_section)):
                for key, val in options.items():
                    # val.values().pop() returns either 0 or 1, indicating if we
                    # care to check this option.
                    if val.values().pop():
                        if config.has_option(main_config_section, key):
                            config_val = config.get(main_config_section, key)
                            LOG.debug("Reading config option '{}' -> '{}'".format(key, config_val))
                            if config_val != val.keys().pop():
                                error_and_exit("Option '{0}' in the existing config file is '{1}', but it is '{2}' in\n"
                                               "the current run. Please use the same value for key '{0}', or use a different project folder.".format(
                                                   key,
                                                   config_val,
                                                   val.keys().pop()
                                               )
                                               )
                        else:
                            error_and_exit("Option '{0}' is defined in the current run, but it doesn't exist in the configuration file '{1}'.\n"
                                           "This option should match since a configuration file exists (indicating that you have"
                                           "already ran the script for the specified zoom level in the current project folder)".format(
                                               key,
                                               zoom_conf
                                           )
                                           )

    except IOError as e:
        # If the error number is 2 (no such file or directory), the conf file does no
        # exist. Most likely it is the first first time we run the script for this specific
        # zoom level under the specified project_folder. In this case return silently.
        # If the errno is NOT 2, raise an error and exit.
        if not e.errno == 2:
            LOG.error("IOError: [Errno {}] {}: '{}'".format(e.errno, e.strerror, e.filename))
            raise
    except ConfigParser.MissingSectionHeaderError as e:
        LOG.error('\nNot a valid configuration file {}'.format(e.filename))
        raise

    return zoom_conf, main_config_section

#----------------------------------------------------------------------
def write_zoom_config(zoom_conf, options, section_to_write):
    """
    Write the options in the configuration file.
    Make sure that the options you pass in this function are "final".
    No sanity checks will be made. Just write in the file.
    """
    with open(zoom_conf, 'w') as cfgfile:
        LOG.debug("\nWriting configuration file '{}'".format(zoom_conf))
        config = ConfigParser.ConfigParser()
        config.add_section(section_to_write)

        for key, val in options.items():
            LOG.debug("Writing '{}' -> '{}'".format(key, val.keys().pop()))
            config.set(section_to_write, key, val.keys().pop())

        config.write(cfgfile)


########################################################################
class stitch_osm_tiles(object):
    """
    Class to stitch OSM tiles
    """

    #----------------------------------------------------------------------
    def __init__(self,
                 zoom,
                 saved_tile_format,
                 tile_servers = None,
                 project_folder = 'maps_project',
                 max_dimensions = 10000,
                 parallelDownloadThreads = 10,
                 parallelStitchingThreads = get_physical_cores()):
        """
        zoom: The zoom level where the class will be working with for downloading and stitching.
        saved_tile_format: Different providers provide different tile formats. Mapquest for example, provides
                           jpg, while openstreetmap provides png tiles. The saved_tile_format defines the format
                           that the tiles will be saved locally. This might be needed for different reasons.
                           For example, OziExplorer can read only PNG files from its local cache. In this case,
                           if you download tiles from MapQuest, you cannot use them if you do not convert them
                           to png format. If you set 'saved_tile_format' to png, then the tiles although they are
                           downloaded in jpg, they will be converted and saved in a png format.
        tile_servers: A list with all of the available tile servers that can be used for tile downloading.
                      e.g:
                         [
                            'http://a.tileserver.com/{z}/{x}/{y}.png',
                            'http://b.tileserver.com/{z}/{x}/{y}.png',
                            'http://c.tileserver.com/{z}/{x}/{y}.png'
                         ]

                         Note that {z}/{x}/{y} should be present, since these placeholders will be substituted
                         when downloading different tiles.

                         If tile_servers == None, no downloading of tiles can be performed, but tiles can
                         still be stitched or calibrated.
        project_folder: Project folder defines where the tiles will be downloaded and where the stitches will
                        be saved.
        """
        # The zoom level where the current tile worker will be working on.
        self.zoom = zoom
        # A dictionary of the provider with layer specific information as created by the
        # create_provider_dict function.
        self.tile_servers = tile_servers
        # the _tile_height and _tile_height will be calculated when the first tile is downloaded.
        self.max_dimensions = max_dimensions # Default 10000 pixels
        # The project name (equals to the project folder)
        self.project_folder = project_folder
        self.saved_tile_format = saved_tile_format
        self.parallelDownloadThreads = parallelDownloadThreads
        self.parallelStitchingThreads = parallelStitchingThreads
        self._tile_height = None
        self._tile_width = None
        self._itemsInProcessing = []
        self._inDownloadQueue = Queue.Queue()
        self._outDownloadQueue = Queue.Queue()
        self._inStitchingQueue = Queue.Queue()
        self._downloadLogFileLock = threading.Lock()

    #----------------------------------------------------------------------
    def get_tile_url(self, tile_server, x, y):
        """
        Return the tile url by replacing the placeholders
        """
        url = re.sub('\{x\}', x, tile_server)
        url = re.sub('\{y\}', y, url)
        url = re.sub('\{z\}', str(self.zoom), url)

        return url

    #----------------------------------------------------------------------
    # X and Y
    #      X goes from 0 (left edge is 180 °W) to 2^zoom − 1 (right edge is 180 °E)
    #      Y goes from 0 (top edge is 85.0511 °N) to 2^zoom − 1 (bottom edge is 85.0511 °S) in a "Mercator projection" <- THIS IS VERY IMPORTANT
    #                                                                                                           LATER WHEN I DO THE CALIBRATION.
    # For the curious, the number 85.0511 is the result of arctan(sinh(π)). By using this bound, the entire map becomes a (very large) square.
    #
    # https://help.openstreetmap.org/questions/37743/tile-coordinates-from-latlonzoom-formula-problem
    def deg2tilenums(self, lat_deg, lon_deg):
        """
        Function to return tile numbers from coordinates given in degress

        http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Lon..2Flat._to_tile_numbers_2
        """
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** self.zoom
        xtile = int((lon_deg + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)

        return (xtile, ytile)

    #----------------------------------------------------------------------
    def tilenums2deg(self, xtile, ytile):
        """
        Function to return coordinates given in degress from tile numbers

        http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Tile_numbers_to_lon..2Flat._2

        This returns the NW-corner of the square. Use the function with xtile+1
        and/or ytile+1 to get the other corners. With xtile+0.5 & ytile+0.5 it
        will return the center of the tile.
        """
        n = 2.0 ** self.zoom
        lon_deg = xtile / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
        lat_deg = math.degrees(lat_rad)

        return (lat_deg, lon_deg)


    #----------------------------------------------------------------------
    # Get the longtitude and latitude per pixel, based on the global pixel scale of the map.
    # For example, if the zoom level is 0, then only one 256x256 tile compose the complete
    # map. In this case, a y pixel value of 0 will give a latitude of ~-85deg and a y pixel
    # value of 256 will give a latitude of +85.
    # If the zoom is 3, then the whole map is 8x8 tiles, so 2048x2048 pixels. In this case
    # a y pixel value of 0 will give a latitude of ~-85deg and a y pixel value of 20248 will
    # give a latitude of +85.
    def pixel2deg(self, xpixel, ypixel, original_tiles_width, original_tiles_height):
        """
        Returns the longtitude and latitude of the of the given x/y pixel
        """
        n = 2.0 ** self.zoom
        lon_deg = float(xpixel) / original_tiles_width / n * 360.0 - 180

        num_pixel = math.pi - 2.0 * math.pi * ypixel / original_tiles_height / n
        lat_deg = 180.0 / math.pi * math.atan2(0.5 * (math.exp(num_pixel) - math.exp(-num_pixel) ), 1)

        return (lat_deg, lon_deg)

    #----------------------------------------------------------------------
    def _convert_degrees_to_OZI_deg(self, degrees, orientation):
        """
        Returns a tuple with the absolute value of degrees and orientation
        like: (int(degrees), minutes, orientation)

        Provided orientation can be one of: N, S, W, E
        Degrees can be either positive or negative degrees
        """

        if orientation == "N" or orientation == "S":
            o = "S" if degrees < 0.0 else "N"
        elif orientation == "W" or orientation == "E":
            o = "W" if degrees < 0.0 else "E"

        deg = abs(degrees)

        return (int(deg), (deg-int(deg))*60, o)


    #----------------------------------------------------------------------
    def generate_OZI_map_file(self, filename, extension, width, height, zoom, N, S, W, E):
        """
        This function will generate a map calibration file for OziExplorer

        # HOW TO CALCULATE MMB1
        # From the official documentation: http://www.oziexplorer3.com/eng/help/map_file_format.html
        #   The scale of the image meters/pixel, its calculated in the left / right image direction.
        #   ***It is calculated each time OziExplorer is run, the value in the file is used when searching for maps of "more detailed" scale.***
        #
        # So obviously, this value is not affecting the positioning since it is recalculated when the file is loaded.
        # Nevertheless, here is the way to calculate it:
        #
        # The earth is a "almost" a perfect sphere and the equatorial circumference of the earth is 40075017m (that's the maximum).
        # However, at different latitudes the circumference changes.
        # When we use degrees for latitude representation, the circumference at any given latitude from -90 deg to +90 deg can be
        # calculated with the following formula:
        #              40075017*cos(lat/180*pi)
        #
        #              At the equator it will always be max. The latitude is zero and the cos of 0 is 1.
        #              At the poles the latitude is +-90 degrees, and the "lat/180*pi" becomes +-0.5*pi and the cos of +-0.5*pi is 0.
        #              At any other latitude, the circumference will get values in between.
        #
        # Each tile in OSM is 256x256px and each complete map is composed from 2^zoom_level tiles.
        # Consequently, the width/height of the whole globe given in pixels, for each zoom_level is 256*2^zoom_level.
        # Eventually, the size of each pixel at different latitudes is given by this formula:
        #         40075017*cos(lat/180*pi)/(256*2^zoom_level.)
        #            or
        #         40075017*cos(lat/180*pi)/*2^(zoom_level+8) # 256 = 2^8
        #
        # Since each tile covers a range of longtitudes and latitudes, we need to find the latitude in the middle of the tile
        # and calculate the MMB1 value based on this.
        #
        # TODO: Change all occurences of '2**(zoom+8)' to 'self._tile_width*(2**8)', because if we export tiles of different size
        #       zoom+8 will not be valid. The +8 part is coming for the fact that 256 = 2**8
        """
        latitude_mid_of_tile = S + (N - S)/2
        MMB1 = 40075017 * math.cos(float(latitude_mid_of_tile) / 180 * math.pi) / 2**(zoom+8)

        N_OZI = self._convert_degrees_to_OZI_deg(N, 'N')
        S_OZI = self._convert_degrees_to_OZI_deg(S, 'S')
        W_OZI = self._convert_degrees_to_OZI_deg(W, 'W')
        E_OZI = self._convert_degrees_to_OZI_deg(E, 'E')

        ozi_map_file = """OziExplorer Map Data File Version 2.2
{19}
{19}.{20}
1,Map Code,
WGS 84,WGS 84,   0.0000,   0.0000,WGS 84
Reserved 1
Reserved 2
Magnetic Variation,,,E
Map Projection,Mercator,PolyCal,No,AutoCalOnly,No,BSBUseWPX,No
Point01,xy, {21}, {21}, in, deg, {0}, {1}, {2}, {6}, {7}, {8}, grid,   , , ,N
Point02,xy, {22}, {23}, in, deg, {3}, {4}, {5}, {9}, {10}, {11}, grid,   , , ,N
Point03,xy, {22}, {21}, in, deg, {0}, {1}, {2}, {9}, {10}, {11}, grid,   , , ,N
Point04,xy, {21}, {23}, in, deg, {3}, {4}, {5}, {6}, {7}, {8}, grid,   , , ,N
Projection Setup,,,,,,,,,,
Map Feature = MF ; Map Comment = MC     These follow if they exist
Track File = TF      These follow if they exist
Moving Map Parameters = MM?    These follow if they exist
MM0,Yes
MMPNUM,4
MMPXY,1,0,0
MMPXY,2,{16},0
MMPXY,3,{16},{17}
MMPXY,4,0,{17}
MMPLL,1, {14}, {12}
MMPLL,2, {15}, {12}
MMPLL,3, {15}, {13}
MMPLL,4, {14}, {13}
MM1B,{18}
MOP,Map Open Position,0,0
IWH,Map Image Width/Height,{16},{17}""".format(
                                                N_OZI[0], N_OZI[1], N_OZI[2],
                                                S_OZI[0], S_OZI[1], S_OZI[2],
                                                W_OZI[0], W_OZI[1], W_OZI[2],
                                                E_OZI[0], E_OZI[1], E_OZI[2],
                                                N, S, W, E,
                                                width, height, MMB1,
                                                filename, extension,
                                                '0'.rjust(5), str(width - 1).rjust(5), str(height - 1).rjust(5)
                                            )

        return ozi_map_file


    #----------------------------------------------------------------------
    def _download_tile_worker(self, inQueue, outQueue):
        """
        Downloads the content (should be a tile) of the given url.
        Returns a ([graphicsMagickImageObject, imageblob], None) tuple if the file was downloaded succesfully, or a
        tuple with the error object and a stritg with the type of the error.
        """
        try:
            while True:
                # The data received from the queue is tuple (url, download_path)
                url, download_path = inQueue.get()

                LOG.debug("{} is DOWNLOADING '{}' -> '{}'".format(threading.currentThread().getName(), url, download_path))

                req = urllib2.Request(url)

                try:
                    resp = urllib2.urlopen(req, timeout = 5)
                except urllib2.HTTPError as e:
                    # e.code contains the actual error code
                    retval = (e, url, download_path, 'HTTPError')
                except urllib2.URLError as e:
                    retval = (e, url, download_path, 'URLError')
                except socket.timeout as e:
                    retval = (e, url, download_path, 'SocketTimeout')
                else:
                    try:
                        tile = resp.read()
                        try:
                            img = gmImage(pgmagick.Blob(tile))
                            img.write(download_path)
                            retval = ([img, tile], url, download_path, None)
                        except RuntimeError, e:
                            e = sys.exc_info()[0]
                            retval = (e, url, download_path, 'UnknownGraphicsMagicError')
                    except socket.error as e:
                        retval = (e, url, download_path, 'SocketError while reading response')

                outQueue.put(retval)
                inQueue.task_done()
        except KeyboardInterrupt:
            inQueue.task_done()
            exit(1)

    #----------------------------------------------------------------------
    def _process_download_results_worker(self, inQueue, progress_bar, logfile):
        """
        Handle the completed downloads.
        Saving the file and writing into log file if a download error occured.
        """
        try:
            while True:
                # The data received from the queue is a tuple as return by the 'download_tile_worker' threads
                result, url, download_path, errorType = inQueue.get()

                LOG.debug("{} is PROCESSING DOWNLOADED file for url '{}'".format(threading.currentThread().getName(), url))
                time_now = time.strftime("%a %d %b %Y %H:%M:%S")

                # If there was an error, append in the log file.
                if errorType is not None:
                    # Use the lock to make sure that threads do not interfere
                    with self._downloadLogFileLock:
                        logfile.write("{} - ERROR:'{}' -> '{}'\n".format(time_now, url, download_path))
                else:
                    img, tile = result

                # Ιf it is the first image we process, update the _tile_width and _tile_height
                # When we download the first image, progress_bar is just initialized, so progress_bar.currval == 0
                # Also, when we process the first image, we are waiting for the processing to complete before adding
                # more items for threaded processing in the queue, so we are sure that when progress_bar.currval == 0
                # we actually process the first image.
                if progress_bar.currval == 0:
                    if errorType is not None:
                        # If there is an error when trying to download the first tile, just exit.
                        error_and_exit("The very first tile must be downloaded in order to continue with the rest, but unfortunately there was an error. Please retry.")
                    self._tile_width = img.columns()
                    self._tile_height = img.rows()

                # Update the progress bar
                with self._downloadLogFileLock:
                    pbar_val = progress_bar.currval + 1
                    progress_bar.update(pbar_val)

                try:
                    self._itemsInProcessing.remove(url)
                except ValueError:
                    error_and_exit("Something strange happened...\nURL '{}' has already been removed from the items to be processed.\nPlease retry..".format(url))

                inQueue.task_done()
        except KeyboardInterrupt:
            inQueue.task_done()
            exit(1)

    #----------------------------------------------------------------------
    def _addToDownloadInputQueue(self, args):
        """
        Helper function to add a url in the input queue for threaded processing

        args must be (url, download_path) tuple
        """
        url = args[0]

        # If we have many pending/unproccessed items, wait until some of the items are processed.
        while len(self._itemsInProcessing) > 2 * self.parallelDownloadThreads:
            time.sleep(0.01)

        # Then add the items in the queue
        self._inDownloadQueue.put(args)
        self._itemsInProcessing.append(url)

    #----------------------------------------------------------------------
    def _addToStitchingInputQueue(self, args):
        """
        Helper function to add the needed arguments for threaded stitching
        """

        stitch = args[1]

        # If we have many pending/unproccessed items, wait until some of the items are processed.
        while len(self._itemsInProcessing) >= self.parallelStitchingThreads:
            time.sleep(0.01)

        # Then add the items in the queue
        self._inStitchingQueue.put(args)
        self._itemsInProcessing.append(stitch)

    #----------------------------------------------------------------------
    def download_tiles(self, tile_west, tile_east, tile_north, tile_south):
        """
        Download tiles for a given zoom level.
        If the tiles are already downloaded, this function will only check the consistency
        of the downloaded files.
        """
        number_of_horizontal_tiles = (tile_east - tile_west) + 1
        number_of_vertical_tiles = (tile_south - tile_north) + 1

        total_tiles = number_of_horizontal_tiles * number_of_vertical_tiles

        myProgressBarFd = sys.stderr
        # If log level is set to 1000 (logging is disabled), or DEBUG, then redirect
        # the progress bar to /dev/null (use os.devnull to support windows as well)
        if LOG.getEffectiveLevel() == 1000 or LOG.getEffectiveLevel() == logging.DEBUG:
            myProgressBarFd = open(os.devnull, "w")

        widgets = ['Downloading tile ', progressbar.Counter(format='%{}d'.format(len(str(total_tiles)))), '/{}: '.format(total_tiles),
                   progressbar.Percentage(), ' ', progressbar.Bar(marker='#'), ' ', progressbar.RotatingMarker(), ' ', progressbar.ETA()]

        pbar = progressbar.ProgressBar(widgets = widgets, maxval = total_tiles, fd = myProgressBarFd).start()

        # How I implemented the thread pool:
        #   I have an input queue (self._inQueue), an output queue (self._outQueue) and a pool of download threads (the number
        #   of the threads is defined by self.parallelDownloadThreads) that are fed by the input queue, and place the returned
        #   values in the output queue that is handled by another single thread.
        #
        #   Whenever I add a url to be downloaded, the url is appended in the self._itemInProcessing (This is done in order
        #   to keep track which items are in the queue and their process hasn't finished yet) and when the download is
        #   finished, the url is removed by the thread that is handling the results. The thread that is handling the results
        #   logs potential errors in a file and updates the progressbar.
        #
        #   I control the number of urls that are added in the input queue, by checking the length of the self._itemInProcessing
        #   list. If this list has more than (2 * self.parallelDownloadThreads) items, then the program sleeps for 10 milliseconds
        #   and checks again the length of the list before adding more url's in the input queue.

        # Instantiate a thread pool with 'self.parallelDownloadThreads' number of threads
        instantiate_threadpool('Download-Thread', self.parallelDownloadThreads, self._download_tile_worker, (self._inDownloadQueue, self._outDownloadQueue))

        # Instantiate a single thread to process the results of the downloads
        # The log file has to be opened before we start the threads, because the thread worker is using the log file.
        downloadLogFile = open( os.path.join(self.project_folder, "zoom-{}-download.log".format(self.zoom)), 'w' )
        instantiate_threadpool('ProccessDownloaded-Thread', 1, self._process_download_results_worker, (self._outDownloadQueue, pbar, downloadLogFile))

        # The counter is mostly used to choose different tile servers if more than one tile servers are provided for the specified provider.
        counter = 1
        for x in xrange(tile_west, tile_east + 1):
            x_path = os.path.join(self.project_folder, str(self.zoom), str(x))
            if not os.path.isdir(x_path):
                os.mkdir(x_path)

            for y in xrange(tile_north, tile_south + 1):
                url = self.get_tile_url(self.tile_servers[counter % len(self.tile_servers)], str(x), str(y))

                y_path = '{}.{}'.format(os.path.join(x_path, str(y)), self.saved_tile_format)

                LOG.debug("Processing tile '{}' (Progress: {}/{})".format(y_path, counter, total_tiles))

                # Before adding files in the queue, check if the file exists
                if os.path.isfile(y_path):
                    try:
                        img = gmImage(y_path)
                        # If it is the first image we process, set the self._tile_width and self._tile_height
                        if counter == 1:
                            self._tile_width = img.columns()
                            self._tile_height = img.rows()

                        # If the image is already loaded successfully, but the image size differs from
                        # self._tile_height/self._tile_width, try to redownload it.
                        if not (img.columns() == self._tile_width and img.rows() == self._tile_height):
                            self._addToDownloadInputQueue((url, y_path))
                        else:
                            # Update the progress bar
                            pbar.currval += 1
                            pbar.update(pbar.currval)
                    except RuntimeError, e:
                        # We execute at this point if the image exists but it cannot be loaded succesfully.
                        # In this case, try to re-download it.
                        self._addToDownloadInputQueue((url, y_path))
                else:
                    # Else the file does not exist, try to download it for the first time.
                    self._addToDownloadInputQueue((url, y_path))

                # If we are processing the first tile, wait until the processing completes because we have to
                # read the width/height of this tile before downloading the rest. The rest of the tiles are
                # processed in parallel by multiple threads.
                if counter == 1:
                    while url in self._itemsInProcessing:
                        time.sleep(0.01)

                counter+=1

        # Wait for the threads to finish their work by joing the in/out Queues
        self._inDownloadQueue.join()
        self._outDownloadQueue.join()

        pbar.finish()

        # Close the log file since we have finished downloading at this point.
        downloadLogFile.close()

    #----------------------------------------------------------------------
    def _calculate_max_dimensions_per_stitch(self, tile_west, tile_east, tile_north, tile_south):
        """
        Calculate the max horizontal/vertical dimensions for the final stitches
        """
        number_of_horizontal_tiles = (tile_east - tile_west) + 1
        number_of_vertical_tiles = (tile_south - tile_north) + 1

        # If we do not already know the dimensions of the tiles, then read the dimensions.
        if self._tile_height == None or self._tile_width == None:
            x_path = os.path.join(self.project_folder, str(self.zoom), str(tile_west))
            first_y_tile_path = '{}.{}'.format(os.path.join(x_path, str(tile_north)), self.saved_tile_format)
            try:
                img = gmImage(first_y_tile_path)
                self._tile_height = img.rows()
                self._tile_width = img.columns()
            except RuntimeError, e:
                LOG.critical(e.message)
                exit(1)


        total_vertical_resolution = self._tile_height * number_of_vertical_tiles
        total_horizontal_resolution = self._tile_width * number_of_horizontal_tiles

        vertical_resolution_per_stitch = total_vertical_resolution
        horizontal_resolution_per_stitch = total_horizontal_resolution

        vertical_divide_by = 1
        horizontal_divide_by = 1

        while vertical_resolution_per_stitch > self.max_dimensions:
            # If we have an accurate division without any remainder,
            if total_vertical_resolution % vertical_divide_by == 0:
                # If the accurately divided number does not result in a resolution less than
                # self.max_dimensions, increase the divisor and try again.
                if total_vertical_resolution / vertical_divide_by > self.max_dimensions:
                    vertical_divide_by+=1
                else:
                    # Otherwise use this value for the vertical resolution
                    # and keep this divisor
                    vertical_resolution_per_stitch = total_vertical_resolution / vertical_divide_by
            else:
                # Otherwise, increase the divisor
                vertical_divide_by+=1

        # Same story as the previous while-loop, but do it for the horizontal resolution.
        while horizontal_resolution_per_stitch > self.max_dimensions:
            if(total_horizontal_resolution % horizontal_divide_by == 0):
                if total_horizontal_resolution / horizontal_divide_by > self.max_dimensions:
                    horizontal_divide_by+=1
                else:
                    horizontal_resolution_per_stitch = total_horizontal_resolution / horizontal_divide_by
            else:
                horizontal_divide_by+=1

        return {
            'total_vertical_resolution': total_vertical_resolution,
            'total_horizontal_resolution': total_horizontal_resolution,
            'vertical_resolution_per_stitch': vertical_resolution_per_stitch,
            'horizontal_resolution_per_stitch': horizontal_resolution_per_stitch,
            'vertical_divide_by': vertical_divide_by,
            'horizontal_divide_by': horizontal_divide_by
        }

    #----------------------------------------------------------------------
    def _stitch_thumbnail(self, img, thumb_filepath, x_res = 144, y_res = 144):
        """
        Function to generate a thumbnail from a stitch img.
        img is a graphicmagick Image object.
        """

        LOG.debug("Generating thumbnail '{}'".format(thumb_filepath))

        im_w = img.columns()
        im_h = img.rows()
        if im_w > im_h:
            geo_size = "{}x{}".format(x_res, int(math.ceil((float(im_h) / im_w)) * x_res))
        else:
            geo_size = "{}x{}".format(int(math.ceil((float(im_w) / im_h) * y_res)), y_res)

        geometry = pgmagick.Geometry(geo_size)
        img.scale(geometry)
        img.write(thumb_filepath)

    #----------------------------------------------------------------------
    def _stitch_tile_worker(self, inQueue):
        """
        The function will get a list of input files (the paths of the files)
        and stitch them together. It will also generate a thumbnail.
        """
        try:
            while True:
                list_of_files, stitch_filepath, thumb_filepath, x_tiles, y_tiles, x_res, y_res, crop_left, crop_top, progress_bar = inQueue.get()

                LOG.debug("{} is STITCHING '{}'".format(threading.currentThread().getName(), stitch_filepath))

                # Prepare the montage command to execute on command line.
                # Graphicsmagick has a bug (at least in the version that I am using) and when doing the montage
                # from jpg files, the resulting montaged images are half of the expected size. So when stitching
                # from jpg source files, use the imagemagick montage, while for all the rest, use gm montage which
                # is faster.
                if self.saved_tile_format == 'jpg':
                    montage_cmd = ['montage']
                else:
                    montage_cmd = ['gm', 'montage']
                montage_cmd.extend(list_of_files)
                # Run the montage, but do not save into a file! Instead, redirect a png output to stdout. Since the stdout is binary
                # data and stored in memory, we use pgmagick.Blob to load it in a pgmagick object and crop it later without having to
                # write a intermediate file on hard disk in between.
                montage_cmd.extend(['-tile', '{}x{}'.format(x_tiles, y_tiles), '-background', 'none', '-geometry', '+0+0', 'png:-'])

                # Stitch the images here
                montage = executeCommand(montage_cmd)

                if montage.getReturnCode() != 0 and montage.getReturnCode() is not None:
                    LOG.error("ERROR: Could not generate stitch file '{}.".format(stitch_filepath))
                else:
                    # Load the stitched image and first crop and save it....
                    LOG.debug("Cropping tile '{}' left, top: {}, {}".format(stitch_filepath, crop_left, crop_top))
                    # Use a Blob to load the output of the montage command we executed earlier.
                    img = gmImage(pgmagick.Blob(montage.getStdout(getList=False)))
                    img.crop('{}x{}+{}+{}'.format(x_res, y_res, crop_left, crop_top))
                    LOG.debug("Saving tile '{}'".format(stitch_filepath))
                    img.write(stitch_filepath)

                    # Second, generate a thumbnail for the final image index.
                    self._stitch_thumbnail(img, thumb_filepath)

                # Update the progress bar
                with self._downloadLogFileLock:
                    pbar_val = progress_bar.currval + 1
                    progress_bar.update(pbar_val)

                self._itemsInProcessing.remove(stitch_filepath)

                inQueue.task_done()
        except KeyboardInterrupt:
            inQueue.task_done()
            exit(1)

    #----------------------------------------------------------------------
    def stitch_tiles(self, tile_west, tile_east, tile_north, tile_south):
        """
        Stitch tiles for a given zoom level in the given max dimensions
        """
        dimensions = self._calculate_max_dimensions_per_stitch(tile_west, tile_east, tile_north, tile_south)

        total_stitches = dimensions['vertical_divide_by'] * dimensions['horizontal_divide_by']

        # Create a thread pool with 'self.parallelStitchingThreads' number of threads for the stitching.
        instantiate_threadpool('Stitching-Thread', self.parallelStitchingThreads, self._stitch_tile_worker, (self._inStitchingQueue, ))

        stitches_path = os.path.join(self.project_folder, "stitched_maps", str(zoom))
        thumbnails_path = os.path.join(stitches_path, "thumbs")
        if not os.path.isdir(stitches_path):
            os.makedirs(stitches_path)

        if not os.path.isdir(thumbnails_path):
            os.makedirs(thumbnails_path)

        counter = 1

        myProgressBarFd = sys.stderr
        # If log level is set to 1000 (logging is disabled), or DEBUG, then redirect
        # the progress bar to /dev/null (use os.devnull to support windows as well)
        if LOG.getEffectiveLevel() == 1000 or LOG.getEffectiveLevel() == logging.DEBUG:
            myProgressBarFd = open(os.devnull, "w")

        widgets = ['Stitching tile ', progressbar.Counter(format='%{}d'.format(len(str(total_stitches)))), '/{}: '.format(total_stitches),
                   progressbar.Percentage(), ' ', progressbar.Bar(marker='#'), ' ', progressbar.RotatingMarker(), ' ', progressbar.ETA()]

        pbar = progressbar.ProgressBar(widgets = widgets, maxval = total_stitches, fd = myProgressBarFd).start()


        # If we have a matrix of files like the following one,
        #
        # 01   02   03   04   05   06
        # 07   08   09   10   11   12
        # 13   14   15   16   17   18
        # 19   20   21   22   23   24
        #
        # and vertical_divide = horizontal_divide = 2, then we will
        # generate 2x2=4 final stitched tiles. In this case the final
        # tiles will be composed of the following pictures:
        #
        # Tile 1: 01, 02, 03, 07, 08, 09
        # Tile 2: 04, 05, 06, 10, 11, 12
        # Tile 3: 13, 14, 15, 19, 20, 21
        # Tile 4: 16, 17, 18, 20, 23, 24
        #
        # In order to build each of the tiles, the graphicsmagick command
        # should be given the files in the above order, and is should be
        # asked to make 3x2 tiles for each stitch.
        total_number_of_horizontal_tiles = (tile_east + 1) - tile_west
        total_number_of_vertical_tiles = (tile_south + 1) - tile_north
        horizontal_tiles_per_stitch = float(total_number_of_horizontal_tiles) / dimensions['horizontal_divide_by']
        vertical_tiles_per_stitch = float(total_number_of_vertical_tiles) / dimensions['vertical_divide_by']

        # This array stores all of the thumbnail filenames of the final stitches, in order to create a final index image in the end
        all_thumb_stitches = []
        for y in xrange(dimensions['vertical_divide_by']):
            for x in xrange(dimensions['horizontal_divide_by']):
                # The stitch_key must contain the final image extension
                stitch_key = '{}_{}.png'.format(y, x)

                # The files_stitch array stores the filename path of all the original images to be stitched in the current stitch.
                files_stitch = []

                start_x_tile = int(tile_west + math.floor(x * horizontal_tiles_per_stitch))
                start_y_tile = int(tile_north + math.floor(y * vertical_tiles_per_stitch))

                # Crop the stitched tiles as needed so that we do not have overlaps and make sure that each tile fits the given dimensions.
                crop_from_left = x * dimensions['horizontal_resolution_per_stitch'] - self._tile_width * (start_x_tile - tile_west)
                crop_from_top = y * dimensions['vertical_resolution_per_stitch'] - self._tile_height * (start_y_tile - tile_north)

                # The variables horizontal_tiles_per_stitch and vertical_tiles_per_stitch are float numbers, since the stitches
                # may need to be composed out of e.g. 25 tiles + 64 pixels. This is 25.25 tiles if each tile is 256x256 pixels.
                # In this case, we might come in a situation that we actually need to process 27 tiles in order to stitch the final
                # tile. 25 whole tiles, and it might be that we have to get 32 pixels from a tile that was used in a previous stitch
                # and another 32 pixels from a tile that it will be partly used for the next stitch. These 32 + 32 pixels make up
                # for the additional 0.25 tiles (remember in this example we need 25.25 horizontal tiles per stitch) but this
                # additional 0.25 tiles might be located either on a tile before the whole 25 tiles, after, or shared in one tile
                # before and one after. If that's the case, the crop_from_left variable has the value 256 - 32 = 224, and since
                # these 224 pixels will be cropped from the start tile, we need to add them in the horizontal_tiles_per_stitch
                # with the 'float(crop_from_left) / self._tile_width'.
                end_x_tile = int(start_x_tile + math.ceil(horizontal_tiles_per_stitch + float(crop_from_left) / self._tile_width))
                end_y_tile = int(start_y_tile + math.ceil(vertical_tiles_per_stitch + float(crop_from_top) / self._tile_height))

                # The end tiles are excluded... So for the current stitch, we
                # actually process from 'start_x_tile' until 'end_x_tile - 1'
                for y_orig_tile in xrange(start_y_tile, end_y_tile):
                    for x_orig_tile in xrange(start_x_tile, end_x_tile):
                        x_path = os.path.join(self.project_folder, str(self.zoom), str(x_orig_tile))
                        y_path = '{}.{}'.format(os.path.join(x_path, str(y_orig_tile)), self.saved_tile_format)

                        files_stitch.append(y_path)

                # The montage is not implemented in the python APIs, so use the command line
                # The command line should look like this: ''gm montage 2x2 ${files} -background none -geometry +0+0 file.png
                path_to_stitch = os.path.join(stitches_path, stitch_key)
                path_to_thumb = os.path.join(thumbnails_path, stitch_key)
                try:
                    img = gmImage(path_to_stitch)

                    if not (img.rows() == dimensions['vertical_resolution_per_stitch'] and
                            img.columns() == dimensions['horizontal_resolution_per_stitch']):
                        raise RuntimeError
                    else:
                        if not os.path.isfile(path_to_thumb):
                            self._stitch_thumbnail(img, path_to_thumb)
                        pbar.currval += 1
                        pbar.update(pbar.currval)
                except RuntimeError, e:
                    self._addToStitchingInputQueue((files_stitch,
                                                    path_to_stitch,
                                                    path_to_thumb,
                                                    end_x_tile - start_x_tile,
                                                    end_y_tile - start_y_tile,
                                                    dimensions['horizontal_resolution_per_stitch'],
                                                    dimensions['vertical_resolution_per_stitch'],
                                                    crop_from_left,
                                                    crop_from_top,
                                                    pbar))

                # Add the thumb to the all_thumb_stitches array
                all_thumb_stitches.append(path_to_thumb)

                LOG.debug("Processing stitch '{}' (Progress: {}/{})".format(stitch_key, counter, dimensions['horizontal_divide_by'] * dimensions['vertical_divide_by']))
                LOG.debug("Composed by:\n"
                          "X tiles {}-{}\n"
                          "Y tiles {}-{}".format(start_x_tile,
                                                 end_x_tile - 1,
                                                 start_y_tile,
                                                 end_y_tile - 1))

                counter += 1

        self._inStitchingQueue.join()

        pbar.finish()

        LOG.info("Generating image index...")
        # Make a "clean" index (no labels)
        index_file = '{}-index.png'.format(stitches_path)
        montage = executeCommand()
        if not os.path.isfile(index_file):
            montage_cmd = ['gm', 'montage']
            montage_cmd.extend(all_thumb_stitches)
            montage_cmd.extend(['-tile', '{}x{}'.format(dimensions['horizontal_divide_by'], dimensions['vertical_divide_by']), '-background', 'white', '-geometry', '+1+1', index_file])
            montage.execute(montage_cmd)

        if montage.getReturnCode() != 0 and montage.getReturnCode() is not None:
            LOG.error("ERROR: Could not generate image index '{}".format(index_file))
        else:
            LOG.info("Image index '{}' was generated successfully.".format(index_file))

        # Make one more index with labels
        index_file = '{}-index-labeled.png'.format(stitches_path)
        if not os.path.isfile(index_file):
            montage_cmd = ['gm', 'montage', '-draw', 'gravity South fill red stroke red text 0,7 "%f"', '-pointsize', '16']
            montage_cmd.extend(all_thumb_stitches)
            montage_cmd.extend(['-tile', '{}x{}'.format(dimensions['horizontal_divide_by'], dimensions['vertical_divide_by']), '-background', 'white', '-geometry', '+1+1', index_file])
            montage.execute(montage_cmd)

        if montage.getReturnCode() != 0 and montage.getReturnCode() is not None:
            LOG.error("ERROR: Could not generate image index '{}".format(index_file))
        else:
            LOG.info("Image index '{}' was generated successfully.".format(index_file))

    #----------------------------------------------------------------------
    def calibrate_tiles(self, tile_west, tile_east, tile_north, tile_south):
        """
        Calibrate stitched tiles for a given zoom level in the given max dimensions
        """

        dimensions = self._calculate_max_dimensions_per_stitch(tile_west, tile_east, tile_north, tile_south)

        total_stitches = dimensions['vertical_divide_by'] * dimensions['horizontal_divide_by']
        myProgressBarFd = sys.stderr
        # If log level is set to 1000 (logging is disabled), or DEBUG, then redirect
        # the progress bar to /dev/null (use os.devnull to support windows as well)
        if LOG.getEffectiveLevel() == 1000 or LOG.getEffectiveLevel() == logging.DEBUG:
            myProgressBarFd = open(os.devnull, "w")

        widgets = ['Calibrating stitches: ', progressbar.Counter(format='%{}d'.format(len(str(total_stitches)))), '/{}: '.format(total_stitches),
                   progressbar.Percentage(), ' ', progressbar.Bar(marker='#'), ' ', progressbar.RotatingMarker(), ' ', progressbar.ETA()]

        pbar = progressbar.ProgressBar(widgets = widgets, maxval = total_stitches, fd = myProgressBarFd).start()

        stitches_path = os.path.join(self.project_folder, "stitched_maps", str(zoom))
        if not os.path.isdir(stitches_path):
            os.makedirs(stitches_path)

        for y in xrange(dimensions['vertical_divide_by']):
            for x in xrange(dimensions['horizontal_divide_by']):
                # The filename and extension is used in the ozi .map file, to find the matching image map
                filename = '{}_{}'.format(y, x)
                # TODO: Add a command line option so that the user can choose either to save on the original format, always convert to jpg, or convert to png.
                extension = 'png'

                map_file = os.path.join(stitches_path, '{}.{}'.format(filename, 'map'))

                # First find the corresponding pixels in the global map.
                # Use +1 because if tile_west = 0, then this will return pixel number 0. while it should return pixel 1
                # tile_west = 1 this will return 256+1 (the first pixel of the 1st tile) etc.
                WesternMost_xpixel = tile_west * self._tile_width + 1
                NorthernMost_ypixel = tile_north * self._tile_height + 1

                W_xpixel = WesternMost_xpixel + x * dimensions['horizontal_resolution_per_stitch']
                E_xpixel = WesternMost_xpixel + (x + 1) * dimensions['horizontal_resolution_per_stitch'] - 1
                N_ypixel = NorthernMost_ypixel + y * dimensions['vertical_resolution_per_stitch']
                S_ypixel = NorthernMost_ypixel + (y + 1) * dimensions['vertical_resolution_per_stitch'] - 1

                # Then use the pixel2deg function to get the longtitude and latitude of the stitched tile
                N_deg, W_deg = self.pixel2deg(W_xpixel, N_ypixel, self._tile_width, self._tile_height)
                S_deg, E_deg = self.pixel2deg(E_xpixel, S_ypixel, self._tile_width, self._tile_height)

                pbar.currval += 1
                pbar.update(pbar.currval)

                LOG.debug("Calibrating file '{}.{}' -> '{}'".format(filename, extension, map_file))

                # And finally we save the map file in a file.
                with open(map_file, 'w+') as f:
                    f.write(
                        self.generate_OZI_map_file(
                            filename,
                            extension,
                            dimensions['horizontal_resolution_per_stitch'],
                            dimensions['vertical_resolution_per_stitch'],
                            self.zoom,
                            N_deg, S_deg, W_deg, E_deg
                        )
                    )

        pbar.finish()

#----------------------------------------------------------------------
def DrawableMapNorth(x, y, size = 100, anchor = 'lowerleft'):
    """
    x: An integer for x placement
    y: An integer for y placement
    size: Size of x of the drawable. Size of y is a little bit more than x.
    color: A pgmagick.Color of the drawable.
    anchor: defines which corner of the N will be placed at x, y
            Accepted values:
               lowerleft,
               lowerright
               upperleft
               upperright
               middle
               bottom
               top
               left
               right

    Returns a pgmagick drawable

    # Since I cannot change the opacity of the text (when I do, I see a semitransparent box
    # behind the text, but the opacity of the text itself is not chaning), draw an 'N' with
    # a drawable polyline.
    #
    # To draw an N, we need a polyline with 10 points at the coordinates illustrated below:
    #               2__3 5_6
    #               |  \ | |
    #               |   \| |
    #               | 9  4 |
    #               | |\   |
    #               |_| \__|
    #              1 10 8  7
    #
    """
    anchor_vals = ('lowerleft', 'lowerright', 'upperleft', 'upperright', 'middle', 'bottom', 'top', 'left', 'right')
    if anchor not in anchor_vals:
        print "Wrong Anchor value. Available values are:\n{}".format(anchor_vals)
        raise KeyError

    north = pgmagick.DrawableList()
    coords = pgmagick.CoordinateList()

    # Use the multipliers for each point, in order to be able to resize the 'N'
    # If you don't like the look of the generated n, change the values of x_p and
    # y_p array. Do not change x_p[1] and x_p[4]. The values
    # should be proportinal to x_p[1] and x_p[4], and x_p[1] should be 1 and
    # x_p[4] should be 2.
    # x_p[1] and y_p[1] is the lower left point of the drawn 'N'
    x_p = {
        1: 1,
        2: 1.3,
        3: 1.7,
        4: 2
    }
    y_p = {
        4: 0.06,
        3: 0.70125,
        2: 0.53625,
        1: 1.2
    }

    # Do not change anything after this point

    n_width = size * abs(x_p[4] - x_p[1])
    n_height = size * abs(y_p[1] - y_p[4])

    if anchor == 'lowerleft':
        anchor_x = 0
        anchor_y = 0
    elif anchor == 'lowerright':
        anchor_x = n_width
        anchor_y = 0
    elif anchor == 'upperleft':
        anchor_x = 0
        anchor_y = -n_height
    elif anchor == 'upperright':
        anchor_x = n_width
        anchor_y = -n_height
    elif anchor == 'middle':
        anchor_x = n_width / 2
        anchor_y = -n_height / 2
    elif anchor == 'bottom':
        anchor_x = n_width / 2
        anchor_y = 0
    elif anchor == 'top':
        anchor_x = n_width / 2
        anchor_y = -n_height
    elif anchor == 'left':
        anchor_x = 0
        anchor_y = -n_height / 2
    elif anchor == 'right':
        anchor_x = n_width
        anchor_y = -n_height / 2


    x_multipliers = [x_p[1], x_p[1], x_p[2], x_p[3], x_p[3], x_p[4], x_p[4], x_p[3], x_p[2], x_p[2]]
    y_multipliers = [y_p[1], y_p[4], y_p[4], y_p[3], y_p[4], y_p[4], y_p[1], y_p[1], y_p[2], y_p[1]]
    subtract_x = 0
    subtract_y = 0
    for i in xrange(10):
        x_point = size * x_multipliers[i]
        y_point = size * y_multipliers[i]
        if i == 0:
            subtract_x = x_point - x
            subtract_y = y_point - y
        x_point = x_point - subtract_x - anchor_x
        y_point = y_point - subtract_y - anchor_y
        coords.append(pgmagick.Coordinate(x_point, y_point))

    north.append(pgmagick.DrawablePolygon(coords))

    return north

#----------------------------------------------------------------------
def DrawableMapCompass(x, y, radius = 100, anchor = 'lowerleft'):
    """
    Draw a compass on the map of 'radius' size (the actual size is radius * 2)
    """
    anchor_vals = ('lowerleft', 'lowerright', 'upperleft', 'upperright', 'middle', 'bottom', 'top', 'left', 'right')
    if anchor not in anchor_vals:
        print "Wrong Anchor value. Available values are:\n{}".format(anchor_vals)
        raise KeyError

    compass = pgmagick.DrawableList()
    black = pgmagick.Color('black')
    white = pgmagick.Color('white')

    # Do not change the central_point! This will always have to be 1, 1
    central_point = {
        'x': 1,
        'y': 1
    }
    # All of the offsets will be added-subtracted from the central_point
    # Do not change offsets[1]
    offsets = {
        1: (0.15, -0.15),
        2: (0, -1)
    }

    n_radius = radius * abs(central_point['x'] - central_point['x'] + offsets[2][1])

    if anchor == 'lowerleft':
        anchor_x = 0
        anchor_y = -n_radius * 2
    elif anchor == 'lowerright':
        anchor_x = -n_radius * 2
        anchor_y = -n_radius * 2
    elif anchor == 'upperleft':
        anchor_x = 0
        anchor_y = 0
    elif anchor == 'upperright':
        anchor_x = -n_radius * 2
        anchor_y = 0
    elif anchor == 'middle':
        anchor_x = -n_radius
        anchor_y = -n_radius
    elif anchor == 'bottom':
        anchor_x = -n_radius
        anchor_y = -n_radius * 2
    elif anchor == 'top':
        anchor_x = -n_radius
        anchor_y = 0
    elif anchor == 'left':
        anchor_x = 0
        anchor_y = -n_height
    elif anchor == 'right':
        anchor_x = -n_width * 2
        anchor_y = -n_height

    x_p_center = central_point['x'] * radius + x + anchor_x
    y_p_center = central_point['y'] * radius + y + anchor_y

    # Make the white parts of the compass first (white fill, black stroke)
    compass.append(pgmagick.DrawableStrokeColor(black))
    compass.append(pgmagick.DrawableFillColor(white))

    # Draw a circle with a thickness relative to the size for every 50 pixels size, add 1 pixel in the thickness
    r = int(radius * 0.55)
    circle_thickness = int(radius / 15)
    compass.append(pgmagick.DrawableStrokeWidth(circle_thickness))
    compass.append(pgmagick.DrawableCircle(x_p_center, y_p_center, x_p_center + r, y_p_center + r))

    # Change back to a thin stroke for the rest
    compass.append(pgmagick.DrawableStrokeWidth(1))

    coords = pgmagick.CoordinateList()
    coords.append(pgmagick.Coordinate(x_p_center, y_p_center))
    # For i = 0 we build the north half arrow
    # ....i = 1, east
    # ....i = 2, south
    # ....i = 3, west
    # Except the central points, each half compass arrow, has two more points
    # We use j to build these two points.
    for i in (0, 1, 2, 3):
        for j in (1, 2):
            if i == 0:
                x_p = radius * (central_point['x'] - offsets[j][0]) + x + anchor_x
                y_p = radius * (central_point['y'] + offsets[j][1]) + y + anchor_y
            elif i == 1:
                x_p = radius * (central_point['x'] - offsets[j][1]) + x + anchor_x
                y_p = radius * (central_point['y'] - offsets[j][0]) + y + anchor_y
            elif i == 2:
                x_p = radius * (central_point['x'] + offsets[j][0]) + x + anchor_x
                y_p = radius * (central_point['y'] - offsets[j][1]) + y + anchor_y
            elif i == 3:
                x_p = radius * (central_point['x'] + offsets[j][1]) + x + anchor_x
                y_p = radius * (central_point['y'] + offsets[j][0]) + y + anchor_y

            coords.append(pgmagick.Coordinate(x_p, y_p))
        coords.append(pgmagick.Coordinate(x_p_center, y_p_center))
    compass.append(pgmagick.DrawablePolygon(coords))

    # Make the black parts of the compass (black fill, black stroke)
    compass.append(pgmagick.DrawableFillColor(black))

    coords = pgmagick.CoordinateList()
    coords.append(pgmagick.Coordinate(x_p_center, y_p_center))
    for i in (0, 1, 2, 3):
        for j in (1, 2):
            if i == 0:
                x_p = radius * (central_point['x'] + offsets[j][0]) + x + anchor_x
                y_p = radius * (central_point['y'] + offsets[j][1]) + y + anchor_y
            elif i == 1:
                x_p = radius * (central_point['x'] - offsets[j][1]) + x + anchor_x
                y_p = radius * (central_point['y'] + offsets[j][0]) + y + anchor_y
            elif i == 2:
                x_p = radius * (central_point['x'] - offsets[j][0]) + x + anchor_x
                y_p = radius * (central_point['y'] - offsets[j][1]) + y + anchor_y
            elif i == 3:
                x_p = radius * (central_point['x'] + offsets[j][1]) + x + anchor_x
                y_p = radius * (central_point['y'] - offsets[j][0]) + y + anchor_y

            coords.append(pgmagick.Coordinate(x_p, y_p))
        coords.append(pgmagick.Coordinate(x_p_center, y_p_center))
    compass.append(pgmagick.DrawablePolygon(coords))

    return compass

#----------------------------------------------------------------------
def DrawableMapGrid(map_width, map_height, canvas_margin, thickness = 2, x_grid_by = 256, y_grid_by = 256):
    """
    Draw the Grid for the given map width and height.

    The grid will be placed every approximately x_grid_by and y_grid_by pixels.
    This is approximate, because the grid will be stretched in order to generate
    equally distributed grid lines, and at least two grid lines should be located at
    the edges.
    For example, if the x_grid_by = 256 and the map_width = 512 the 3 grid lines
    will be generated: at x = 1, x=257 and x=512. In these values, the canvas_margin
    size is added. If the x_grid_by = 256 and the map_width = 544, then the x_lines will
    be placed at 1, 273, 544.

    The calculated x/y values where the grid lines will be placed are the central values.
    If the grid thickness is more than 1 pixels (2 by default), the grid will be
    distributed around this central value.
    """
    grid = pgmagick.DrawableList()

    x_grid_by = x_grid_by + (map_width % x_grid_by / float(int(map_width / x_grid_by)))
    y_grid_by = y_grid_by + (map_height % y_grid_by / float(int(map_height / y_grid_by)))

    for central_x_pos in xfrange(canvas_margin, map_width + canvas_margin + 1, x_grid_by):
        # central_x is a float, but we want an integer in order to draw in a pixel,
        # so round the value of central_x to the nearest integer
        central_x_pos = round(central_x_pos)
        for t in xrange(thickness):
            x = central_x_pos - int(thickness / 2) + t
            y1 = 0
            y2 = map_height + 2 * canvas_margin
            grid.append(pgmagick.DrawableLine(x, y1, x, y2))

    for central_y_pos in xfrange(canvas_margin, map_height + canvas_margin + 1, y_grid_by):
        central_y_pos = round(central_y_pos)
        for t in xrange(thickness):
            y = central_y_pos - int(thickness / 2) + t
            x1 = 0
            x2 = map_width + 2 * canvas_margin
            grid.append(pgmagick.DrawableLine(x1, y, x2, y))

    return grid

#----------------------------------------------------------------------
def DrawableMapLabels(map_width, map_height, canvas_margin, fontsize = 80, x_grid_by = 256, y_grid_by = 256):
    """
    Draw the labels on the sides of the canvas

    This function could be merged with the DrawableMapGrid function
    but we keep it separate for fine tuning. The grid for example may need to be
    semitransparent, but the labels should not
    """
    labels = pgmagick.DrawableList()

    fontname = 'FreeSans'
    labels.append(pgmagick.DrawableFont(fontname, pgmagick.StyleType.NormalStyle, 600, pgmagick.StretchType.NormalStretch))
    labels.append(pgmagick.DrawablePointSize(fontsize))
    labels.append(pgmagick.DrawableGravity(pgmagick.GravityType.NorthWestGravity))

    # Use an image object, in order to make use of the fontmetrics capability.
    text = pgmagick.Image()
    text.fontPointsize(fontsize)
    text.font(fontname)
    fontmetric = pgmagick.TypeMetric()

    x_grid_by = x_grid_by + (map_width % x_grid_by / float(int(map_width / x_grid_by)))
    y_grid_by = y_grid_by + (map_height % y_grid_by / float(int(map_height / y_grid_by)))

    ascii_chr = [65] # ASCII 65 = A
    for x in xfrange(canvas_margin, map_width + canvas_margin, x_grid_by):
        x = round(x)
        lab = ''.join(chr(i) for i in ascii_chr)
        pgmagick.Image.fontTypeMetrics(text, lab, fontmetric)
        labels.append(pgmagick.DrawableText(x + int(x_grid_by / 2) - int(fontmetric.textWidth() / 2), canvas_margin - 30 , lab))
        labels.append(pgmagick.DrawableText(x + int(x_grid_by / 2) - int(fontmetric.textWidth() / 2),
                                            map_height + canvas_margin + 30 + (fontmetric.ascent() + fontmetric.descent()), lab))
        # If we reached Z, start counting from AA, AB, AC etc...
        # This if so far it will only work until ZZ which I think is more than enough.
        if ascii_chr[len(ascii_chr) - 1] < 90: # ASCII 90 = Z
            ascii_chr[len(ascii_chr) - 1] += 1
        else:
            if len(ascii_chr) == 1:
                ascii_chr[0] = 65
                ascii_chr.append(65)
            else:
                ascii_chr[0] += 1
                ascii_chr[1] = 65

    lab = 1
    for y in xfrange(canvas_margin, map_height + canvas_margin, y_grid_by):
        y = round(y)
        pgmagick.Image.fontTypeMetrics(text, str(lab), fontmetric)
        # http://www.graphicsmagick.org/Magick++/TypeMetric.html
        labels.append(pgmagick.DrawableText(canvas_margin - fontmetric.textWidth() - 30,
                                            y + int(y_grid_by / 2) + int((fontmetric.ascent() + fontmetric.descent()) / 2), str(lab)))
        labels.append(pgmagick.DrawableText(map_width + canvas_margin + 30,
                                            y + int(y_grid_by / 2) + int((fontmetric.ascent() + fontmetric.descent()) / 2), str(lab)))
        lab += 1

    return labels

#----------------------------------------------------------------------
def DrawableScaleRuler(x, y, latitude_mid_of_tile, zoom, rulersize = 16, anchor = 'lowerleft'):
    """
    The ruler size defines the thickness of the ruler.

    The actual height of the ruler will be its thickness plus the tick marks and the labels.

    The zoom level the openstreetmap zoom level for the specified stitched image.

    The formula to calculate the horizontalMetersPerPixel is the same with the formula used for MMB1
    calculation when calibrating OziExplorer files. Look at the function generate_OZI_map_file() for
    more details

    # TODO: Change all occurences of '2**(zoom+8)' to 'self._tile_width*(2**8)', because if we export
            tiles of different size
    #       zoom+8 will not be valid. The +8 part is coming for the fact that 256 = 2**8
    """
    anchor_vals = ('lowerleft', 'lowerright', 'upperleft', 'upperright', 'middle', 'bottom', 'top', 'left', 'right')
    if anchor not in anchor_vals:
        print "Wrong Anchor value. Available values are:\n{}".format(anchor_vals)
        raise KeyError

    horizontalMetersPerPixel = 40075017 * math.cos(latitude_mid_of_tile / 180.0 * math.pi) / 2**(zoom+8)

    ruler = pgmagick.DrawableList()
    black = pgmagick.Color('black')
    white = pgmagick.Color('white')

    fontname = 'FreeSans'
    fontsize = rulersize
    ruler.append(pgmagick.DrawableFont(fontname, pgmagick.StyleType.NormalStyle, 100, pgmagick.StretchType.NormalStretch))
    ruler.append(pgmagick.DrawablePointSize(fontsize))
    ruler.append(pgmagick.DrawableGravity(pgmagick.GravityType.NorthWestGravity))

    # Use an image object, in order to make use of the fontmetrics capability.
    text = pgmagick.Image()
    text.fontPointsize(fontsize)
    text.font(fontname)
    fontmetric = pgmagick.TypeMetric()
    # The tallest text we use in the ruler is the letter 'k'
    # So get its height in order to add it to the anchor_y
    max_text_height = pgmagick.TypeMetric()
    pgmagick.Image.fontTypeMetrics(text, 'k', max_text_height)

    # We want the ruler to be at least size pixels in height.
    # If the ruler is height pixels, the width should be around 14 * height
    # In the width, we will draw two ruler blocks.
    height = rulersize
    half_width = height * 7

    m = int(half_width * horizontalMetersPerPixel)
    m_lab = "m"
    len_m = len(str(m))

    if  m > 1000:
        # If the half length of the width is more than 1000 meters,
        # round to the nearest major number in km.
        m = int(round(m, -len_m + 1))
        m = m / 1000
        m_lab = "km"
        # Now we have km. If the values are less than 10000 km, round
        # them to the nearest 1, 2, 3, 5
        if m < 10000 and m > 3000:
            m = int(round(m / 5000.0) * 5000)
        elif m < 1000 and m > 300:
            m = int(round(m / 500.0) * 500)
        elif m < 100 and m > 30:
            m = int(round(m / 50.0) * 50)
        elif m < 10 and m > 3:
            m = int(round(m / 5.0) * 5)
    else:
        m = int(round(m, -len_m + 1))
        if m < 1000 and m > 300:
            m = int(round(m / 500.0) * 500)
        elif m < 100 and m > 30:
            m = int(round(m / 50.0) * 50)
        elif m < 10 and m > 3:
            m = int(round(m / 5.0) * 5)

    if m_lab == 'm':
        actual_pixels_for_half_width = horizontalMetersPerPixel * half_width
    elif m_lab == 'km':
        actual_pixels_for_half_width = (horizontalMetersPerPixel / 1000) * half_width

    reformed_half_width = int(round((m / actual_pixels_for_half_width) * half_width))
    width = reformed_half_width * 2

    # The height variable holds only the height of the bar.
    # The actual height is more, because we add tick marks and labels.
    # So the anchor_height must take into account these additional pixels.
    #
    # If I want to be 100% accurate, I have to take into account the text on the right and left
    # of the bar and change the width accordingly as well, but that's not much so I do not bother now.
    anchor_height = height + (3.5 * height / 4) + max_text_height.textHeight() - max_text_height.ascent() - max_text_height.descent()
    if anchor == 'lowerleft':
        anchor_x = 0
        anchor_y = height
    elif anchor == 'lowerright':
        anchor_x = width
        anchor_y = height
    elif anchor == 'upperleft':
        anchor_x = 0
        anchor_y = -(anchor_height)
    elif anchor == 'upperright':
        anchor_x = width
        anchor_y = -anchor_height
    elif anchor == 'middle':
        anchor_x = width / 2
        anchor_y = -anchor_height / 2
    elif anchor == 'bottom':
        anchor_x = width / 2
        anchor_y = height
    elif anchor == 'top':
        anchor_x = width / 2
        anchor_y = -anchor_height
    elif anchor == 'left':
        anchor_x = 0
        anchor_y = -anchor_height / 2
    elif anchor == 'right':
        anchor_x = width
        anchor_y = -anchor_height / 2

    ruler.append(pgmagick.DrawableStrokeColor(black))
    # Generate major/minor ticks
    y_pos_1 = y - anchor_y
    counter = 0
    prev_lab = 0
    lab = 0
    for x_pos in xfrange(x, x + width + 1, width / 20.0):
        # Every 10th tick, we need a major tick
        # Every 5th tick we need an intermediate tick
        if counter % 10 == 0:
            y_pos_2 = y - int((3.5 * height / 4))
            if counter:
                prev_lab += m
                lab = '{} {}'.format(prev_lab, m_lab)
            else:
                lab = prev_lab
        elif counter % 5 == 0:
            y_pos_2 = y - (height / 2)
        else:
            y_pos_2 = y - (height / 4)
            lab = None
        x_pos = int(round(x_pos)) - anchor_x
        y_pos_2 = y_pos_2 - anchor_y

        if lab is not None:
            pgmagick.Image.fontTypeMetrics(text, str(lab), fontmetric)
            x_lab_pos = x_pos - fontmetric.textWidth() / 2
            y_lab_pos = y_pos_1 - height
            ruler.append(pgmagick.DrawableText(x_lab_pos, y_lab_pos, str(lab)))

        ruler.append(pgmagick.DrawableLine(x_pos, y_pos_1, x_pos, y_pos_2))
        counter += 1

    ruler.append(pgmagick.DrawableFillColor(white))
    ruler.append(pgmagick.DrawableRectangle(x - anchor_x,
                                            y - anchor_y,
                                            x + reformed_half_width - anchor_x,
                                            y + height - anchor_y))
    ruler.append(pgmagick.DrawableFillColor(black))
    ruler.append(pgmagick.DrawableRectangle(x + reformed_half_width - anchor_x,
                                            y - anchor_y,
                                            x + width - anchor_x,
                                            y + height - anchor_y))

    return ruler

#----------------------------------------------------------------------
def prepareStitchForPrint(mapInputFile, zoom, outputFile, N, S, W, E):
    """
    This function will generate a stitched tile with labeled grid, a compass and a scale ruler.
    Useful for printouts.

    mapfile: The source file to prepare for printout
    zoom: The zoom level that is used by this file

    N, S, W, E are the corresponding edge coordinates of the mapInputFile.

    # TODO: Add an option to let use choose paper-type friendly stitches (A4, A3 etc...)
    #       Then the function should cut the maps in smaller part so that they can fit in the
    #       chosen paper type without shrinking.
    """
    # Read the image
    img = pgmagick.Image(mapInputFile)
    # Create a canvas
    canvas_margin_px = 144
    canvas_width = img.columns() + canvas_margin_px * 2
    canvas_height = img.rows() + canvas_margin_px * 2
    canvas_geometry = pgmagick.Geometry(canvas_width, canvas_height)
    canvas = pgmagick.Image(canvas_geometry, pgmagick.Color("white"))
    # Add the image in the canvas
    canvas.composite(img, pgmagick.GravityType.CenterGravity)

    # Draw semitransparent grid
    grid = DrawableMapGrid(img.columns(), img.rows(), canvas_margin_px)
    grid.append(pgmagick.DrawableFillOpacity(0.3))
    canvas.draw(grid)

    # Add labels on the canvas margin
    labels = DrawableMapLabels(img.columns(), img.rows(), canvas_margin_px)
    canvas.draw(labels)

    # Add a compass widget
    compass_size = 110
    compass_coords = (canvas.columns() - canvas_margin_px - 20, canvas_margin_px + 80)
    compass = DrawableMapCompass(compass_coords[0], compass_coords[1], compass_size, anchor='upperright')
    canvas.draw(compass)

    # Add an 'N' on top of the compass to indicate where the north is.
    north_size = int(compass_size / 2.5)
    north_coords = (compass_coords[0] - compass_size, compass_coords[1] - 10)
    north = DrawableMapNorth(north_coords[0], north_coords[1], north_size, anchor='bottom')
    canvas.draw(north)

    # Add a ruler widget to indicate the scale of the map.
    latMidTile = S + (N - S) / 2.0
    ruler = DrawableScaleRuler(canvas_margin_px + 100, img.rows() + canvas_margin_px - 100, latMidTile, zoom, 35)
    canvas.draw(ruler)

    # Save the file in the outputFile
    canvas.write(outputFile)

#----------------------------------------------------------------------
if __name__ == '__main__':
    """
    Write the main program here
    """
    # Parse the command line options
    options = _command_Line_Options()
    # Configure logging
    _configureLogging(options.loglevel)
    # Validate the command line arguments
    validate_arguments(options)

    LOG.info("Welcome to " + PROGRAM_NAME + " v" + str(VERSION))
    LOG.info("----------------------------------\n")

    #print options
    try:

        for zoom in options.zoom_level:
            zoom_folder = os.path.join(options.project_folder, str(zoom))
            if not os.path.isdir(zoom_folder):
                os.mkdir(zoom_folder)

            tileWorker = stitch_osm_tiles(zoom = zoom,
                                          saved_tile_format = options.tile_format,
                                          tile_servers = options.tile_servers,
                                          project_folder = options.project_folder,
                                          max_dimensions = options.max_resolution_px,
                                          parallelDownloadThreads = options.download_threads,
                                          parallelStitchingThreads = options.stitching_threads
                                          )

            tile_west, tile_north = tileWorker.deg2tilenums(options.lat1, options.long1)
            tile_east, tile_south = tileWorker.deg2tilenums(options.lat2, options.long2)

            number_of_horizontal_tiles = (tile_east - tile_west) + 1
            number_of_vertical_tiles = (tile_south - tile_north) + 1
            total_tiles = number_of_horizontal_tiles * number_of_vertical_tiles

            # Prepare the configuration dictionary
            # The configuration dictionary a two levels nested dictionary. The top level key
            # is the config option, each top level key has dictionary value. The key of the dictionary value
            # is the actualy configuration value, and the value of the value is a number 0 or 1.
            # 0 indicates that this config option is informative, and 1 indicated that this option must
            # match on subsequent runs.
            # E.g., for the config_dict['tile_format'] = {options.tile_format: 1}
            #       'tile_format' is the option saved in the config file, and the value of the option
            #       is options.tile_format. The value of the nested dict which is '1', indicates that
            #       if we re-run the script, the 'tile_format' provided by the command line options should
            #       be the same as the one used the first time we ran the script and this conf file was
            #       generated.
            config_dict = OrderedDict()
            config_dict['project_folder'] = {str(options.project_folder): 0}
            config_dict['provider'] = {options.tile_server_provider: 1}
            config_dict['overlay'] = {options.tile_server_provider_layer: 1} if options.tile_server_provider_layer else {"": 0}
            config_dict['tile_format'] = {options.tile_format: 1}
            config_dict['zoom'] = {str(zoom): 1}
            config_dict['longtitude1-west'] = {str(options.long1): 1}
            config_dict['longtitude2-east'] = {str(options.long2): 1}
            config_dict['latitude1-north'] = {str(options.lat1): 1}
            config_dict['latitude2-south'] = {str(options.lat2): 1}
            config_dict['tile_west'] = {str(tile_west): 1}
            config_dict['tile_east'] = {str(tile_east): 1}
            config_dict['tile_north'] = {str(tile_north): 1}
            config_dict['tile_south'] = {str(tile_south): 1}
            config_dict['total_tiles'] = {str(total_tiles): 1}
            config_dict['degrees_by_western_most_tile'] = {str(tileWorker.tilenums2deg(tile_west, tile_north)[1]): 1}
            config_dict['degrees_by_northern_most_tile'] = {str(tileWorker.tilenums2deg(tile_west, tile_north)[0]): 1}
            config_dict['degrees_by_eastern_most_tile'] = {str(tileWorker.tilenums2deg(tile_east + 1, tile_south + 1)[1]): 1}
            config_dict['degrees_by_southern_most_tile'] = {str(tileWorker.tilenums2deg(tile_east + 1, tile_south + 1)[0]): 1}
            config_dict['max_resolution'] = {str(options.max_resolution_px): 1}

            # Check if there is an existing config file, and if the necessary config
            # values do match, warn the user and exit.
            zoom_conf, main_config_section = read_zoom_config(zoom, config_dict)

            # Write the configuration in a conf file
            write_zoom_config(zoom_conf, config_dict, main_config_section)

            if not options.skip_downloading and not options.only_calibrate:
                tileWorker.download_tiles(tile_west, tile_east, tile_north, tile_south)
            else:
                LOG.info("Skipping tile downloading as requested.")

            # Get the dimensions after we are sure that the files have been downloaded, since we need to know the size
            # of the original tiles in order to calculate this.
            dimensions = tileWorker._calculate_max_dimensions_per_stitch(tile_west, tile_east, tile_north, tile_south)

            config_dict['total_stitched_tiles'] = {'{} ({}x{})'.format(dimensions['horizontal_divide_by'] * dimensions['vertical_divide_by'],
                                                                      dimensions['horizontal_divide_by'],
                                                                      dimensions['vertical_divide_by']): 0}
            config_dict['resolution_per_stitch'] = {'{}x{} px ({} MPixels)'.format(dimensions['horizontal_resolution_per_stitch'],
                                                                                  dimensions['vertical_resolution_per_stitch'],
                                                                                  round(dimensions['horizontal_resolution_per_stitch'] * dimensions['vertical_resolution_per_stitch'] / 1000000.0, 1)): 0}
            write_zoom_config(zoom_conf, config_dict, main_config_section)

            if not options.skip_stitching and not options.only_calibrate:
                tileWorker.stitch_tiles(tile_west, tile_east, tile_north, tile_south)
            else:
                LOG.info("Skipping tile stitching as requested.")

            if not options.skip_stitching or options.only_calibrate:
                tileWorker.calibrate_tiles(tile_west, tile_east, tile_north, tile_south)

            # If the user has asked to prepare paper friendly maps, do it now.
            if options.printout:
                total_tiles = dimensions['horizontal_divide_by'] * dimensions['vertical_divide_by']

                myProgressBarFd = sys.stderr
                # If log level is set to 1000 (logging is disabled), or DEBUG, then redirect
                # the progress bar to /dev/null (use os.devnull to support windows as well)
                if LOG.getEffectiveLevel() == 1000 or LOG.getEffectiveLevel() == logging.DEBUG:
                    myProgressBarFd = open(os.devnull, "w")

                widgets = ['Preparing paper friendly maps ', progressbar.Counter(format='%{}d'.format(len(str(total_tiles)))), '/{}: '.format(total_tiles),
                           progressbar.Percentage(), ' ', progressbar.Bar(marker='#'), ' ', progressbar.RotatingMarker(), ' ', progressbar.ETA()]

                pbar = progressbar.ProgressBar(widgets = widgets, maxval = total_tiles, fd = myProgressBarFd).start()

                printer_maps_path = os.path.join(options.project_folder, "paper_maps", str(zoom))
                if not os.path.isdir(printer_maps_path):
                    os.makedirs(printer_maps_path)
                for y in xrange(dimensions['horizontal_divide_by']):
                    for x in xrange(dimensions['vertical_divide_by']):
                        inputFile = os.path.join(options.project_folder, "stitched_maps", str(zoom), '{}_{}.png'.format(x, y))
                        outputFile = os.path.join(printer_maps_path, '{}_{}_print.png'.format(x, y))
                        if os.path.isfile(inputFile):
                            if not os.path.isfile(outputFile):
                                mapCalibrationFile = os.path.join(options.project_folder, "stitched_maps", str(zoom), '{}_{}.map'.format(x, y))
                                if os.path.isfile(mapCalibrationFile):
                                    r = quick_regexp()
                                    N = S = W = E = None
                                    with open(mapCalibrationFile) as f:
                                        for line in f:
                                            if r.search('MMPLL\s*,\s*1\s*,\s*(.+)\s*,\s*(.+)', line):
                                                W = float(r.groups[0])
                                                N = float(r.groups[1])
                                            elif r.search('MMPLL\s*,\s*3\s*,\s*(.+)\s*,\s*(.+)', line):
                                                E = float(r.groups[0])
                                                S = float(r.groups[1])

                                    if (N == None or S == None or W == None or E == None):
                                        error_and_exit("Could not read the coordinates from the map file '{}' properly.".format(mapCalibrationFile))

                                    prepareStitchForPrint(inputFile, zoom, outputFile, N, S, W, E)
                                    pbar.currval += 1
                                else:
                                    error_and_exit("Looked for {}, but I could not locate the specified map calibration file.\n"
                                                   "The map calibration file is needed in order to calculate the scale of the map.".format(mapCalibrationFile))
                            pbar.update(pbar.currval)
                        else:
                            error_and_exit("File '{}' not found.\nYou need to stitch the necessary files before creating paper friendly maps.".format(inputFile))

                pbar.finish()

            properties = """Provider: {}
Overlay: {}
Tile Format: {}
Zoom: {}
longtitude1 (W): {}
longtitude2 (E): {}
latitude1 (N): {}
latitude2 (S): {}
tile_west: {}
tile_east: {}
tile_north: {}
tile_south: {}
total_tiles: {}
W_degrees_by_western_most_tile: {}
N_degrees_by_northern_most_tile: {}
E_degrees_by_eastern_most_tile: {}
S_degrees_by_southern_most_tile: {}
max_resolution: {}
total_stitched_tiles: {}
resolution_per_stitch: {}""".format(
                                config_dict['provider'].keys().pop(),
                                config_dict['overlay'].keys().pop(),
                                config_dict['tile_format'].keys().pop(),
                                config_dict['zoom'].keys().pop(),
                                config_dict['longtitude1-west'].keys().pop(),
                                config_dict['longtitude2-east'].keys().pop(),
                                config_dict['latitude1-north'].keys().pop(),
                                config_dict['latitude2-south'].keys().pop(),
                                config_dict['tile_west'].keys().pop(),
                                config_dict['tile_east'].keys().pop(),
                                config_dict['tile_north'].keys().pop(),
                                config_dict['tile_south'].keys().pop(),
                                config_dict['total_tiles'].keys().pop(),
                                config_dict['degrees_by_western_most_tile'].keys().pop(),
                                config_dict['degrees_by_northern_most_tile'].keys().pop(),
                                config_dict['degrees_by_eastern_most_tile'].keys().pop(),
                                config_dict['degrees_by_southern_most_tile'].keys().pop(),
                                config_dict['max_resolution'].keys().pop(),
                                config_dict['total_stitched_tiles'].keys().pop(),
                                config_dict['resolution_per_stitch'].keys().pop()
                            )
            LOG.info("\n" + properties)

            # To compose two images (satellite with hybrid on top), use the convert command like this:
            #   convert sat-img/11/0_0.png hyb-img/11/0_0.png -composite 0_0.png
            # Use the already generated oziexplorer map files.
            # Of course, the W, E, N, S should be exactly the same for the sat and hyb images.
    except KeyboardInterrupt:
        # If received Ctrl+C, exit without printing a backtrace (change line as well..).
        LOG.critical("\n")
        exit(0)
