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

# How to use this script
# 1. Download and run JTileDownloader
#      svn co http://svn.openstreetmap.org/applications/utils/downloading/JTileDownloader/trunk/ JTileDownloader
#      (use "ant run" if you want to do any modifications and compile the program)
#      java -jar jar/jTileDownloader-0-6-1.jar
# 2. Configure JTileDownloader
#      a) In the Options tab, untick the "Wait <n> sec after downloading <m> tiles?> tick box.
#      b) In the Options tab, increase the "Download Threads" to the maximum (4).
#      c) In the Main tab, on the "Alt. TileServer" field add your own server to download the tiles from.
#      d) In the Main tab, choose the "Bounding Box (Lat/Lon)" sub-tab and use the "Slippy Map chooser" to choose a rectangle that you want to download the tile from.
#      e) Choose the zoom level
#      f) Choose the desired "Outputfolder". The tiles will be downloaded in a folder with the number of the chosen zoom level, located under the directory that you chose in the "Outputfolder"
#      g) Make sure that the "Outputfolder" is empty.
#      h) Press the button "Download Tiles"
#      i) Wait for the tile-download to complete. If you use a zoom level of 11 or more, it might take several thousand tiles to be downloaded as each OSM tile is 256x256px.
#         Each zoom level equivalent scale is:
#             Level   Degree  Area              m / pixel       ~Scale
#             0       360     whole world       156,412         1:500 Mio
#             1       180                       78,206          1:250 Mio
#             2       90                        39,103          1:150 Mio
#             3       45                        19,551          1:70 Mio
#             4       22.5                      9,776           1:35 Mio
#             5       11.25                     4,888           1:15 Mio
#             6       5.625                     2,444           1:10 Mio
#             7       2.813                     1,222           1:4 Mio
#             8       1.406                     610.984         1:2 Mio
#             9       0.703   wide area         305.492         1:1 Mio
#             10      0.352                     152.746         1:500,000
#             11      0.176   area              76.373          1:250,000
#             12      0.088                     38.187          1:150,000
#             13      0.044   village or town   19.093          1:70,000
#             14      0.022                     9.547           1:35,000
#             15      0.011                     4.773           1:15,000
#             16      0.005   small road        2.387           1:8,000
#             17      0.003                     1.193           1:4,000
#             18      0.001                     0.596           1:2,000
#             19      0.0005                    0.298           1:1,000 
# 3. Copy this script in the chosen "Outputfolder".
# 4. Run the script with one command line argument, that of the zoom level 
#      e.g. if you chose to download tiles with zoom 12 and you set the "Outputfolder" in JTileDownloader to be "~/downloaded_tiles"
#           add this script in the directory "~/downloaded_tiles" and execute like this:
#                 $ cd ~/downloaded_tiles
#                 $ ./stitch-osm-tiles.sh 12

trap "exit" INT

# The horizontal or vertical resolution of the final tiles should not exceed that of the $max_resolution_px variable
max_resolution_px=20000
# MapQuest tile servers:
#   http://otile1.mqcdn.com/tiles/1.0.0/osm
#   http://otile2.mqcdn.com/tiles/1.0.0/osm
#   http://otile3.mqcdn.com/tiles/1.0.0/osm
#   http://otile4.mqcdn.com/tiles/1.0.0/osm
osm_server=${OSM_SERVER:-}
# Available MAPQUEST Overlays:
#   osm: OpenStreetMap (available zoom levels 0-18)
#   sat: Satellite (available zoom levels 0-11)
overlay=${OSM_MAPQUEST_OVERLAY:-osm}
osm_mapquest_servers=( "http://otile1.mqcdn.com/tiles/1.0.0/osm" "http://otile2.mqcdn.com/tiles/1.0.0/osm" "http://otile3.mqcdn.com/tiles/1.0.0/osm" "http://otile4.mqcdn.com/tiles/1.0.0/osm" )

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
  echo " -z|--zoom-level ZOOM           Valid ZOOM values: 0-18"
  echo " -o|--osm-server OSM_SERVER     The URL of your tile server. If this option is"
  echo "                                  not set, mapquest tile servers will be used."
  echo "                                  This option can also be set as an OSM_SERVER"
  echo "                                  environment variable OSM_SERVER."
  echo " -w|--lon1 W_DEGREES            Set the western (W) longtitude of a bounding box for"
  echo "                                  tile downloading. -e, -n and -s should also be set."
  echo " -e|--lon2 E_DEGREES            Set the eastern (E) longtitude of a bounding box for"
  echo "                                  tile downloading. -w, -n and -s should also be set."
  echo " -n|--lat1 N_DEGREES            Set the northern (N) latitude of a bounding box for"
  echo "                                  tile downloading. -w, -e and -s should also be set."
  echo " -s|--lat2 S_DEGREES            Set the southern (S) latitude of a bounding box for"
  echo "                                  tile downloading. -w, -e, and -n should also be set."
  echo " -p|--skip-stitching            This option can be used together with the -w, -e, -n"
  echo "                                  and -s options, in order to just download tiles, but"
  echo "                                  not stitch them together. The stitching can always"
  echo "                                  done later."
  echo " -h|--help                      Prints this help message."
  echo ""
  exit 0
}

