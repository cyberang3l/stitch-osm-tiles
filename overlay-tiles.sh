#!/bin/bash

# Use this script to create a batch of overlayed tiles/stitched-tiles from a base layer anda an overlay layer.
# Execute the script with the -h/--help parameter to get a list of supported command line arguments.
#
# Example of overlaying hiking paths for the Everest Base Camp:
#
# 1) Use stitch-osm-tiles.py to download a base topomap layer:
#    ./stitch-osm-tiles.py -p Nepal-Everest-Base -n 28.0344 -s 27.6501 -w 86.6698 -e 86.9479 -z 1-14 -t Misc -l opentopomap --download-threads 5 --retry-failed --prepare-tiles-for-software maverick
#
# 2) Use stitch-osm-tiles.py to download an overlay layer for EXACTLY the same area and with exactly the same parameters that you used in step 1.
#    Only the -t/-l parameters should change in order to choose the desired overlay tiles to be downloaded:
#    ./stitch-osm-tiles.py -p Nepal-Everest-Overlay -n 28.0344 -s 27.6501 -w 86.6698 -e 86.9479 -z 1-14 -t Misc -l overlay_hiking_paths --download-threads 5 --retry-failed --prepare-tiles-for-software maverick
#
# 3) Use this script to combine the layers in a new folder. The overlay will be combined with 70% opacity in this example:
#    ./overlay-tiles.sh -b Nepal-Everest-Base -o Nepal-Everest-Overlay -d Nepal-Everest-Overlayed -p 0.7

function get_color {
	echo '\033['"$1"'m'
}

Black=$(get_color '0;30')
Blue=$(get_color '0;34')
Green=$(get_color '0;32')
Cyan=$(get_color '0;36')
Red=$(get_color '0;31')
Purple=$(get_color '0;35')
Brown=$(get_color '0;33')
LightGray=$(get_color '0;37')
DarkGray=$(get_color '1;30')
LightBlue=$(get_color '1;34')
LightGreen=$(get_color '1;32')
LightCyan=$(get_color '1;36')
LightRed=$(get_color '1;31')
LightPurple=$(get_color '1;35')
Yellow=$(get_color '1;33')
White=$(get_color '1;37')
Reset=$(get_color '0')

error_msg() {
	msg="${1}"
	echo -e "${LightRed}ERROR${Reset}: ${Yellow}${msg}${Reset}"
}

compare_nums()
{
	# Function to compare two numbers (float or integers) by using awk.
	# The function will not print anything, but it will return 0 (if the comparison is true) or 1
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
	if ! [[ $num1 =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then return $E_BADARGS; fi
	if ! [[ $num2 =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then return $E_BADARGS; fi

	# If you want to print the exit code as well (instead of only returning it), uncomment
	# the awk line below and comment the uncommented one which is two lines below.
	#awk 'BEGIN {print return_code=('$num1' '$op' '$num2') ? 0 : 1; exit} END {exit return_code}'
	awk 'BEGIN {return_code=('$num1' '$op' '$num2') ? 0 : 1; exit} END {exit return_code}'
	return_code=$?
	return $return_code
}

# Check dependencies
if ! which bc > /dev/null ; then
	error_msg "The command 'bc' is required by this program."
	exit 1
elif ! which convert > /dev/null ; then
	error_msg "The imagemagick 'convert' command is required by this program."
	exit 1
fi

# Provide a help/usage message
usage() {
	echo -e "Usage: $(basename $0) -b BASE_PROJECT_PATH -o OVERLAYER_PROJECT_PATH -d DESTINATION_PROJECT_PATH [OPTIONS]"
	echo -e ""
	echo -e "$(basename $0) composes base tiles with overlay tiles."
	echo -e ""
	echo -e "Command line parameters:"
	echo -e "  -b BASE_PROJECT_PATH, --base-project-path BASE_PROJECT_PATH"
	echo -e "                           Path of the base project with tiles that have been"
	echo -e "                           downloaded with 'stitch-osm-tiles.py'."
	echo -e ""
	echo -e "  -o OVERLAY_PROJECT_PATH, --overlay-project-path OVERLAY_PROJECT_PATH"
	echo -e "                           Path of the overlay project with tiles that have been"
	echo -e "                           downloaded with 'stitch-osm-tiles.py'. Note that the"
	echo -e "                           overlay project must be having the same folder and file"
	echo -e "                           structure with the base project."
	echo -e ""
	echo -e "  -b DESTINATION_PROJECT_PATH, --destination-project-path DESTINATION_PROJECT_PATH"
	echo -e "                           Path of the destination project with all the overlayed"
	echo -e "                           tiles."
	echo -e ""
	echo -e "  -p OVERLAY_OPACITY, --overlay-opacity OVERLAY_OPACITY"
	echo -e "                           A float number between 0 and 1 that controls the opacity"
	echo -e "                           of the overlay layer. 0 makes the overlay fully transparent,"
	echo -e "                           1 makes the overlay fully opaque. Default: 1.0"
	echo -e ""
	echo -e "  -h, --help               Displays this help message."
}

# Parse command line arguments
ARGS=$( \
	getopt \
		-o b:o:d:p:h \
		-l "base-project-path:,overlay-project-path:,destination-project-path:,overlay-opacity:,help" \
		-n "$(basename $0)" \
		-- "$@" \
)

# Exit on bad arguments
if [ $? -ne 0 ] ; then exit 1 ; fi

# Evaluate the command line arguments
eval set -- "$ARGS";

while true ; do
	case "$1" in
		-b|--base-project-path)        shift ; BASE_PROJECT_PATH="$1" ; shift ;;
		-o|--overlay-project-path)     shift ; OVERLAY_PROJECT_PATH="$1" ; shift ;;
		-d|--destination-project-path) shift ; DESTINATION_PROJECT_PATH="$1" ; shift ;;
		-p|--overlay-opacity)          shift ; OVERLAY_OPACITY="$1" ; shift ;;
		-h|--help)                     shift ; usage ; exit 0 ;;
		--)                            shift ; break ;;
	esac
