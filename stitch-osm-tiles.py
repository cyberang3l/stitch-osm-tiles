#!/usr/bin/env python
# -*- coding: utf8 -*-
#
# Copyright (C) 2014 Vangelis Tasoulas <vangelis@tasoulas.net>
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

import os
import sys
import re
import argparse
import logging
import subprocess   # Needed to execute system commands. If you remove the class "executeCommand", you can safely remove this line as well
import datetime     # If you remove the class "executeCommand", you can safely remove this line as well
import math
import urllib2
import progressbar
import multiprocessing
import Queue
import threading
import time
import pgmagick
import wand
from pgmagick import Image as gmImage
from wand.image import Image as imImage
from wand.display import display as imDisplay
from collections import OrderedDict

__all__ = [
    'quick_regexp', 'print_', 'is_number',
    'trim_list', 'split_strip',
    'executeCommand', 'LOG'
]

# TODO: Add -l -r -t -b for left, right, top, bottom tiles to be downloaded (if the user doesn't want to provide the coordinates)

PROGRAM_NAME = 'stitch-osm-tiles'
VERSION = '0.0.1'
AUTHOR = 'Vangelis Tasoulas'

LOG = logging.getLogger('default.' + __name__)

#----------------------------------------------------------------------
# Define the providers and the layer available by each provider in an ordered dict!
#    Individual layers can override the following parameters: 'tileservers', 'extension', 'zoom_levels'
PROVIDERS = OrderedDict([
    ('Mapquest', {
        'attribution':'Tiles Courtesy of MapQuest',
        'url':'http://www.mapquest.com',
        'tile_servers': [ 'http://otile{alts:1,2,3,4}.mqcdn.com/tiles/1.0.0/{layer}/{z}/{x}/{y}.{ext}' ], # The tile servers that serve the tiles for this provider.
        'extension': 'jpg',     # The default extension support by this provider
        'zoom_levels': '0-18',  # The zoom levels supported by this provider
        'layers': OrderedDict([
            ('map', {
                'desc': 'Default MapQuest Style'
            }),
            ('osm', {
                'desc': 'Default OSM Style'
            }),
            ('sat', {
                'desc': 'Satellite imagery',
                'zoom_levels': '0-11'
            }),
            ('sat2', {
                'name': 'sat',
                'desc': 'Higher Quality Satellite imagery',
                'zoom_levels': '0-13',
                'tile_servers': [
                        'http://ttiles0{alts:1,2,3,4}.mqcdn.com/tiles/1.0.0/vy/{layer}/{z}/{x}/{y}.{ext}'
                ]
            }),
            ('hyb', {
                'desc': 'Hybrid tiles',
                'extension': 'png'
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
            ('toner-hybrid', {}),
            ('toner-labels', {}),
            ('toner-lines', {}),
            ('toner-background', {}),
            ('toner-lite', {}),
            ('watercolor', {})
        ])
    }),

    ('Mapbox', {
        'attribution':'Map tiles by Mapbox',
        'url':'http://www.mapbox.com/about/maps/',
        'tile_servers': [ 'http://{alts:a,b,c,d}.tiles.mapbox.com/v4/{layer}/{z}/{x}/{y}.{ext}?access_token=pk.eyJ1Ijoib3BlbnN0cmVldG1hcCIsImEiOiJncjlmd0t3In0.DmZsIeOW-3x-C5eX-wAqTw' ],
        'extension': 'jpg',
        'zoom_levels': '0-17',
        'layers': OrderedDict([
            ('openstreetmap.map-inh7ifmo', {
                'desc': 'High quality satellite imagery'
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

def _command_Line_Options():
    """
    Define the accepted command line arguments in this function

    Read the documentation of argparse for more advanced command line
    argument parsing examples
    http://docs.python.org/2/library/argparse.html
    """
    # TODO: Add two options to allow the user to choose the download concurrency and stitching concurrency.
    #       Default value for the download concurrency will be 10, and for the stitching concurrency
    #       multiprocessing.cpu_count()

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
                        "Default project name: 'maps_project'")
    parser.add_argument("-z", "--zoom-level",
                        action="store",
                        dest="zoom_level",
                        required=True,
                        help="The tile zoom level for download. Accepts an integer or a range like '1-10' or '1,4,7-9'.")
    parser.add_argument("-w", "--long1",
                        action="store",
                        type=float,
                        dest="long1",
                        metavar="W_DEGREES",
                        required=True,
                        help="Set the western (W) longtitude of a bounding box for tile downloading. Accepted values: -180 to 179.999.")
    parser.add_argument("-e", "--long2",
                        action="store",
                        type=float,
                        dest="long2",
                        metavar="E_DEGREES",
                        required=True,
                        help="Set the eastern (E) longtitude of a bounding box for tile downloading. Accepted values: -180 to 179.999.")
    parser.add_argument("-n", "--lat1",
                        action="store",
                        type=float,
                        dest="lat1",
                        metavar="N_DEGREES",
                        required=True,
                        help="Set the northern (N) latitude of a bounding box for tile downloading. Accepted values: -85.05112 to 85.05113.")
    parser.add_argument("-s", "--lat2",
                        action="store",
                        type=float,
                        dest="lat2",
                        metavar="S_DEGREES",
                        required=True,
                        help="Set the southern (S) latitude of a bounding box for tile downloading. Accepted values: -85.05112 to 85.05113.")
    parser.add_argument("-o", "--custom-osm-server",
                        action="store",
                        dest="custom_osm_server",
                        metavar="OSM_SERVER_URL",
                        help="R|The URL of your private tile server. If the URL\n"
                        "contains the {z}/{x}/{y} placeholders for\n"
                        "substitution, these will be substituted with the\n"
                        "corresponding 'zoom level', 'x' and 'y' tiles during\n"
                        "download. If not, {z}/{x}/{y}.png will be appended\n"
                        "after the end of the provided URL. Example URL:\n"
                        "'http://your.osm.server.com/osm/{z}/{x}/{y}.png?token=12345'")
    parser.add_argument("-m", "--max-stitch-size-per-side",
                        action="store",
                        type=int,
                        default=10000,
                        dest="max_resolution_px",
                        metavar="PIXELS",
                        help="The horizontal or vertical resolution of the final stitched tiles should not exceed that of the --max-stitch-size-per-side.\n"
                        "Default size: 10000 px")
    parser.add_argument("-r", "--retry-failed",
                        action="store_true",
                        dest="retry_failed",
                        help="When the tiles are downloaded, a log file with the tiles that failed to be downloaded is generated."
                        "If --retry-failed option is used, after the tiles have been downloaded the script will go through this log file and will retry to download the failed tiles.")
    parser.add_argument("-k", "--skip-stitching",
                        action="store_true",
                        dest="skip_stitching",
                        help="Only download the original 256x256 pixel tiles, but do not stitch them onto large tiles.")
    parser.add_argument("-c", "--only-calibrate",
                        action="store_true",
                        dest="only_calibrate",
                        help="When this option is enabled, the script will not download or stitch any tiles. Only OziExplorer calibration files will be generated.")
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
                        "used. Layers per provider:\n" + '\n'.join(["   * " + s + '\n' + "\n".join(['      - ' + l for l in PROVIDERS[s]['layers']]) for s in PROVIDERS]))

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
    if os.path.isdir(options.project_folder):
        # TODO: Read zoom-specific configuration if it exists under the 'project_folder', and if it
        #       doesn't match (for example if the current configuration uses a different tile provider
        #       or layer than the already saved one), then prompt the user and exit.
        pass
    else:
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

            if r.search('\{alts:([^\}]*)\}', server_string):
                for alternative in split_strip(r.groups[0]):
                    options.tile_servers.append(re.sub('\{alts:[^\}]*\}', alternative, server_string))
            else:
                options.tile_servers.append(server_string)

########################################################################
class stitch_osm_tiles(object):
    """
    Class to stitch OSM tiles
    """

    #----------------------------------------------------------------------
    def __init__(self, zoom, tile_servers = None, project_folder = 'maps_project', parallelDownloadThreads = 10, parallelStitchingThreads = multiprocessing.cpu_count()):
        """
        zoom: the zoom level where the class will be working with.
        tile_servers: A list with all of the available tile servers that can be used for tile downloading.
           e.g:
           [
              'http://a.tileserver.com/{z}/{x}/{y}.png',
              'http://b.tileserver.com/{z}/{x}/{y}.png',
              'http://c.tileserver.com/{z}/{x}/{y}.png'
           ]

           Note that {z}/{x}/{y} should be present, since these placeholders will be substituted
           when downloading different tiles.

           If tile_servers == None, no downloading of tiles can be performed, but tiles can still be stitched or calibrated.
        """
        # The zoom level where the current tile worker will be working on.
        self.zoom = zoom
        # A dictionary of the provider with layer specific information as created by the
        # create_provider_dict function.
        self.tile_servers = tile_servers
        # the _tile_height and _tile_height will be calculated when the first tile is downloaded.
        self.max_dimensions = 10000 # 10000 pixels
        # The project name (equals to the project folder)
        self.project_folder = project_folder
        self.parallelDownloadThreads = parallelDownloadThreads
        self.parallelStitchingThreads = parallelStitchingThreads
        self._tile_height = None
        self._tile_width = None
        self._itemsInProcessing = []
        self._inQueue = Queue.Queue()
        self._outQueue = Queue.Queue()
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
    def pixel2deg(self, xpixel, ypixel, original_tile_size = 256):
        """
        Returns the longtitude and latitude of the of the given x/y pixel
        """
        n = 2.0 ** self.zoom
        lon_deg = xpixel / original_tile_size / n * 360.0 - 180
        num_pixel = math.pi - 2.0 * math.pi * ypixel / original_tile_size / n
        lat_deg = 180.0 / math.pi * math.atan2(0.5 * (math.exp(num_pixel) - math.exp(-num_pixel) ), 1)

        return (lat_deg, lon_deg)

    #----------------------------------------------------------------------
    def generate_OZI_map_file(self, filename, extension, width, height, zoom, north, west, east, sourth):
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
        #              At the equator it will always be max the latitude is zero and the cos of 0 is 1.
        #              At the poles the latitude is +-90 degrees, and the "lat/180*pi" becomes +-0.5 and the cos of +-0.5 is 0.
        #              At any other latitude, the circumference will get values in between.
        #
        # Each tile in OSM is 256x256px and each complete map is composed from 2^zoom_level tiles.
        # Consequently, the width/height of the whole globe given in pixels, for each zoom_level is 256*2^zoom_level.
        # Eventually, the size of each pixel at different latitudes is given by this formula:
        #         40075017*cos(lat/180*pi)/(256*2^zoom_level.)
        #            or
        #         40075017*cos(lat/180*pi)/*2^(zoom_level+8)
        #
        # Since each tile covers a range of longtitudes and latitudes, we need to find the latitude in the middle of the tile
        # and calculate the MMB1 value based on this.
        """
        pass

    #----------------------------------------------------------------------
    def _download_tile_worker(self, worker_id, inQueue, outQueue):
        """
        Downloads the content (should be a tile) of the given url.
        Returns a ([graphicsMagickImageObject, imageblob], None) tuple if the file was downloaded succesfully, or a
        tuple with the error object and a stritg with the type of the error.
        """

        while True:
            # The data received from the queue is tuple (url, download_path)
            url, download_path = inQueue.get()

            LOG.debug("Processing by thread {}: DOWNLOADING '{}' -> '{}'".format(worker_id, url, download_path))

            req = urllib2.Request(url)

            try:
                resp = urllib2.urlopen(req, timeout = 5)
            except urllib2.HTTPError as e:
                # e.code contains the actual error code
                retval = (e, url, download_path, 'HTTPError')
            except urllib2.URLError as e:
                retval = (e, url, download_path, 'URLError')
            except:
                e = sys.exc_info()[0]
                retval = (e, url, download_path, 'UnknownDownloadError')
            else:
                tile = resp.read()
                try:
                    ## For direct saving of the downloaded file.
                    #f = open( download_path, 'w' )
                    #f.write(tile)
                    #f.close()

                    ## Load the images with imagemagick
                    #img = imImage(blob=tile)

                    ## Find the extension of the file by reading its format
                    #if img.format.lower() == 'jpeg':
                        #ext = 'jpg'
                    #elif img.format.lower() == 'png':
                        #ext = 'png'
                    #print img.width
                    #print img.height
                    #img.compression_quality = 95
                    #img.totalColors = 10
                    #img.save(filename=y_path)

                    img = gmImage(pgmagick.Blob(tile))
                    img.write(download_path)
                    retval = ([img, tile], url, download_path, None)
                except:
                    e = sys.exc_info()[0]
                    retval = (e, url, download_path, 'UnknownGraphicsMagicError')

            outQueue.put(retval)
            inQueue.task_done()

    #----------------------------------------------------------------------
    def _process_download_results_worker(self, worker_id, inQueue, progress_bar, logfile):
        while True:
            # The data received from the queue is a tuple as return by the 'download_tile_worker' threads
            result, url, download_path, errorType = inQueue.get()

            LOG.debug("Worker {} is processing results for url '{}'".format(worker_id, url))
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

            self._itemsInProcessing.remove(url)

            inQueue.task_done()

    #----------------------------------------------------------------------
    def _addToDownloadInputQueue(self, url, download_path):
        """
        Helper function to add a url in the input queue for threaded processing
        """
        # If we have many pending/unproccessed items, wait until some of the items are processed.
        while len(self._itemsInProcessing) > 2 * self.parallelDownloadThreads:
            time.sleep(0.01)

        # Then add the items in the queue
        self._inQueue.put((url, download_path))
        self._itemsInProcessing.append(url)

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
        # If log level is set to 1000 (logging is disabled), then redirect the progress bar to /dev/null (use os.devnull to support windows as well)
        if LOG.getEffectiveLevel() == 1000:
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
        for i in xrange(self.parallelDownloadThreads):
            thread_worker = threading.Thread(target=self._download_tile_worker, args=(i, self._inQueue, self._outQueue))
            thread_worker.setDaemon(True)
            thread_worker.start()

        # Instantiate a single thread to process the results of the downloads
        downloadLogFile = open( os.path.join(self.project_folder, "zoom-{}-download.log".format(self.zoom)), 'w' )
        thread_worker = threading.Thread(target=self._process_download_results_worker, args=(self.parallelDownloadThreads, self._outQueue, pbar, downloadLogFile))
        thread_worker.setDaemon(True)
        thread_worker.start()

        # The counter is mostly used to choose different tile servers if more than one tile servers are provided for the specified provider.
        counter = 1
        for x in xrange(tile_west, tile_east + 1):
            x_path = os.path.join(self.project_folder, str(self.zoom), str(x))
            if not os.path.isdir(x_path):
                os.mkdir(x_path)

            for y in xrange(tile_north, tile_south + 1):
                url = self.get_tile_url(self.tile_servers[counter % len(self.tile_servers)], str(x), str(y))

                # Always save the original tiles in png format (for better compatibility. For example, OziExplorer's Internet Maps functionality cannot read jpg tiles)
                # TODO: Add a command line option so that the user can choose either to save on the original format, always convert to jpg, or convert to png.
                y_path = '{}.{}'.format(os.path.join(x_path, str(y)), 'png')

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
                            self._addToDownloadInputQueue(url, y_path)
                        else:
                            # Update the progress bar
                            pbar.currval += 1
                            pbar.update(pbar.currval)
                    except:
                        # We execute at this point if the image exists but it cannot be loaded succesfully.
                        # In this case, try to re-download it.
                        self._addToDownloadInputQueue(url, y_path)
                else:
                    # Else the file does not exist, try to download it for the first time.
                    self._addToDownloadInputQueue(url, y_path)


                # If we have just processed the last tile, wait for the threads to finish their work
                # By joing the in/out Queues
                if counter == total_tiles:
                    self._inQueue.join()
                    self._outQueue.join()

                # If we are processing the first tile, wait until the processing completes because we have to
                # read the width/height of this tile before downloading the rest. The rest of the tiles are
                # processed in parallel by multiple threads.
                if counter == 1:
                    while url in self._itemsInProcessing:
                        time.sleep(0.01)

                counter+=1

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
            # TODO: Add a command line option so that the user can choose either to save on the original format, always convert to jpg, or convert to png.
            first_y_tile_path = '{}.{}'.format(os.path.join(x_path, str(tile_north)), 'png')
            img = gmImage(first_y_tile_path)
            self._tile_height = img.rows()
            self._tile_width = img.columns()

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
    def stitch_tiles(self, tile_west, tile_east, tile_north, tile_south):
        """
        Stitch tiles for a given zoom level in the given max dimensions
        """
        print_(self._calculate_max_dimensions_per_stitch(tile_west, tile_east, tile_north, tile_south))

    #----------------------------------------------------------------------
    def calibrate_tiles(self, tile_west, tile_east, tile_north, tile_south):
        """
        Calibrate stitched tiles for a given zoom level in the given max dimensions
        """
        pass

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

    ######################################
    ### Starting adding your code here ###
    ######################################
    #LOG.critical("CRITICAL messages are printed")
    #LOG.error("ERROR messages are printed")
    #LOG.warning("WARNING messages are printed")
    #LOG.info("INFO message are printed")
    #LOG.debug("DEBUG messages are printed")
###
###

    print "---------------------------------"
    #print options

    for zoom in options.zoom_level:
        zoom_folder = os.path.join(options.project_folder, str(zoom))
        if not os.path.isdir(zoom_folder):
            os.mkdir(zoom_folder)

        tileWorker = stitch_osm_tiles(zoom, options.tile_servers, options.project_folder)

        tile_west, tile_north = tileWorker.deg2tilenums(options.lat1, options.long1)
        tile_east, tile_south = tileWorker.deg2tilenums(options.lat2, options.long2)

        number_of_horizontal_tiles = (tile_east - tile_west) + 1
        number_of_vertical_tiles = (tile_south - tile_north) + 1
        total_tiles = number_of_horizontal_tiles * number_of_vertical_tiles

        print """\nProvider: {}
Overlay: {}
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
S_degrees_by_southern_most_tile: {}""".format(
            options.tile_server_provider,
            options.tile_server_provider_layer if options.tile_server_provider_layer else "",
            zoom,
            options.long1,
            options.long2,
            options.lat1,
            options.lat2,
            tile_west,
            tile_east,
            tile_north,
            tile_south,
            (number_of_horizontal_tiles * number_of_vertical_tiles),
            tileWorker.tilenums2deg(tile_west, tile_north)[1],
            tileWorker.tilenums2deg(tile_west, tile_north)[0],
            tileWorker.tilenums2deg(tile_east + 1, tile_south + 1)[1],
            tileWorker.tilenums2deg(tile_east + 1, tile_south + 1)[0]
        )

        tileWorker.download_tiles(tile_west, tile_east, tile_north, tile_south)
        tileWorker.stitch_tiles(tile_west, tile_east, tile_north, tile_south)