######################################################################################
# Define functions to get tiles from longitude/latitude and vice versa
# http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Coordinates_to_tile_numbers_2
#
#   X and Y
#      X goes from 0 (left edge is 180 °W) to 2zoom − 1 (right edge is 180 °E)
#      Y goes from 0 (top edge is 85.0511 °N) to 2zoom − 1 (bottom edge is 85.0511 °S) in a Mercator projection
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
 ytile=$1;
 zoom=$2;
 tms=$3;
 if [ ! -z "${tms}" ]
 then
 #  from tms_numbering into osm_numbering
  ytile=`echo "${ytile}" ${zoom} | awk '{printf("%d\n",((2.0^$2)-1)-$1)}'`;
 fi
 lat=`echo "${ytile} ${zoom}" | awk -v PI=3.14159265358979323846 '{ 
       num_tiles = PI - 2.0 * PI * $1 / 2.0^$2;
       printf("%.9f", 180.0 / PI * atan2(0.5 * (exp(num_tiles) - exp(-num_tiles)),1)); }'`;
 echo "${lat}";
}
 
lat2ytile() 
{ 
 lat=$1;
 zoom=$2;
 tms=$3;
 ytile=`echo "${lat} ${zoom}" | awk -v PI=3.14159265358979323846 '{ 
   tan_x=sin($1 * PI / 180.0)/cos($1 * PI / 180.0);
   ytile = (1 - log(tan_x + 1/cos($1 * PI/ 180))/PI)/2 * 2.0^$2; 
   ytile+=ytile<0?-0.5:0.5;
   printf("%d", ytile ) }'`; 
 if [ ! -z "${tms}" ]
 then
  #  from oms_numbering into tms_numbering
  ytile=`echo "${ytile}" ${zoom} | awk '{printf("%d\n",((2.0^$2)-1)-$1)}'`;
 fi
 echo "${ytile}";
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

E_BADARGS=65

download_tiles=0
lon1=
lon2=
lat1=
lat2=
zoom_level=
skip_stitching=0

args=$(getopt --options z:w:e:n:s:ho:p --longoptions zoom-level:,lon1:,lon2:,lat1:,lat2:,help,osm-server:,skip-stitching -- "$@")

#if [ "$(echo "$args" | $EGREP "(^|'[[:space:]]')-z[[:space:]]")" == "" ]; then
#       echo "\nParameter \"-z (--zoom-level)\" is mandatory.."
#       usage
#       exit 1
#fi

eval set -- "$args"

for i
do
   case "$i" in
      -z|--zoom-level) shift
         zoom_level=$1
         shift
         ;;  
      -w|--lon1) shift
         lon1=$1
         download_tiles=1
         shift
         #echo "Longitude west was set to $lon1"
         ;;  
      -e|--lon2) shift
         lon2=$1
         download_tiles=1
         shift
         #echo "Longitude east was set to $lon2"
         ;;  
      -n|--lat1) shift
         lat1=$1
         download_tiles=1
         shift
         #echo "Latitude north was set to $lat1"
         ;;  
      -s|--lat2) shift
         lat2=$1
         download_tiles=1
         shift
         #echo "Latitude south was set to $lat2"
         ;;
      -o|--osm-server) shift
         osm_server="$1"
         shift
         ;;
      -p|--skip-stitching) shift
         skip_stitching=1
         ;;
      -h|--help) shift
         usage
         ;;
   esac
done

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

# TODO: Add a command line parameter for tuning the parallel (multithreaded) wget downloads.
#       Update the readme at the top of this file and the README.md file.
#       Implement automatic calibration for OziExplorer.
#       Make subroutines for the stitching functionality?

