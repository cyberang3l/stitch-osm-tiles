#!/bin/bash
#
# Script to stitch OpenStreetMap tiles in a single (or multiple) larger
# ones for printouts or use in programs such as OziExplorer.
#
# Copyright (C) 2015 Vangelis Tasoulas <cyberang3l@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Prerequisites:
#   Bash4 is needed, because I use associative arrays in order to parallelize the download of tiles.
#   If you use a recent distro, that shouldn't be a problem.
#
#   apt-get install graphicsmagick imagemagick
#      The 'identify' utility of the imagemagick library is much much faster, but graphicsmagick library's montage and crop operations that are used by this script, are much faster.
#      That's why I use both libraries.
#
#         Each zoom level equivalent scale is:
#             Level   Degree  Area              m / pixel       ~Scale          Accurate-Scale
#             0       360     whole world       156,412         1:500 Mio       559.082.264
#             1       180                       78,206          1:250 Mio       279.541.132
#             2       90                        39,103          1:150 Mio       139.770.566
#             3       45                        19,551          1:70 Mio        69.885.283
#             4       22.5                      9,776           1:35 Mio        34.942.642
#             5       11.25                     4,888           1:15 Mio        17.471.321
#             6       5.625                     2,444           1:10 Mio        8.735.660
#             7       2.813                     1,222           1:4 Mio         4.367.830
#             8       1.406                     610.984         1:2 Mio         2.183.915
#             9       0.703   wide area         305.492         1:1 Mio         1.091.958
#             10      0.352                     152.746         1:500,000       545.979
#             11      0.176   area              76.373          1:250,000       272.989
#             12      0.088                     38.187          1:150,000       136.495
#             13      0.044   village or town   19.093          1:70,000        68.247
#             14      0.022                     9.547           1:35,000        34.124
#             15      0.011                     4.773           1:15,000        17.062
#             16      0.005   small road        2.387           1:8,000         8.531
#             17      0.003                     1.193           1:4,000         4.265
#             18      0.001                     0.596           1:2,000         2.133
#             19      0.0005                    0.298           1:1,000         1.066

# TODO: Convert to python
#       Add a command line parameter for tuning the parallel (multithreaded) wget downloads.
#       Update the readme at the top of this file and the README.md file.
#       Make subroutines for the stitching functionality (In general make more subroutines when you will convert it to python)
#       Add proper "project" functionality. Add an option to load settings from a project file.
#       Do not call multiple times the identify command. Call it once, store the output in a variable and then parse the variables.
#       When making the sanity checks about the type of the file, use the info that you've gotten from the identify command. Not the extension since the extension might be wrong.
#       Add a command line parameter to allow the user to choose the max size of the stitched tiles. Now it is hardcoded in the variable $max_resolution_px
#       Allow the user to choose different max_resolution_px for y an x. Now max-allowed-y = max-allowed-x = $max_resolution_px
#       Currently, when a custom osm server is used, it must be using this format "http://my.osm.server/{z}/{x}/{y}.{ext}". If the user does not provide the '{z}/{x}/{y}.{ext}' part, then you should append it at the end of the custom server URL.

trap "exit" INT

# Variables to store the custom server info
osm_custom_server=${OSM_CUSTOM_SERVER:-}
osm_custom_extension=${OSM_CUSTOM_EXTENSION:-"png"}

# If you want to add new providers, add the provider name in the "available_providers" array
# and add the 2 more arrays and 1 more variable for each new provider:
#      provider_available_overlays
#      provider_extension
#      provider_tile_servers
# Look at how the already existing providers are defined below.
# Note that the "provider_tile_servers" array is using a codeword
# "_OVERLAY_". The "_OVERLAY_" will be replaced with the overlay
# chosen by the user at each execution of the script.
#
# The first values of each array are considered to be the defaults
# available_providers=( "mapquest" "thunderforest" )
available_providers=( "mapquest" "mapquest2" "stamen" "mapbox" )

# MapQuest tile servers
# http://www.mapquest.com/
#
# Available MAPQUEST Overlays:
#   osm|map: OpenStreetMap (available zoom levels 0-18)
#   sat: Satellite (available zoom levels 0-11)
mapquest_available_overlays=( "map" "osm" "sat" )
mapquest_extension="jpg"
mapquest_tile_servers=( 
 "http://otile1.mqcdn.com/tiles/1.0.0/_OVERLAY_/{z}/{x}/{y}.{ext}"
 "http://otile2.mqcdn.com/tiles/1.0.0/_OVERLAY_/{z}/{x}/{y}.{ext}"
 "http://otile3.mqcdn.com/tiles/1.0.0/_OVERLAY_/{z}/{x}/{y}.{ext}"
 "http://otile4.mqcdn.com/tiles/1.0.0/_OVERLAY_/{z}/{x}/{y}.{ext}"
)

# MapQuest2
#   sat: Satellite (available zoom levels 0-13)
mapquest2_available_overlays=( "map" "sat" "hyb" )
mapquest2_extension="jpg"
mapquest2_tile_servers=( 
 "http://ttiles01.mqcdn.com/tiles/1.0.0/vy/_OVERLAY_/{z}/{x}/{y}.{ext}"
 "http://ttiles02.mqcdn.com/tiles/1.0.0/vy/_OVERLAY_/{z}/{x}/{y}.{ext}"
 "http://ttiles03.mqcdn.com/tiles/1.0.0/vy/_OVERLAY_/{z}/{x}/{y}.{ext}"
 "http://ttiles04.mqcdn.com/tiles/1.0.0/vy/_OVERLAY_/{z}/{x}/{y}.{ext}"
)
# Stamen
# http://maps.stamen.com
stamen_available_overlays=( "toner" "toner-hybrid" "toner-labels" "toner-lines" "toner-background" "toner-lite" "watercolor" )
stamen_extension="png"
stamen_tile_servers=( 
 "http://a.sm.mapstack.stamen.com/_OVERLAY_/{z}/{x}/{y}.{ext}"
 "http://b.sm.mapstack.stamen.com/_OVERLAY_/{z}/{x}/{y}.{ext}"
 "http://c.sm.mapstack.stamen.com/_OVERLAY_/{z}/{x}/{y}.{ext}"
 "http://d.sm.mapstack.stamen.com/_OVERLAY_/{z}/{x}/{y}.{ext}"
)
# Mapbox Satellite
# http://www.mapbox.com/about/maps/
mapbox_available_overlays=( "openstreetmap.map-inh7ifmo" )
mapbox_extension="jpg"
mapbox_tile_servers=( 
 "http://a.tiles.mapbox.com/v4/_OVERLAY_/{z}/{x}/{y}.{ext}?access_token=pk.eyJ1Ijoib3BlbnN0cmVldG1hcCIsImEiOiJncjlmd0t3In0.DmZsIeOW-3x-C5eX-wAqTw"
 "http://b.tiles.mapbox.com/v4/_OVERLAY_/{z}/{x}/{y}.{ext}?access_token=pk.eyJ1Ijoib3BlbnN0cmVldG1hcCIsImEiOiJncjlmd0t3In0.DmZsIeOW-3x-C5eX-wAqTw"
 "http://c.tiles.mapbox.com/v4/_OVERLAY_/{z}/{x}/{y}.{ext}?access_token=pk.eyJ1Ijoib3BlbnN0cmVldG1hcCIsImEiOiJncjlmd0t3In0.DmZsIeOW-3x-C5eX-wAqTw"
 "http://d.tiles.mapbox.com/v4/_OVERLAY_/{z}/{x}/{y}.{ext}?access_token=pk.eyJ1Ijoib3BlbnN0cmVldG1hcCIsImEiOiJncjlmd0t3In0.DmZsIeOW-3x-C5eX-wAqTw"
)
# # Thunderforest tile servers
# # http://thunderforest.com/
# #
# # Available Thunderforest overlays: opencyclemap, outdoors, landscape, transport, transport-dark
# # http://thunderforest.com/outdoors/
# # http://thunderforest.com/landscape/
# thunderforest_available_overlays=( "outdoors" "opencyclemap" "landscape" "transport" "transport-dark" )
# thunderforest_extension="png"
# thunderforest_tile_servers=(
#  "http://a.tile.thunderforest.com/_OVERLAY_"
#  "http://b.tile.thunderforest.com/_OVERLAY_"
#  "http://c.tile.thunderforest.com/_OVERLAY_"
# )

