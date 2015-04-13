#!/bin/bash

# Once you have the final tiles stitched, you might want to delete some of them that do not contain
# any useful information (such as tiles located over the ocean for example).
# This script will create a indexed collage of the final larged stitched tiles, and the user can quickly
# choose which file names will have to be deleted.

# In order for this script to work, you will need the packages 'graphicsmagick' and 'parallel'
##
# apt-get install graphicsmagick parallel
##

if [[ $# -ne 1 ]]; then
   echo "Please choose a folder with the final stitches to make an indexed collage."
   exit 1
fi

folder="$1"
cd "${folder}"

all_files=$(ls *.png | wc -l)

if [[ ! -d thumbs ]]; then
   mkdir thumbs
fi

if [[ $(ls thumbs/*.png | wc -l) -ne ${all_files} ]];
   parallel --progress gm mogrify -quality 100 -output-directory thumbs -resize 128x128 ::: *.png
fi

cd thumbs

rows=$(ls | sort -V | sed 's/_.*//' | uniq | wc -l)
columns=$(( all_files / rows ))

gm montage $(for i in "$( ls *_*.png | sort -V )"; do echo "$i"; done) -tile ${columns}x${rows} -background white -geometry +1+1 collage.png
gm montage -label '%f' $(for i in "$( ls *_*.png | sort -V )"; do echo "$i"; done) -tile ${columns}x${rows} -background white -geometry +1+6 collage-labels.png
gm montage -draw 'gravity South fill red stroke red text 0,7 "%f"' -pointsize 16 $(for i in "$( ls *_*.png | sort -V )"; do echo "$i"; done) -tile ${columns}x${rows} -background white -geometry +1+1 collage-labels-on-tiles.png