#####################################################################
# If at least one coordinate has been given, try to download tiles. #
#####################################################################
if [[ $download_tiles -eq 1 ]]; then
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

   # Eventually download the tiles.
   total_tiles_to_download=$(( (($tile_east - $tile_west) + 1) * (( $tile_south - $tile_north ) + 1) ))
   downloading_now=0
   successfully_downloaded=0
   parallel_downloads=30
   #set -x
   echo "Started downloading on "$(date) > $zoom_level.log
   echo "Downloading $total_tiles_to_download tiles."
   declare -A pid_array=()
   for (( lon=$tile_west; lon<=$tile_east; lon++)); do
      mkdir -p mkdir "$zoom_level/$lon"
      for (( lat=$tile_north; lat<=$tile_south; lat++)); do
         (( ++downloading_now ))
         # If an ${osm_server} is not provided by the OSM_SERVER environment variable, 
         # or by the "-o" option, then try to use the MapQuest servers in a round-robin fashion.
         if [[ -z "${osm_server}" ]]; then
            # MapQuest serves jpg files
            tile_server=${osm_mapquest_servers[$(( $downloading_now % ${#osm_mapquest_servers[@]} ))]}
            ext="jpg"
         else
            # The default OSM servers usually serve png's
            tile_server="$osm_server"
            ext="png"
         fi
         
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
                        (( successfully_downloaded++ ))
                     else
                        # If the exit status of the finished background process is not 0 (meaning that the process
                        # did not finish successfylly), then add a log warning so that the user knows which tiles
                        # faced download problems.
                        echo "ERROR: File ${pid_array[$i]} was not downloaded properly from server $tile_server." >> $zoom_level.log
                     fi
                     # remove the pid from the array
                     unset "pid_array[$i]"
                     (( removed++ ))
                  fi
               done
            done
         fi
         
         # If the file does not exist or is corrupted, then download the file.
         if [[ ! -f "$zoom_level/$lon/$lat.$ext" || $(identify -format "%h" "$zoom_level/$lon/$lat.$ext") -ne 256 && $(identify -format "%w" "$zoom_level/$lon/$lat.$ext") -ne 256 ]]; then
            echo "Downloading tile $downloading_now/$total_tiles_to_download.."
            # Start a new download thread using wget and put it in the background.
            wget "$tile_server/$zoom_level/$lon/$lat.$ext" -O "$zoom_level/$lon/$lat.$ext" -o /dev/null &
            # Store the PID of the last wget command added in the background.
            pid_array[$!]="$zoom_level/$lon/$lat.$ext"
         else
            echo "File '$zoom_level/$lon/$lat.$ext' ($downloading_now/$total_tiles_to_download) already downloaded."
            (( successfully_downloaded++ ))
         fi
         
      done
   done
   echo "Finished downloading on "$(date) >> $zoom_level.log
   
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

if [[ $skip_stitching -eq 1 ]]; then
   echo "Skipping stitching."
   if [[ $download_tiles -ne 1 ]]; then
      echo "The option --skip-stitching only makes sense to use when downloading tiles... :/"
      echo "Skipping stitching anyway..."
   fi
   exit 0
fi

######################################
# Start the stitching procedure here #
######################################
if [[ -d "$zoom_level" ]]; then
   stitches_folder="$(pwd)/stitches/$zoom_level"
   stitches_folder_final="$stitches_folder/../final/$zoom_level/"
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
total_folders_to_be_processed=$(ls -U $zoom_level | wc -l)
ext=

####################################
# Step 1: Make some sanity checks. #
####################################
# Find how many files exist for all the subdirectories in the zoom level.
# All the subdirectories should contain the same number of files with the same filenames.
for folder in $(ls -U $zoom_level | sort -n); do   
   full_path_folder="$(pwd)/$zoom_level"/"$folder"

   files_in_folder=$(ls -U "$full_path_folder" | wc -l)
   # On the first round in the for loop, $files_per_folder = blank (-z returns true)
   if [[ -z $files_per_folder ]]; then
      # If it is the first round in the loop
      files_per_folder=$files_in_folder
      for filename in $(ls -U "$full_path_folder" | sort -n); do
         if [[ -z $ext ]]; then
            ext="$(echo "$filename" | rev | cut -d. -f1 | rev)"
         else
            if [[ "$(echo "$filename" | rev | cut -d. -f1 | rev)" -ne "$ext" ]]; then
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
# The vertical resolution of each large tile generated by the smaller OSM extracted tiles,
# should not exceed the 'max_resolution_px' variable, and all of the generated tiles should
# have the same height.

###########
# Step 2.1: 
###########
# The initial 'vertical_resolution_per_stitch' is the total vertical resolution of all the
# images combined. This might be a very large image, so we want to find the a divisor that
# will give the least number of equally sized vertical crops, while the vertical resolution
# of each crop does not exceed 'max_resolution_px'.
vertical_resolution_per_stitch=$(( 256 * $files_per_folder ))
vertical_divide_by=1
# The next 'while' loop divides the total
while [[ $vertical_resolution_per_stitch -gt $max_resolution_px ]]; do
	# Find which exact division gives a number less or equal to 20000.
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

###########
# Step 2.2:
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
# Step 2.3:
###########
# Eventually use graphicsmagick to stich and crop the vertical tiles as needed.
# This step will create many "thin" vertical tiles (256px wide) but very long (up to 'max_resolution_px' height).
count=0
for folder in $(ls $zoom_level); do
   #eval "items_in_array=\${#files_stitch_$i[@]}"
   let "count++"
   echo "Processing vertical tiles in folder "./$zoom_level/$folder" (progress: $count/$total_folders_to_be_processed)"
   for (( i=0; i<$vertical_divide_by; i++ )); do
      eval "files_stitch_$i_$folder=( \${files_stitch_$i[@]/#/$(pwd)\/$zoom_level\/$folder\/} )"
      #eval "echo \${files_stitch_$i_$folder[@]}"
      eval "crop_from_top=\${crop_rules_stitch_$i[0]}"
   
      filename_to_save="$stitches_folder/"$folder"_"$i".png"
      
      # If the file does not exist, or the file is not corrupted (it can be properly read by the 'identify' command)
      # or the height is not as needed ($vertical_resolution_per_stitch), then (re)-generate the file.
      if [[ ! -f "$filename_to_save" || ! $(identify "$filename_to_save") || $(identify -format "%h" "$filename_to_save") -ne $vertical_resolution_per_stitch ]]; then
         echo "Building '$(readlink -f "$filename_to_save")'"
         # There is an annoying bug on graphicsmagick, and when I try to stitch jpg files, it shrinks the montaged file to half resolution :/
         # So use imagemagick when stitching jpg files from MapQuest.
         if [[ "$ext" == "jpg" ]]; then
            eval "montage \${files_stitch_$i_$folder[@]} -tile 1x\${#files_stitch_$i_$folder[@]}  -geometry +0+0 $filename_to_save"
            convert -crop 256x"$vertical_resolution_per_stitch"+0+"$crop_from_top" "$filename_to_save" "$filename_to_save"
         else
            eval "gm montage \${files_stitch_$i_$folder[@]} -tile 1x\${#files_stitch_$i_$folder[@]}  -geometry +0+0 $filename_to_save"
            #eval "echo gm montage \${files_stitch_$i_$folder[@]} -tile 1x\${#files_stitch_$i_$folder[@]}  -geometry +0+0 $filename_to_save"
            #echo 'identify -format "%h" "$filename_to_save"' $(identify -format "%h" "$filename_to_save")
            #echo $vertical_resolution_per_stitch
            #echo 'gm convert -crop 256x"$vertical_resolution_per_stitch"+0+"$crop_from_top" "$filename_to_save" "$filename_to_save"' "-crop 256x"$vertical_resolution_per_stitch"+0+"$crop_from_top" "$filename_to_save" "$filename_to_save")"
            gm convert -crop 256x"$vertical_resolution_per_stitch"+0+"$crop_from_top" "$filename_to_save" "$filename_to_save"
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

# The total horizontal resolution is given by the number of folders located under the "$zoom_level" folder
horizontal_resolution_per_stitch=$(( 256 * $(ls -U $zoom_level | wc -l) ))

###########
# Step 3.1:
###########
horizontal_divide_by=1
# The next 'while' loop divides the total
while [[ $horizontal_resolution_per_stitch -gt $max_resolution_px ]]; do
        # Find which exact division gives a number less or equal to 20000.
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

###########
# Step 3.2:
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
   # Step 3.3:
   ###########

   #eval "items_in_array=\${#files_stitch_$i[@]}"
   for (( i=0; i<$horizontal_divide_by; i++ )); do
      let "count++"
      echo "Processing final tiles for row "$j", column "$i" (progress: $count/$(( $vertical_divide_by * $horizontal_divide_by )))"
      
      eval "files_stitch_$j_$i=( \${files_stitch_$i[@]/#/$stitches_folder\/} )"
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
            eval "montage \${files_stitch_$j_$i[@]} -tile \${#files_stitch_$j_$i[@]}x1  -geometry +0+0 $filename_to_save"
         
            convert -crop "$horizontal_resolution_per_stitch"x"$vertical_resolution_per_stitch"+"$crop_from_left"+0 "$filename_to_save" "$filename_to_save"
         else
            eval "gm montage \${files_stitch_$j_$i[@]} -tile \${#files_stitch_$j_$i[@]}x1  -geometry +0+0 $filename_to_save"
         
            gm convert -crop "$horizontal_resolution_per_stitch"x"$vertical_resolution_per_stitch"+"$crop_from_left"+0 "$filename_to_save" "$filename_to_save"
         fi
      fi
   done

done


echo ""
echo "$(( $vertical_divide_by * $horizontal_divide_by )) ("$horizontal_divide_by"x"$vertical_divide_by") big tiles ($horizontal_resolution_per_stitch"x"$vertical_resolution_per_stitch pixels each) were generated"
echo ""