function usage {
   echo ""
   echo "Usage: $(basename $0) -z ZOOM [OPTION]..."
   echo "Script to stitch OpenStreetMap tiles in a single (or multiple) larger"
   echo "ones for printouts or use in programs such as OziExplorer."
   echo ""
   echo "If only the zoom level is given as a parameter, the script will look for the specified"
   echo "zoom folder and try to stitch any OSM tiles. If more options are utilized, the script"
   echo "can be used to download tiles defined by a bounding box and then stitch them if -p"
   echo "option is not used."
   echo ""
   echo " -p|--project-name                    Choose a project name. The downloaded data and stitching"
   echo "                                        operations will all be made under this folder."
   echo "                                        Default value: 'maps_project'"
   echo " -z|--zoom-level ZOOM                 Valid ZOOM values: 0-18. This option is mandatory."
   echo " -w|--lon1 W_DEGREES                  Set the western (W) longtitude of a bounding box for"
   echo "                                        tile downloading. -e, -n and -s should also be set."
   echo "                                        This option is mandatory."
   echo " -e|--lon2 E_DEGREES                  Set the eastern (E) longtitude of a bounding box for"
   echo "                                        tile downloading. -w, -n and -s should also be set."
   echo "                                        This option is mandatory."
   echo " -n|--lat1 N_DEGREES                  Set the northern (N) latitude of a bounding box for"
   echo "                                        tile downloading. -w, -e and -s should also be set."
   echo "                                        This option is mandatory."
   echo " -s|--lat2 S_DEGREES                  Set the southern (S) latitude of a bounding box for"
   echo "                                        tile downloading. -w, -e, and -n should also be set."
   echo "                                        This option is mandatory."
   echo " -o|--custom-osm-server OSM_SERVER    The URL of your tile server. If this option is"
   echo "                                        not set, mapquest tile servers will be used."
   echo "                                        This option can also be set as an OSM_CUSTOM_SERVER"
   echo "                                        environment variable."
   echo " -x|--custom-osm-extension EXT        Choose the extension of the tiles served by the custom"
   echo "                                        server. The provided extension should not be prefixed"
   echo "                                        with a dot '.'. For example, if the server is serving"
   echo "                                        jpg tiles, then the option should be called like:"
   echo "                                           '-x jpg'"
   echo "                                        This option can also be set as an OSM_CUSTOM_EXTENSION"
   echo "                                        environment variable, and it has no effect if it is"
   echo "                                        not used together with the -o option."
   echo " -r|--retry-failed                    Retry to download tiles that failed to be downloaded at"
   echo "                                        the first try. If this option is not used, the files"
   echo "                                        that they were not able to be download, will be logged"
   echo "                                        in a log file."
   echo " -k|--skip-stitching                  This option can be used together with the -w, -e, -n"
   echo "                                        and -s options, in order to just download tiles, but"
   echo "                                        not stitch them together. The stitching and"
   echo "                                        calibration can always can be done later."
   echo " -d|--skip-tile-downloading           This option will make the script to skip tile downloading."
   echo "                                        Nevertheless, the script will still try to stitch and"
   echo "                                        calibrate the downloaded tiles located in the"
   echo "                                        corresponding 'zoom' directory."
   echo " -c|--only-calibrate                  With this option, the script will not download nor stitch"
   echo "                                        any tiles. It will only produce OziExplorer map"
   echo "                                        calibration files. Use this option together with -w,"
   echo "                                        -e, -n and -s options, to make the script aware of the"
   echo "                                        tiles that you want to calibrate."
   echo " -t|--tile-server-provider PROVIDER   Choose one of the predefined tile server providers."
   echo "                                         Available tile server providers:"
   for (( i=0; i<${#available_providers[@]}; i++ )); do
	echo "                                             * ${available_providers[$i]}"
   done
   echo " -l|--tile-server-provider-overlay OVERLAY"
   echo "                                      Choose one of the overlays for the predefined tile"
   echo "                                        providers. This option has no effect if it is"
   echo "                                        not used together in combination with -t option."
   echo "                                         Available overlays per provider:"
   for (( i=0; i<${#available_providers[@]}; i++ )); do
	echo "                                             * ${available_providers[$i]}"
	local available_overlays="${available_providers[$i]}"_available_overlays[@]
	available_overlays=( "${!available_overlays}" )
	
	for (( j=0; j<${#available_overlays[@]}; j++ )); do
	   echo "                                                - ${available_overlays[$j]}"
	done
   done
   echo " -h|--help                            Prints this help message."
   echo ""
   exit 0
}

E_BADARGS=65

# The horizontal or vertical resolution of the final tiles should not exceed that of the $max_resolution_px variable
max_resolution_px=10000
coordinates_given=0
lon1=
lon2=
lat1=
lat2=
zoom_level=
skip_stitching=0
skip_tile_downloading=0
only_calibrate=0
project_folder="maps_project"
provider=
overlay=
retry_failed=0

args=$(getopt --options z:w:e:n:s:ho:kt:l:x:cdp:r --longoptions zoom-level:,lon1:,lon2:,lat1:,lat2:,help,custom-osm-server:,skip-stitching,tile-server-provider:,tile-server-provider-overlay:,custom-osm-extension:,only-calibrate,skip-tile-downloading,project-name:,retry-failed -- "$@")

eval set -- "$args"

for i
do
   case "$i" in
      -z|--zoom-level) shift
         zoom_level="$1"
         shift
         ;;  
      -w|--lon1) shift
         lon1="$1"
         coordinates_given=1
         shift
         #echo "Longitude west was set to $lon1"
         ;;  
      -e|--lon2) shift
         lon2="$1"
         coordinates_given=1
         shift
         #echo "Longitude east was set to $lon2"
         ;;  
      -n|--lat1) shift
         lat1="$1"
         coordinates_given=1
         shift
         #echo "Latitude north was set to $lat1"
         ;;  
      -s|--lat2) shift
         lat2="$1"
         coordinates_given=1
         shift
         #echo "Latitude south was set to $lat2"
         ;;
      -o|--custom-osm-server) shift
         osm_custom_server="$1"
         shift
         ;;
      -x|--custom-osm-extension) shift
         osm_custom_extension="$1"
         shift
         ;;
      -t|--tile-server-provider) shift
         provider="$1"
         shift
         ;;
      -l|--tile-server-provider-overlay) shift
         overlay="$1"
         shift
         ;;
      -p|--project_name) shift
         project_folder=$1
         shift
         ;;
	-r|--retry-failed) shift
         retry_failed=1
         ;;
      -k|--skip-stitching) shift
         skip_stitching=1
         ;;
      -d|--skip-tile-downloading) shift
         skip_tile_downloading=1
         ;;
      -c|--only-calibrate) shift
         only_calibrate=1
         ;;
      -h|--help) shift
         usage
         ;;
   esac
done

