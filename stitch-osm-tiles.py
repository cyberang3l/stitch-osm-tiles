#!/usr/bin/env python
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
from collections import OrderedDict

__all__ = [
    'quick_regexp', 'print_', 'is_number',
    'trim_list', 'split_strip',
    'executeCommand', 'LOG'
]

# TODO: Add -l -r -t -b for left, right, top, bottom tiles to be downloaded (if the used doesn't want to provide the coordinates)

PROGRAM_NAME = 'stitch-osm-tiles'
VERSION = '0.0.1'
AUTHOR = 'Vangelis Tasoulas'

LOG = logging.getLogger('default.' + __name__)

#----------------------------------------------------------------------
# Define the providers and the layer available by each provider in an ordered dict!
PROVIDERS = OrderedDict([
    ('Mapquest', {
        'attribution':'Tiles Courtesy of MapQuest',
        'url':'http://www.mapquest.com',
        'tileservers': [ 'http://otile{alts:1,2,3,4}.mqcdn.com/tiles/1.0.0/{layer}/{z}/{x}/{y}.{ext}' ],
        'extension': 'jpg',
        'zoom_levels': '0-18',
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
                'desc': 'Higher Quality Satellite imagery',
                'zoom_levels': '0-13',
                'tileservers': [
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
        'tileservers': [ 'http://{alts:a,b,c,d}.sm.mapstack.stamen.com/{layer}/{z}/{x}/{y}.{ext}' ],
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
        'tileservers': [ 'http://{alts:a,b,c,d}.tiles.mapbox.com/v4/{layer}/{z}/{x}/{y}.{ext}?access_token=pk.eyJ1Ijoib3BlbnN0cmVldG1hcCIsImEiOiJncjlmd0t3In0.DmZsIeOW-3x-C5eX-wAqTw' ],
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
    def __init__(self):
        self.groups = None
        self.matched = False

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

    parser.add_argument("-p", "--project-name",
                        action="store",
                        default='maps_project',
                        dest="project_name",
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
                        help="Set the western (W) longtitude of a bounding box for tile downloading")
    parser.add_argument("-e", "--long2",
                        action="store",
                        type=float,
                        dest="long2",
                        metavar="E_DEGREES",
                        required=True,
                        help="Set the eastern (E) longtitude of a bounding box for tile downloading")
    parser.add_argument("-n", "--lat1",
                        action="store",
                        type=float,
                        dest="lat1",
                        metavar="N_DEGREES",
                        required=True,
                        help="Set the northern (N) latitude of a bounding box for tile downloading")
    parser.add_argument("-s", "--lat2",
                        action="store",
                        type=float,
                        dest="lat2",
                        metavar="S_DEGREES",
                        required=True,
                        help="Set the southern (S) latitude of a bounding box for tile downloading")
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
    if os.path.isdir(options.project_name):
        # TODO: READ PROJECT CONFIGURATION AND ASK THE USER IF THEY REALLY WANT TO CONTINUE
        pass
    else:
        os.mkdir(options.project_name)

    # Validate and expand the given zoom level(s)
    options.zoom_level = expand_zoom_levels(options.zoom_level)

    # Validate the coordinates (we do not need to check if the coordinates are valid numbers. Argparse is already doing this for us)
    if (options.long1 < -180 or options.long1 > 180) or (options.long2 < -180 or options.long2 > 180):
        error_and_exit("Longtitude value for 'West' or 'East' should be between -180.0 and 180.0")

    if (options.lat1 < -85.05113 or options.lat1 > 85.05113) or (options.lat2 < -85.05113 or options.lat2 > 85.05113):
        error_and_exit("Latitude value for 'North' or 'South' should be between -85.05113 and 85.05113 in the mercator projection.")

    # Check if the custom_osm_server is provided
    # If yes, check if the {z}/{x}/{y} placeholders are present and configure accordingly.
    if options.custom_osm_server:
        r = quick_regexp()
        if(not r.search('\{z\}', options.custom_osm_server) or not r.search('\{x\}', options.custom_osm_server) or not r.search('\{y\}', options.custom_osm_server)):
            if options.custom_osm_server.endswith("/"):
                options.custom_osm_server = options.custom_osm_server + "{z}/{x}/{y}.png"
            else:
                options.custom_osm_server = options.custom_osm_server + "/{z}/{x}/{y}.png"
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
                                   "Chosen zoom levels:\n   {}\n".format(options.tile_server_provider, options.tile_server_provider_layer, accepted_zoom_levels, options.zoom_level))


#----------------------------------------------------------------------
# TODO: Create the necessary functions.

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
    print options
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

    print "---------------------------------"
    print options
    pass