done

# Define variable defaults
OVERLAY_OPACITY=${OVERLAY_OPACITY:-1.0}

# Perform sanity checks
if [[ -z "${BASE_PROJECT_PATH}" || -z "${OVERLAY_PROJECT_PATH}" || -z "${DESTINATION_PROJECT_PATH}" ]] ; then
	error_msg "Base project path, overlay project path and destination project path"
	error_msg "are all required parameters."
	echo "-----------"
	usage
	exit 1
elif [[ ! -d "${BASE_PROJECT_PATH}" ]] ; then
	error_msg "The base project path '${BASE_PROJECT_PATH}' is not a directory"
	exit 1
elif [[ ! -d "${OVERLAY_PROJECT_PATH}" ]] ; then
	error_msg "The overlay project path '${OVERLAY_PROJECT_PATH}' is not a directory"
	exit 1
elif [[ "${BASE_PROJECT_PATH}" == "${DESTINATION_PROJECT_PATH}" || \
	"${OVERLAY_PROJECT_PATH}" == "${DESTINATION_PROJECT_PATH}" ]] ; then
	error_msg "The destination project path should be different than the base"
	error_msg "project path and the overlay project path."
	exit 1
fi

if compare_nums $OVERLAY_OPACITY "<" 0 || compare_nums $OVERLAY_OPACITY ">" 1 || \
	[[ ! $OVERLAY_OPACITY =~ ^-?[0-9]+([.][0-9]+)?$ ]] ; then
	error_msg "Overlay opacity accepts numeric values between 0 and 1."
	exit 1
fi

if [[ -d "${DESTINATION_PROJECT_PATH}" ]] ; then
	echo -e "Destination project path ${DESTINATION_PROJECT_PATH} already exists."
	echo -n "Do you want to continue and overwrite any existing files within the folder? (Y/n): "
	read answer
	if [[ ${answer} == 'Y' || ${answer,,} == 'yes' ]] ; then
		echo -e "Continuing with destination project path ${DESTINATION_PROJECT_PATH}"
	else
		echo -e "Aborting."
		exit 0
	fi
else
	mkdir -p "${DESTINATION_PROJECT_PATH}"
fi

# Use full paths
BASE_PROJECT_PATH="$(realpath ${BASE_PROJECT_PATH})"
OVERLAY_PROJECT_PATH="$(realpath ${OVERLAY_PROJECT_PATH})"
DESTINATION_PROJECT_PATH="$(realpath ${DESTINATION_PROJECT_PATH})"

# Do the work
divideby=$(echo 1 / $OVERLAY_OPACITY | bc -l)
# If we have a maverick folder, the content of is_maverick
# variable will be "1". Otherwise it will be "0".
is_maverick=$(find ${BASE_PROJECT_PATH} -maxdepth 1 -type d -name maverick | wc -l)

counter=0
while read folder_in_base ; do
	echo "Parsing files in folder ${folder_in_base}"
	while read file_in_base ; do
		if file "${file_in_base}" | grep -qE 'image|bitmap' ; then
			let "counter += 1"
			echo "${counter}: ${file_in_base}"

			file_in_overlay="${OVERLAY_PROJECT_PATH}/${file_in_base#"${BASE_PROJECT_PATH}"}"
			folder_in_overlay="${OVERLAY_PROJECT_PATH}/${folder_in_base#"${BASE_PROJECT_PATH}"}"

			file_in_destination="${DESTINATION_PROJECT_PATH}/${file_in_base#"${BASE_PROJECT_PATH}"}"
			folder_in_destination="${DESTINATION_PROJECT_PATH}/${folder_in_base#"${BASE_PROJECT_PATH}"}"

			#echo $file_in_overlay
			#echo $folder_in_overlay
			#echo $file_in_destination
			#echo $folder_in_destination
			mkdir -p "${folder_in_destination}"

			# Combine the base with the overlay and save to destination if the destination
			# file doesn't exist already, or if it exists but it's zero bytes.
			if ! ls "${file_in_destination}" &> /dev/null || [[ $(stat --printf="%s" "${file_in_destination}") -eq 0 ]] ; then
				convert "${file_in_base}" \( "${file_in_overlay}" -alpha set -channel A -evaluate divide ${divideby} \) -composite "${file_in_destination}"
			fi

			if [[ ${is_maverick} -eq 1 ]] ; then
				# We don't want to traverse the maverick folder.
				# If we have a maveric folder, we copy the data in the end with
				# an added .tile extension.
				file_in_destination_maverick="${DESTINATION_PROJECT_PATH}/maverick/${file_in_base#"${BASE_PROJECT_PATH}"}.tile"
				folder_in_destination_maverick="${DESTINATION_PROJECT_PATH}/maverick/${folder_in_base#"${BASE_PROJECT_PATH}"}"
				mkdir -p "${folder_in_destination_maverick}"
				cp "${file_in_destination}" "${file_in_destination_maverick}"
			fi
		else
			:
			#echo "File '$file_in_base' is not an image"
		fi
	done < <(find "${folder_in_base}" -maxdepth 1 -type f)
done < <(find "${BASE_PROJECT_PATH}" -not -path "${BASE_PROJECT_PATH}/maverick*" -mindepth 1 -type d)