provider_tile_servers=
process_provider()
{
   provider=$1
   overlay=$2
   
   local available_overlays="$provider"_available_overlays[@]
   local tile_servers="$provider"_tile_servers[@]
   
   available_overlays=( "${!available_overlays}" )
   tile_servers=( "${!tile_servers}" )
   
   valid_overlay_chosen=0
   if [[ ! -z "$overlay" ]]; then
	for over in "${available_overlays[@]}"; do
	   if [[ "$overlay" == "$over" ]]; then
		valid_overlay_chosen=1
		break
	   fi
	done
   else
	# If an overlay was not chosen by the user, use as default
	# the first one in the "available_overlays" array 
	overlay=${available_overlays[0]}
	valid_overlay_chosen=1
   fi
   
   if [[ $valid_overlay_chosen -eq 0 ]]; then
	echo "ERROR: The chosen overlay '$overlay' for provider '$provider' is not valid."
	echo "   A list of valid overlays for the '$provider' provider:"
	for (( i=0; i<${#available_overlays[@]}; i++ )); do
	   echo "      $(( i+1 )): ${available_overlays[$i]}"
	done
	exit 1
   else
	for (( i=0; i<${#tile_servers[@]}; i++ )); do
	   tile_servers[$i]=$(echo "${tile_servers[$i]}" | sed 's/_OVERLAY_/'"$overlay"'/')
	done
	provider_tile_servers=( "${tile_servers[@]}" )
   fi
}

get_url()
{
   tile_url="$1"
   z="$2"
   x="$3"
   y="$4"
   ext="$5"
   
   echo $(echo $tile_url | sed -e 's/{z}/'$z'/g' -e 's/{x}/'$x'/g' -e 's/{y}/'$y'/g' -e 's/{ext}/'$ext'/g')
}

######################################################################################
# Define functions to get tiles from longitude/latitude and vice versa
# http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Coordinates_to_tile_numbers_2
#
#   X and Y
#      X goes from 0 (left edge is 180 °W) to 2^zoom − 1 (right edge is 180 °E)
#      Y goes from 0 (top edge is 85.0511 °N) to 2^zoom − 1 (bottom edge is 85.0511 °S) in a "Mercator projection" <- THIS IS VERY IMPORTANT
#                                                                                                      LATER WHEN I PERFORM THE CALIBRATION.
#   For the curious, the number 85.0511 is the result of arctan(sinh(π)). By using this bound, the entire map becomes a (very large) square.
#
#   https://help.openstreetmap.org/questions/37743/tile-coordinates-from-latlonzoom-formula-problem
#
xtile2long()
{
   xtile=$1
   zoom=$2
   echo "${xtile} ${zoom}" | awk '{printf("%.9f", $1 / 2.0^$2 * 360.0 - 180)}'
} 
 
long2xtile()  
{ 
   long=$1
   zoom=$2
   echo "${long} ${zoom}" | awk '{ xtile = ($1 + 180.0) / 360 * 2.0^$2; 
      xtile+=xtile<0?-0.5:0.5;
      printf("%d", xtile ) }'
}
 
ytile2lat()
{
   ytile=$1
   zoom=$2
   tms=$3
   if [ ! -z "${tms}" ]
   then
   #  from tms_numbering into osm_numbering
   ytile=$(echo "${ytile}" ${zoom} | awk '{printf("%d\n",((2.0^$2)-1)-$1)}')
   fi
   lat=$(echo "${ytile} ${zoom}" | awk -v PI=3.14159265358979323846 '{ 
            num_tiles = PI - 2.0 * PI * $1 / 2.0^$2;
            printf("%.9f", 180.0 / PI * atan2(0.5 * (exp(num_tiles) - exp(-num_tiles)),1)); }')
   echo "${lat}"
}
 
lat2ytile() 
{ 
   lat=$1
   zoom=$2
   tms=$3
   ytile=$(echo "${lat} ${zoom}" | awk -v PI=3.14159265358979323846 '{ 
      tan_x=sin($1 * PI / 180.0)/cos($1 * PI / 180.0);
      ytile = (1 - log(tan_x + 1/cos($1 * PI/ 180))/PI)/2 * 2.0^$2; 
      ytile+=ytile<0?-0.5:0.5;
      printf("%d", ytile ) }')
   if [ ! -z "${tms}" ]; then
      #  from oms_numbering into tms_numbering
      ytile=`echo "${ytile}" ${zoom} | awk '{printf("%d\n",((2.0^$2)-1)-$1)}'`
   fi
   echo "${ytile}"
}

########################################################################################
# Get the longtitude and latitude per pixel, based on the global pixel scale of the map.
# For example, if the zoom level is 0, then only one 256x256 tile compose the complete
# map. In this case, a y pixel value of 0 will give a latitude of ~-85deg and a y pixel
# value of 256 will give a latitude of +85.
# If the zoom is 3, then the whole map is 8x8 tiles, so 2048x2048 pixels. In this case
# a y pixel value of 0 will give a latitude of ~-85deg and a y pixel value of 20248 will
# give a latitude of +85.
xpixel2long()
{
   xpixel=$1
   zoom=$2
   awk -v px=$xpixel -v z=$zoom '
      BEGIN {
         printf "%.15f", px / 256 / 2.0^z * 360.0 - 180
      }'
}

ypixel2lat()
{
   ypixel=$1
   zoom=$2
   awk -v PI=3.14159265358979323846 -v px=$ypixel -v z=$zoom '
      BEGIN {
         num_pixel = PI - 2.0 * PI * px / 256 / 2.0^z
         printf "%.15f", 180.0 / PI * atan2(0.5 * (exp(num_pixel) - exp(-num_pixel) ), 1)
      }'
}
######################################################################################

check_if_valid_number() {
   integer_comparizon="$2"
   if [[ ! -z "$integer_comparizon" ]]; then
      re='^-?[0-9]+$'
      message="is not a valid integer number."
   else
      re='^-?[0-9]+([.][0-9]+)?$'
      message="is not a valid number."
   fi
   
   if ! [[ $1 =~ $re ]]; then >&2 echo "$1 ""$message"; return $E_BADARGS; fi
}

compare_nums()
{
   # Function to compare two numbers (float or integers) by using awk.
   # The function will nor print anything, but it will return 0 (if the comparison is true) or 1
   # (if the comparison is false) exit codes, so it can be used directly in shell one liners.
   #############
   ### Usage ###
   ### Note that you have to enclose the comparison operator in quotes.
   #############
   # compare_nums 1 ">" 2 # returns false
   # compare_nums 1.23 "<=" 2 # returns true
   # compare_nums -1.238 "<=" -2 # returns false
   #############################################
   num1=$1
   op=$2
   num2=$3
   E_BADARGS=65
   
   # Make sure that the provided numbers are actually numbers.
   check_if_valid_number $num1 || return $E_BADARGS
   check_if_valid_number $num2 || return $E_BADARGS
   
   # If you want to print the exit code as well (instead of only returning it), uncomment
   # the awk line below and comment the uncommented one which is two lines below.
   #awk 'BEGIN {print return_code=('$num1' '$op' '$num2') ? 0 : 1; exit} END {exit return_code}'
   awk 'BEGIN {return_code=('$num1' '$op' '$num2') ? 0 : 1; exit} END {exit return_code}'
   return_code=$?
   return $return_code
}

convert_to_degrees()
{
   decimal_coord="$1"
   orientation="$2"
   
   awk -v d="$decimal_coord" -v o="$orientation" '
   function abs(x){
	return ((x < 0.0) ? -x : x)
   }
   
   function orientation(x, orient){
	if (o == "N" || o == "S")
	   return ((x < 0.0) ? "S" : "N")
	else if (o == "W" || o == "E")
	   return ((x < 0.0) ? "W" : "E")
   }
   
   BEGIN {
	abs_d=abs(d)
	
	printf "%3d %12.9f %s", abs_d, (abs_d-int(abs_d))*60, orientation(d, o)
   }'
}

generate_OZI_map_file()
{
   filename="$1"
   extension="$2"
   width="$3"
   height="$4"
   zoom="$5"

   North="$6"
   West="$7"
   East="$8"
   South="$9"

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
   lat_mid_of_tile=$(awk -v s=$South -v n=$North 'BEGIN {printf "%.9f", s + (n - s)/2}')
   MMB1=$(awk -v pi=3.14159265358979323846 'BEGIN {printf "%.9f\n", 40075017*cos('$lat_mid_of_tile'/180*pi)/2^('$zoom'+8)}')

   N=( $(convert_to_degrees "$North" "N") )
   W=( $(convert_to_degrees "$West" "W") )
   E=( $(convert_to_degrees "$East" "E") )
   S=( $(convert_to_degrees "$South" "S") )

   w="$(printf %5s $(( $width - 1 )))"
   h="$(printf %5s $(( $height - 1 )))"
   # z (zero) is only added here for the sake of having well aligned code :)
   z="$(printf %5s 0)"

   echo "OziExplorer Map Data File Version 2.2
$filename
$filename.$extension
1,Map Code,
WGS 84,WGS 84,   0.0000,   0.0000,WGS 84
Reserved 1
Reserved 2
Magnetic Variation,,,E
Map Projection,Mercator,PolyCal,No,AutoCalOnly,No,BSBUseWPX,No
Point01,xy, $z, $z, in, deg, ${N[0]}, ${N[1]}, ${N[2]}, ${W[0]}, ${W[1]}, ${W[2]}, grid,   , , ,N
Point02,xy, $w, $h, in, deg, ${S[0]}, ${S[1]}, ${S[2]}, ${E[0]}, ${E[1]}, ${E[2]}, grid,   , , ,N
Point03,xy, $w, $z, in, deg, ${N[0]}, ${N[1]}, ${N[2]}, ${E[0]}, ${E[1]}, ${E[2]}, grid,   , , ,N
Point04,xy, $z, $h, in, deg, ${S[0]}, ${S[1]}, ${S[2]}, ${W[0]}, ${W[1]}, ${W[2]}, grid,   , , ,N
Projection Setup,,,,,,,,,,
Map Feature = MF ; Map Comment = MC     These follow if they exist
Track File = TF      These follow if they exist
Moving Map Parameters = MM?    These follow if they exist
MM0,Yes
MMPNUM,4
MMPXY,1,0,0
MMPXY,2,$width,0
MMPXY,3,$width,$height
MMPXY,4,0,$height
MMPLL,1, $West, $North
MMPLL,2, $East, $North
MMPLL,3, $East, $South
MMPLL,4, $West, $South
MM1B,$MMB1
MOP,Map Open Position,0,0
IWH,Map Image Width/Height,$width,$height"
}

########################################
# Process the user provided arguments. #
########################################

###################################################################
# 1. check if the zoom level has been provided. This is mandatory.#
###################################################################
if [[ -z $zoom_level ]]; then
   echo "Please provide the OpenStreetMap zoom level with the '-z' option."
   exit $E_BADARGS
else
   # Check if the zoom level is a valid integer between 1-18
   check_if_valid_number "$zoom_level" "int" || exit
   if [[ $zoom_level -lt 1 || $zoom_level -gt 18 ]]; then
      echo "Zoom level values should be between 1-18"
      exit $E_BADARGS
   fi
fi

############################################################################
# 2. Check if the coordinates havebeen provided. This is mandatory.        #
# If at least one coordinate has been given, then process the coordinates. #
############################################################################
if [[ $coordinates_given -ne 1 ]]; then
   echo "Please provide the coordinates that you want to process. (-w, -e, -n and -s options)"
   exit $E_BADARGS
else
   # If one coordinate has been given, then all of the coordinates should have been given.
   if [[ -z $lon1 || -z $lon2 || -z $lat1 || -z $lat2 ]]; then
	echo "If you provide coordinates for tile downloading, you need to provide all 4 coordinates:"
	echo "   West (longitude 1)"
	echo "   East (longitude 2)"
	echo "   North (latitude 1)"
	echo "   South (latitude 2)"
	exit $E_BADARGS
   fi
   
   # Check if the coordinate numbers are valid float numbers
   check_if_valid_number $lon1 || exit
   check_if_valid_number $lon2 || exit
   check_if_valid_number $lat1 || exit
   check_if_valid_number $lat2 || exit
   
   # Check if the user has given coordinates within the limits. No wrap-arounds are allows
   #   e.g. -200° is actually 160°, but we do not support such cases
   longtitude_val_error="Map wrap-arounds are not allowed. Use longtitude values between -180.0°(W) and 180.0°(E)."
   latitude_val_error="Map wrap-arounds are not allowed. Use latitude values between 85.0511°(N) and -85.0511°(S)."
   compare_nums $lon1 "<"     -180 && echo "$longtitude_val_error" && exit $E_BADARGS
   compare_nums $lon2 ">"      180 && echo "$longtitude_val_error" && exit $E_BADARGS
   compare_nums $lat1 ">"  85.0511 && echo "$latitude_val_error" && exit $E_BADARGS
   compare_nums $lat2 "<" -85.0511 && echo "$latitude_val_error" && exit $E_BADARGS
   
   # Convert the coordinates to OSM tiles.
   tile_west=$(long2xtile $lon1 $zoom_level)
   tile_east=$(long2xtile $lon2 $zoom_level)
   tile_north=$(lat2ytile  $lat1 $zoom_level)
   tile_south=$(lat2ytile  $lat2 $zoom_level)

   # echo $tile_west $tile_east
   # echo $tile_north $tile_south
   
   # The west tile should always be smaller than the east tile.
   if [[ $tile_west -gt $tile_east ]]; then
      echo ""
      echo "WARNING: Longtitude 1 value should be smaller than that of longitude 2, because wrap arrounds are not supported. Swapping values and continuing."
      echo ""
      temp=$tile_west
      tile_west=$tile_east
      tile_east=$temp
   fi
   
   # The north tile should always be smaller than the south tile.
   if [[ $tile_north -gt $tile_south ]]; then
      echo ""
      echo "WARNING: Latitude 1 value should be smaller than that of latitude 2, because wrap arrounds are not supported. Swapping values and continuing."
      echo ""
      temp=$tile_south
      tile_south=$tile_north
      tile_north=$temp
   fi
   
   # If the calculated tiles wrap around go out of the limits, just use the tiles on the limits
   compare_nums $tile_north "<" 0 && tile_north=0
   compare_nums $tile_south ">" $(( 2**$zoom_level-1 )) && tile_south=$(( 2**$zoom_level-1 ))
   compare_nums $tile_west "<" 0 && tile_west=0
   compare_nums $tile_east ">" $(( 2**$zoom_level-1 )) && tile_east=$(( 2**$zoom_level-1 ))
   
   # echo $tile_west $tile_east
   # echo $tile_north $tile_south
   
   # echo $(xtile2long $tile_west $zoom_level) $(xtile2long $tile_east $zoom_level)
   # echo $(ytile2lat $tile_north $zoom_level) $(ytile2lat $tile_south $zoom_level)
fi

# When we download files, we download from $tile_west to $tile_east inclusive.
# That's why the horizontal and vertical tiles are the '($tile_east - $tile_west) + 1'.
# The same goes for North and South
number_of_horizontal_tiles=$(( ($tile_east - $tile_west) + 1 ))
number_of_vertical_tiles=$(( ( $tile_south - $tile_north ) + 1 ))


#############################################
# Start the tile downloading procedure here #
#############################################
if [[ $skip_tile_downloading -eq 1 || $only_calibrate -eq 1 ]]; then
   echo "Skipping tile downloading as requested..."
else
   # If a tile provider has not been chosen....
   if [[ -z "$provider" ]]; then
	# And if the user has not provided any custom tile server....
	if [[ -z "${osm_custom_server}" ]]; then
	   # Then use the default provider with the default overlay
	   echo "Using the default provider '${available_providers[0]}' to download tiles"
	   process_provider "${available_providers[0]}"
	   provider="${available_providers[0]}"
	else
	   # Else, use the custom tile server.
	   provider_tile_servers=( "${osm_custom_server}" )
	   # And set the provider to osm custom, in order to use the correct extension later on.
	   provider="osm_custom"
	fi
   else
   # If a tile provider has been chosen, make sure that the provider is already known,
   # and choose a proper overlay
	provider_is_valid=0
	for prov in ${available_providers[@]}; do
	   if [[ "$provider" == "$prov" ]]; then
		provider_is_valid=1
		break
	   fi
	done
	if [[ $provider_is_valid -ne 1 ]]; then
	   # If the provided provider is not known, then use the default provider.
	   echo "WARNING: Provider $provider was not found in the list of the valid providers."
	   echo "         Falling back to the default provider: ${available_providers[0]}"
	   process_provider "${available_providers[0]}"
	   provider="${available_providers[0]}"
	else
	   # At this point, we know that the given provider is valid.
	   # Now check if the user has asked for a specific overlay, and use this if possible.
	   # If the user hasn't chosen any overlay, use the default for this provider.
	   if [[ ! -z "$overlay" ]]; then
		process_provider "$provider" "$overlay"
	   else
		process_provider "$provider"
	   fi
	fi
   fi
   
   if [[ "$provider" == "mapquest2" && "$overlay" == "hyb" ]]; then
	ext="png"
   else
	temp_var="$provider"_extension
	ext=${!temp_var}
   fi
   # echo "${provider_tile_servers[@]}"
   # echo "$ext"
   
   # Store project information in project_folder at this point
   mkdir -p $project_folder
   project_settings_file="$project_folder/zoom-$zoom_level-settings.osmtiles"
   if [[ -f "$project_settings_file" ]]; then
	echo "Zoom level $zoom_level tiles already exist for this project."
	echo "Checking if data are as expected..."
	# TODO: Check if the proper tiles are downloaded.
	# If not, then you can safely keep on downloading.
	# If more tiles than those needed for the given coordinates exist, raise an error and exit.
   else
	if [[ "$provider" == "osm_custom" ]]; then
	   provider_string="${provider_tile_servers[0]}"
	else
	   provider_string="$provider"
	fi
	echo "Provider: $provider_string
Overlay: $overlay
Zoom: $zoom_level
command_line_longtitude1 (W): $lon1
command_line_longtitude2 (E): $lon2
command_line_latitude1 (N): $lat1
command_line_latitude2 (S): $lat2
tile_west: $tile_west
tile_north: $tile_north
tile_east: $tile_east
tile_south: $tile_south
W_degrees_by_western_most_tile: $(xtile2long $tile_west $zoom_level)
N_degrees_by_northern_most_tile: $(ytile2lat $tile_north $zoom_level)" > "$project_settings_file"
   fi

   # Eventually download the tiles.
   total_tiles_to_download=$(( $number_of_horizontal_tiles * $number_of_vertical_tiles ))
   downloading_now=0
   successfully_downloaded=0
   parallel_downloads=30
   logfile="$project_folder/$zoom_level.log"
   echo "Started downloading on "$(date) > "$logfile"
   echo "Downloading $total_tiles_to_download tiles."
   declare -A pid_array=()
   for (( lon=$tile_west; lon<=$tile_east; lon++)); do
	download_folder="$project_folder/original_files/"
      mkdir -p "$download_folder/$zoom_level/$lon"
      for (( lat=$tile_north; lat<=$tile_south; lat++)); do
         (( ++downloading_now ))
         # If more than one tile server is provided, use all of the tile servers in a round robin fashion.
         tile_server=${provider_tile_servers[$(( $downloading_now % ${#provider_tile_servers[@]} ))]}
         
         # Check how many concurrent threads are running.
         # If we have reached the "$parallel_downloads" limit, then we have to wait for a thread to complete before starting another one.
         if [[ ${#pid_array[@]} -ge $parallel_downloads ]]; then
            removed=0
            while [[ $removed -eq 0 ]]; do
               # Run in this while loop until at least on thread completes its work.
               for i in ${!pid_array[@]}; do
                  # If the process finished downloading, ps will return an exit code other than zero.
                  ps $i > /dev/null
                  exit_status=$?
                  if [[ $exit_status -ne 0 ]]; then
                     # Then call wait in order to get the exit status of the finished background process.
                     wait $i
                     exit_status=$?
                     if [[ $exit_status -eq 0 ]]; then
                        # If the exit status of the background process is zero, increase the "successfully_downloaded" counter
                        failed_tile_name=
                        (( successfully_downloaded++ ))
                     else
                        # If the exit status of the finished background process is not 0 (meaning that the process
                        # did not finish successfylly), then add a log warning so that the user knows which tiles
                        # faced download problems.
                        if [[ $retry_failed -eq 1 ]]; then
                           echo "ERROR: File '${pid_array[$i]}' was not downloaded properly from server $tile_server. Retrying..." >> "$logfile"
                           failed_tile_name="${pid_array[$i]}"
                        else
                           echo "ERROR: File '${pid_array[$i]}' was not downloaded properly from server $tile_server." >> "$logfile"
                        fi
                     fi
                     # remove the pid from the array
                     unset "pid_array[$i]"
                     
                     # If the tile was not downloaded successfully, the variable $failed_tile_name will
                     # not be empty. If the user has asked to retry to download failed tiles, then run
                     # "wget" for the specified tile again.
                     if [[ ! -z "$failed_tile_name" && $retry_failed -eq 1 ]]; then
                     	failed_tile_name_url="$(echo $failed_tile_name | rev | cut -d'/' -f 1-3 | rev)"
                     	z=$(echo "$failed_tile_name_url" | awk -F'[/.]' '{print $2}')
                     	x=$(echo "$failed_tile_name_url" | awk -F'[/.]' '{print $3}')
                     	y=$(echo "$failed_tile_name_url" | awk -F'[/.]' '{print $4}')
                     	counter=0
                     	max_counter=3
                     	while [[ $counter -lt $max_counter ]]; do
				   wget "$(get_url $tile_server $z $x $y $ext)" -O "$download_folder/$z/$x/$y.$ext" -o /dev/null
                     	   exit_status=$?
                     	   if [[ $exit_status -ne 0 ]]; then
                     		(( counter++ ))
                     		echo "ERROR: File '$failed_tile_name_url' was not downloaded properly from server $tile_server after $counter retries." >> "$logfile"
                     		if [[ $counter -eq $max_counter ]]; then echo "ERROR: Giving up on file '$failed_tile_name_url'"  >> "$logfile"; fi
                     	   else
                     		echo "GOOD: File '$failed_tile_name_url' was eventually downloaded." >> "$logfile"
                     		counter=$max_counter
                     	   fi
                     	done
                     fi
                     (( removed++ ))
                  fi
               done
            done
         fi
         
         # If the file does not exist or is corrupted, then download the file.
         if [[ ! -f "$download_folder/$zoom_level/$lon/$lat.$ext" || $(identify -format "%h" "$download_folder/$zoom_level/$lon/$lat.$ext") -ne 256 && $(identify -format "%w" "$download_folder/$zoom_level/$lon/$lat.$ext") -ne 256 ]]; then
            echo "Downloading tile $downloading_now/$total_tiles_to_download.."
            # Start a new download thread using wget and put it in the background.
            #echo "wget "$(get_url $tile_server $zoom_level $lon $lat $ext)" -O "$download_folder/$zoom_level/$lon/$lat.$ext" -o /dev/null"
            wget "$(get_url $tile_server $zoom_level $lon $lat $ext)" -O "$download_folder/$zoom_level/$lon/$lat.$ext" -o /dev/null &
            # Store the PID of the last wget command added in the background.
            pid_array[$!]="$download_folder/$zoom_level/$lon/$lat.$ext"
         else
            echo "File '$download_folder/$zoom_level/$lon/$lat.$ext' ($downloading_now/$total_tiles_to_download) already downloaded."
            (( successfully_downloaded++ ))
         fi
         
         # If the last tile is downloading, then wait for all the background processes to complete.
         if [[ $lon -eq $tile_east && $lat -eq $tile_south ]]; then
		while [[ ${#pid_array[@]} -gt 0 ]]; do
		   for i in ${!pid_array[@]}; do
			ps $i > /dev/null
			exit_status=$?
			if [[ $exit_status -ne 0 ]]; then
			   wait $i
			   exit_status=$?
			   if [[ $exit_status -eq 0 ]]; then
				failed_tile_name=
				(( successfully_downloaded++ ))
			   else
				if [[ $retry_failed -eq 1 ]]; then
				   echo "ERROR: File '${pid_array[$i]}' was not downloaded properly from server $tile_server. Retrying..." >> "$logfile"
				   failed_tile_name="${pid_array[$i]}"
				else
				   echo "ERROR: File '${pid_array[$i]}' was not downloaded properly from server $tile_server." >> "$logfile"
				fi
			   fi
			   unset "pid_array[$i]"
			   if [[ ! -z "$failed_tile_name" && $retry_failed -eq 1 ]]; then
                     	failed_tile_name_url="$(echo $failed_tile_name | rev | cut -d'/' -f 1-3 | rev)"
                     	z=$(echo "$failed_tile_name_url" | awk -F'[/.]' '{print $2}')
                     	x=$(echo "$failed_tile_name_url" | awk -F'[/.]' '{print $3}')
                     	y=$(echo "$failed_tile_name_url" | awk -F'[/.]' '{print $4}')
                     	counter=0
                     	max_counter=3
                     	while [[ $counter -lt $max_counter ]]; do
				   wget "$(get_url $tile_server $z $x $y $ext)" -O "$download_folder/$z/$x/$y.$ext" -o /dev/null
                     	   exit_status=$?
                     	   if [[ $exit_status -ne 0 ]]; then
                     		(( counter++ ))
                     		echo "ERROR: File '$failed_tile_name_url' was not downloaded properly from server $tile_server after $counter retries." >> "$logfile"
                     		if [[ $counter -eq $max_counter ]]; then echo "ERROR: Giving up on file '$failed_tile_name_url'"  >> "$logfile"; fi
                     	   else
                     		echo "GOOD: File '$failed_tile_name_url' was eventually downloaded." >> "$logfile"
                     		counter=$max_counter
                     	   fi
                     	done
                     fi
			fi
		   done
		done
	   fi
      done
   done
   
   echo "Finished downloading on "$(date) >> "$logfile"
   
   problems_occured=$(( $total_tiles_to_download - $successfully_downloaded ))
   if [[ $problems_occured -gt 0 ]]; then
      echo "ERRORS logged. $(( $total_tiles_to_download - $successfully_downloaded ))/$total_tiles_to_download could not be downloaded successfully."
      echo "Please check the log file for more details."
      echo ""
      echo "Please download all of the tiles before continuing with the stitching. (rerun)"
      echo "The program will now exit."
      exit 1
   fi
fi


################################################
# Calculate the resolution of the final images #
################################################
# Each large, final tile generated by the smaller OSM extracted tiles, should
# not exceed the 'max_resolution_px' variable, and all of the generated tiles
# should have the same height/width.

# The initial 'vertical_resolution_per_stitch' is the total vertical resolution of all the
# tiles in y axis combined. This might be a very large image, so we want to find the a
# divisor that will give the least number of equally sized vertical crops, while the
# vertical resolution of each crop does not exceed 'max_resolution_px'.
vertical_resolution_per_stitch=$(( 256 * $number_of_vertical_tiles ))
vertical_divide_by=1
while [[ $vertical_resolution_per_stitch -gt $max_resolution_px ]]; do
	# Find which exact division gives a number less or equal to 'max_resolution_px'.
	temp=$(( $vertical_resolution_per_stitch / $vertical_divide_by ))
	temp2=$(( $temp * $vertical_divide_by ))
	# If $temp2 -ne $vertical_resolution_per_stitch, then the division is not exact.
	if [[ $temp2 -ne $vertical_resolution_per_stitch ]]; then
		let "vertical_divide_by++"
	else
		if [[ $temp -le $max_resolution_px ]]; then
			vertical_resolution_per_stitch=$temp
		else
			let "vertical_divide_by++"
		fi
	fi
done

# The total horizontal resolution is given by the number of tiles in x axis.
horizontal_resolution_per_stitch=$(( 256 * $number_of_horizontal_tiles ))
horizontal_divide_by=1
while [[ $horizontal_resolution_per_stitch -gt $max_resolution_px ]]; do
	# Find which exact division gives a number less or equal to 'max_resolution_px'
	temp=$(( $horizontal_resolution_per_stitch / $horizontal_divide_by ))
	temp2=$(( $temp * $horizontal_divide_by ))
	# If $temp2 -ne $horizontal_resolution_per_stitch, then the division is not exact.
	if [[ $temp2 -ne $horizontal_resolution_per_stitch ]]; then
		   let "horizontal_divide_by++"
	else
		   if [[ $temp -le $max_resolution_px ]]; then
				horizontal_resolution_per_stitch=$temp
		   else
				let "horizontal_divide_by++"
		   fi
	fi
done

######################################
# Start the stitching procedure here #
######################################
# If the user wants to skip the stitching and hasn't asked for file calibration, then exit the program here.

original_files_folder="$(pwd)/$project_folder/original_files/$zoom_level"
stitches_folder="$(pwd)/$project_folder/vertical_stitches/$zoom_level"
stitches_folder_final="$(pwd)/$project_folder/final_stitches/$zoom_level"

if [[ $skip_stitching -eq 1 || $only_calibrate -eq 1 ]]; then
   echo "Skipping stitching as requested..."
else
   # If we are running here, the user hasn't asked to skip the stitching. However,
   # if the user has asked to calibrate the files only, we still need to skip stitching.
   echo ""
   echo "Starting the stitching procedure..."
   echo ""
   if [[ -d "$original_files_folder" ]]; then
	if [[ -d "$stitches_folder" ]]; then
	   echo "Folder '$stitches_folder' already exists. Do you want to delete the folder's contents and recreate all of the tiles?"
	   echo "If you do not delete the folder, existing tiles will not be regenerated."
	   echo ""
	   echo "Delete folder content's? (y/N) "
	   read answer
	   if [[ "${answer,,}" == "y" ]]; then
		rm -rf "$stitches_folder/"*
	   fi
	else
	   mkdir -p "$stitches_folder"
	fi
	mkdir -p "$stitches_folder_final"
   else
	echo "Zoom level folder '$zoom_level' does not exist."
	exit 1
   fi

   files_per_folder=
   filenames_in_folder=()
   total_folders_to_be_processed=$(ls -U "$original_files_folder" | wc -l)
   ext=

   ####################################
   # Step 1: Make some sanity checks. #
   ####################################
   # Find how many files exist for all the subdirectories in the zoom level.
   # All the subdirectories should contain the same number of files with the same filenames.
   for folder in $(ls -U "$original_files_folder" | sort -n); do   
	full_path_folder="$original_files_folder"/"$folder"

	files_in_folder=$(ls -U "$full_path_folder" | wc -l)
	# On the first round in the for loop, $files_per_folder = blank (-z returns true)
	if [[ -z $files_per_folder ]]; then
	   # If it is the first round in the loop
	   files_per_folder=$files_in_folder
	   for filename in $(ls -U "$full_path_folder" | sort -n); do
		if [[ -z $ext ]]; then
		   ext="$(echo "$filename" | rev | cut -d. -f1 | rev)"
		else
		   if [[ "$(echo "$filename" | rev | cut -d. -f1 | rev)" != "$ext" ]]; then
			# If you find different extensions in a folder, then exit.
			echo "ERROR: '$filename' does not match default extension '$ext'"
			echo "       All the files in $full_path_folder must have the same extension."
			exit 1
		   fi
		fi
		filenames_in_folder+=( "$filename" )
	   done
	else
	   if [[ $files_in_folder -ne $files_per_folder ]]; then
		echo "First folder had $files_per_folder files in it."
		echo "Folder "$full_path_folder" has $files_in_folder files."
		echo "All the folders should have the same amount of files."
		exit 1
	   else
		for (( i=0; i<${#filenames_in_folder[@]}; i++ )); do
		   if [[ ! -f "$full_path_folder/${filenames_in_folder[$i]}" ]]; then
			echo "$filename"" is expected to be found in folder ""$full_path_folder"" but it doesn't look like it is there.'"
			echo "Please make sure that you have downloaded a big square tile from OpenStreeMap."
			exit 1
		   fi
		done
	   fi
	fi
   done

   # echo ${files_in_folder[@]}
   # echo ${filenames_in_folder[@]}

   #############################################
   # Step 2: Process the vertical tiles first. #
   #############################################

   ###########
   # Step 2.1:
   ###########
   # Once we have the vertical resolution divisor (it can also be 1 if there is no division needs to be done)
   # We have to find which of the original OSM tiles (256x256 pixels each) will compose each of the larger tiles.
   # Some of the original OSM tiles might have to be splitted and used by two of the larger tiles that we are
   # going to generate.
   pixels=0
   current_file=0
   # Initialize some dynamically named arrays to store the crop rules (how much each of the generated vertical
   # tiles needs to be cropped) and the filenames of the original OSM tiles that will be part of each of the
   # generated tiles.
   for (( i=0; i<$vertical_divide_by; i++ )); do
	eval "files_stitch_$i=()"
	eval "crop_rules_stitch_$i=()"
   done

   # The top-most stitch do not need a top crop and the bottom-most stitch do not need a bottom crop (since
   # the chosen divisor divides the vertical size equally), so initialize with zero value.
   crop_rules_stitch_0[0]=0
   eval "crop_rules_stitch_$(( $vertical_divide_by-1 ))[1]=0"

   for (( i=0; i<$vertical_divide_by; i++ )); do
	# echo "i: "$i
	# Each small tile is 256 pixels,
	while (( $pixels < ($i + 1) * $vertical_resolution_per_stitch )); do
	   #echo $current_file
	   # Add the filenames for each vertical stitch in an array.
	   eval "files_stitch_$i+=( \"${filenames_in_folder[$current_file]}\" )"
	   if (( $i - 1 < 0 )); then
		array_index=$current_file
	   else
		i_minus_1=$(( $i - 1 ))
		eval "temp_array_index=\${#files_stitch_$i_minus_1[@]}"
		array_index=$(( $current_file - $temp_array_index * $i ))
	   fi
	   #eval "echo \${files_stitch_$i[$array_index]}"
	   
	   let "pixels += 256 - pixels % 256"
	   #echo $pixels
	   let "current_file++"
	done
	
	# Store in the first element ([0]) of the crop array, the value that each of the
	# generated vertical tiles will need to be cropped by from the top.
	# Store in the second element ([1]) of the crop array, the value that each of the
	# generated vertical tiles will need to be cropped by from the bottom (although
	# we do not really use this value later).
	crop=$(( $pixels-($i + 1) * $vertical_resolution_per_stitch ))
	eval "crop_rules_stitch_$i[1]=$crop"
	if (( $i + 1 < $vertical_divide_by )); then
	   if (( $crop > 0 )); then
		eval "crop_rules_stitch_$((i + 1))[0]=$((256-$crop))"
	   else
		eval "crop_rules_stitch_$((i + 1))[0]=0"
	   fi
	fi
	if (( $pixels > ($i + 1) * $vertical_resolution_per_stitch )); then
	   let "pixels-=pixels-(i + 1)*vertical_resolution_per_stitch"
	   let "current_file--"
	fi
   done

   # echo ${files_stitch_0[@]}
   # echo ${#files_stitch_0[@]}
   # echo ${files_stitch_1[@]}
   # echo ${#files_stitch_1[@]}
   # echo ${files_stitch_2[@]}
   # echo ${#files_stitch_2[@]}
   # echo ${files_stitch_3[@]}
   # echo ${#files_stitch_3[@]}
   # echo ${files_stitch_4[@]}
   # echo ${#files_stitch_4[@]}
   # echo ${files_stitch_5[@]}
   # echo ${#files_stitch_5[@]}
   # echo ${files_stitch_6[@]}
   # echo ${#files_stitch_6[@]}
   # echo ${files_stitch_7[@]}
   # echo ${#files_stitch_7[@]}
   # 
   # echo ${crop_rules_stitch_0[@]}
   # echo ${crop_rules_stitch_1[@]}
   # echo ${crop_rules_stitch_2[@]}
   # echo ${crop_rules_stitch_3[@]}
   # echo ${crop_rules_stitch_4[@]}
   # echo ${crop_rules_stitch_5[@]}
   # echo ${crop_rules_stitch_6[@]}
   # echo ${crop_rules_stitch_7[@]}
   
   ###########
   # Step 2.2:
   ###########
   # Eventually use graphicsmagick to stich and crop the vertical tiles as needed.
   # This step will create many "thin" vertical tiles (256px wide) but very long (up to 'max_resolution_px' height).
   count=0
   for folder in $(ls "$original_files_folder"); do
	#eval "items_in_array=\${#files_stitch_$i[@]}"
	let "count++"
	echo "Processing vertical tiles in folder '"$zoom_level/$folder"' (progress: $count/$total_folders_to_be_processed)"
	for (( i=0; i<$vertical_divide_by; i++ )); do
	   eval "files_stitch_$i"_"$folder=( \"\${files_stitch_$i[@]/#/\"$original_files_folder/$folder/\"}\" )"
	   eval "crop_from_top=\${crop_rules_stitch_$i[0]}"
	
	   filename_to_save="$stitches_folder/"$folder"_"$i".png"
	   
	   # If the file does not exist, or the file is not corrupted (it can be properly read by the 'identify' command)
	   # or the height is not as needed ($vertical_resolution_per_stitch), then (re)-generate the file.
	   if [[ ! -f "$filename_to_save" || ! $(identify "$filename_to_save") || $(identify -format "%h" "$filename_to_save") -ne $vertical_resolution_per_stitch ]]; then
		echo "Building '$(readlink -f "$filename_to_save")'"
		# There is an annoying bug on graphicsmagick, and when I try to stitch jpg files, it shrinks the montaged file to half resolution :/
		# So use imagemagick when stitching jpg files from MapQuest.
		if [[ "$ext" == "jpg" ]]; then
		   eval "montage \"\${files_stitch_${i}_${folder}[@]}\" -tile 1x\${#files_stitch_$i"_"$folder[@]}  -geometry +0+0 \"$filename_to_save\""
		   convert -crop 256x"${vertical_resolution_per_stitch}"+0+"${crop_from_top}" "${filename_to_save}" "${filename_to_save}"
		else
                   # Use background none to keep the transparency on png's (if any)
		   eval "gm montage \"\${files_stitch_${i}_${folder}[@]}\" -tile 1x\${#files_stitch_${i}_${folder}[@]}  -background none -geometry +0+0 \"${filename_to_save}\""
		   gm convert -crop 256x"${vertical_resolution_per_stitch}"+0+"${crop_from_top}" "${filename_to_save}" "${filename_to_save}"
		fi
	   fi
	done
   done

   ########################################
   # Step 3: Process the horizontal tiles #
   ########################################
   # At this point we have many "thin" vertical tiles (256px wide) but very long (up to 'max_resolution_px' height).
   # Now we have to merge them in rows, in order to generate the final tiles.
   # We follow exactly the same steps that we followed in "Step 2", but for the horizontal length.

   ###########
   # Step 3.1:
   ###########

   count=0
   for (( j=0; j<$vertical_divide_by; j++ )); do

	filenames_in_folder=()
	for filename in $(ls -U "$stitches_folder/" | sort -n | grep "_$j.png"); do
	   filenames_in_folder+=( "$filename" )
	done
	
	pixels=0
	current_file=0

	for (( i=0; i<$horizontal_divide_by; i++ )); do
	   eval "files_stitch_$i=()"
	   eval "crop_rules_stitch_$i=()"
	done

	crop_rules_stitch_0[0]=0
	eval "crop_rules_stitch_$(( $horizontal_divide_by-1 ))[1]=0"

	for (( i=0; i<$horizontal_divide_by; i++ )); do
	   # echo "i: "$i
	   # Each tile is 256 pixels wide,
	   while (( $pixels < ($i + 1) * $horizontal_resolution_per_stitch )); do
		#echo $current_file
		# Add the filenames for each horizontal stitch in an array.
		eval "files_stitch_$i+=( ${filenames_in_folder[$current_file]} )"
		if (( $i - 1 < 0 )); then
		   array_index=$current_file
		else
		   i_minus_1=$(( $i - 1 ))
		   eval "temp_array_index=\${#files_stitch_$i_minus_1[@]}"
		   array_index=$(( $current_file - $temp_array_index * $i ))
		fi
		#eval "echo \${files_stitch_$i[$array_index]}"
		
		let "pixels += 256 - pixels % 256"
		#echo $pixels
		let "current_file++"
	   done
	   
	   crop=$(( $pixels-($i + 1) * $horizontal_resolution_per_stitch ))
	   #echo "crop: $crop"
	   eval "crop_rules_stitch_$i[1]=$crop"
	   if (( $i + 1 < $horizontal_divide_by )); then
		if (( $crop > 0 )); then
		   eval "crop_rules_stitch_$((i + 1))[0]=$((256-$crop))"
		else
		   eval "crop_rules_stitch_$((i + 1))[0]=0"
		fi
	   fi
	   if (( $pixels > ($i + 1) * $horizontal_resolution_per_stitch )); then
		let "pixels-=pixels-(i + 1)*horizontal_resolution_per_stitch"
		let "current_file--"
	   fi
	done

	###########
	# Step 3.2:
	###########

	#eval "items_in_array=\${#files_stitch_$i[@]}"
	for (( i=0; i<$horizontal_divide_by; i++ )); do
	   let "count++"
	   echo "Processing final tiles for row "$j", column "$i" (progress: $count/$(( $vertical_divide_by * $horizontal_divide_by )))"
	   
	   eval "files_stitch_${j}_${i}=( \"\${files_stitch_$i[@]/#/\"$stitches_folder/\"}\" )"
	   #eval "echo \${files_stitch_$j_$i[@]}"
	   eval "crop_from_left=\${crop_rules_stitch_$i[0]}"
	
	   filename_to_save="$stitches_folder_final/"$j"_"$i".png"
	   
	   # If the file does not exist, or the file is not corrupted (it can be properly read by the 'identify' command)
	   # or the width is not as needed ($horizontal_resolution_per_stitch), then (re)-generate the file.
	   if [[ ! -f "$filename_to_save" || $(identify -format "%w" "$filename_to_save") -ne $horizontal_resolution_per_stitch ]]; then
		echo "Building '$(readlink -f "$filename_to_save")'"
		# There is an annoying bug on graphicsmagick, and when I try to stitch jpg files, it shrinks the montaged file to half resolution :/
		# So use imagemagick when stitching jpg files from MapQuest.
		if [[ "$ext" == "jpg" ]]; then
		   eval "montage \"\${files_stitch_${j}_${i}[@]}\" -tile \${#files_stitch_${j}_${i}[@]}x1  -geometry +0+0 \"${filename_to_save}\""
		   convert -crop "${horizontal_resolution_per_stitch}"x"${vertical_resolution_per_stitch}"+"${crop_from_left}"+0 "${filename_to_save}" "${filename_to_save}"
		else
		   eval "gm montage \"\${files_stitch_${j}_${i}[@]}\" -tile \${#files_stitch_${j}_${i}[@]}x1 -background none -geometry +0+0 \"${filename_to_save}\""
		   gm convert -crop "${horizontal_resolution_per_stitch}"x"${vertical_resolution_per_stitch}"+"${crop_from_left}"+0 "${filename_to_save}" "${filename_to_save}"
		fi
	   fi
	done

   done


   echo ""
   echo "$(( $vertical_divide_by * $horizontal_divide_by )) ("$horizontal_divide_by"x"$vertical_divide_by") big tiles ($horizontal_resolution_per_stitch"x"$vertical_resolution_per_stitch pixels each) were generated"
   echo ""
fi

##############################################
# Produce OziExplorer .map Calibration files #
##############################################
# If the stitching is skipped, then the user might only need to download tiles.
# So producing map calibration files is useless, unless the user has requested
# just map calibration.
if [[ $skip_stitching -eq 0 || $only_calibrate -eq 1 ]]; then

#    filename="test"
#    extension="png"
#    width=14336
#    height=18432
#    zoom=11
# 
#    North=72.1818
#    West=-169.45312
#    East=-140.09766
#    South=56.26776

   echo "Calibrating maps"
   mkdir -p "$stitches_folder_final"
   # http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Zoom_levels
   # Tile size in degrees: 360/2^zoom x 170.1022/2^zoom
   # Pixel size in degrees: (360/2^zoom x 170.1022/2^zoom)/256
   horizontal_deg_per_px=$( awk -v z=$zoom_level 'BEGIN {printf "%.12f", 360/2^z/256 }' )
   vertical_deg_per_px=$( awk -v z=$zoom_level 'BEGIN {printf "%.12f", 170.1022/2^z/256 }' )
   
   westmost_long=$(xtile2long $tile_west $zoom_level)
   northmost_lat=$(ytile2lat $tile_north $zoom_level)
   northmost_pixel=$(( $tile_north * 256 + 1 ))
   westmost_pixel=$(( $tile_west * 256 + 1 ))
  
   # Process row (each vertical y represents one row)....
   for ((y=0; y<$vertical_divide_by; y++)); do
	# ...and columns x for each row y.
	for ((x=0; x<$horizontal_divide_by; x++)); do
           top_pixel_on_current_map=$(( $northmost_pixel + $y * $vertical_resolution_per_stitch ))
           bottom_pixel_on_current_map=$(( $northmost_pixel + $y * $vertical_resolution_per_stitch + $vertical_resolution_per_stitch - 1 ))
           left_pixel_on_current_map=$(( $westmost_pixel + $x * $horizontal_resolution_per_stitch ))
           right_pixel_on_current_map=$(( $westmost_pixel + $x * $horizontal_resolution_per_stitch + $horizontal_resolution_per_stitch - 1 ))
           
	   N=$(ypixel2lat $top_pixel_on_current_map $zoom_level)
	   S=$(ypixel2lat $bottom_pixel_on_current_map $zoom_level)
	   W=$(xpixel2long $left_pixel_on_current_map $zoom_level)
	   E=$(xpixel2long $right_pixel_on_current_map $zoom_level)
	   # echo "$y"_"$x"
	   # echo -e "$N"
	   # echo -e "$S"
	    echo -e "$W"
	    echo -e "$E\n"
	   echo "$(generate_OZI_map_file "$y"_"$x" "png" "$horizontal_resolution_per_stitch" "$vertical_resolution_per_stitch" "$zoom_level" "$N" "$W" "$E" "$S")" > "$stitches_folder_final"/"$y"_"$x".map
	   echo "Generated map calibration file "$stitches_folder_final"/"$y"_"$x".map"
	done
   done
fi

# To compose two images (satellite with hybrid on top), use the convert command like this:
#   convert sat-img/11/0_0.png hyb-img/11/0_0.png -composite 0_0.png
# Use the already generated oziexplorer map files.
# Of course, the W, E, N, S should be exactly the same for the sat and hyb images.
