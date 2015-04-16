# stitch-osm-tiles
Stitch OpenStreetMap tiles and generate very large regions of maps for high quality printouts or use with other mapping software.


# Prerequisites

Bash4 is needed, because I use associative arrays in order to parallelize the download of tiles. If you use a recent distro, that shouldn't be a problem.

Both graphics magick and imagemagick are needed.

`apt-get install graphicsmagick imagemagick`

The 'identify' utility of the imagemagick library is much much faster, but graphicsmagick library's montage and crop operations that are used by this script, are much faster. That's why I use both libraries. Moreover, graphicsmagick jpg stitching results in half sized tiles. This must be a bug, but I haven't bothered looking deeper into it. Whenever the script stitches large tiles from jpg sources, imagemagick is used instead.

# How to use this script
The plan is to convert the script in python language because I started this project as a simple bash script, but eventually it grown up to a monster bash script. When I find time to do this, I will probably write some examples here on how to use this script. For the moment, use the --help option.
`./stitch-osm-tiles.sh --help`
