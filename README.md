# stitch-osm-tiles
Stitch OpenStreetMap tiles and generate very large regions of maps for high quality printouts or use with other mapping software.


# Prerequisites

`apt-get install graphicsmagick imagemagick`

The 'identify' utility of the imagemagick library is much much faster, but graphicsmagick library's montage and crop operations that are used by this script, are much faster.
That's why I use both libraries.

# How to use this script
1. Download and run JTileDownloader
      - svn co http://svn.openstreetmap.org/applications/utils/downloading/JTileDownloader/trunk/ JTileDownloader
      - (use "ant run" if you want to do any modifications and compile the program)
      - java -jar jar/jTileDownloader-0-6-1.jar
2. Configure JTileDownloader
      - In the Options tab, untick the "Wait <n> sec after downloading <m> tiles?> tick box.
      - In the Options tab, increase the "Download Threads" to the maximum (4).
      - In the Main tab, on the "Alt. TileServer" field add your own server to download the tiles from.
      - In the Main tab, choose the "Bounding Box (Lat/Lon)" sub-tab and use the "Slippy Map chooser" to choose a rectangle that you want to download the tile from.
      - Choose the zoom level
      - Choose the desired "Outputfolder". The tiles will be downloaded in a folder with the number of the chosen zoom level, located under the directory that you chose in the "Outputfolder"
      - Make sure that the "Outputfolder" is empty.
      - Press the button "Download Tiles"
      - Wait for the tile-download to complete. If you use a zoom level of 11 or more, it might take several thousand tiles to be downloaded as each OSM tile is 256x256px.
      <pre>
         Each zoom level equivalent scale is:
             Level   Degree  Area              m / pixel       ~Scale
             0       360     whole world       156,412         1:500 Mio
             1       180                       78,206          1:250 Mio
             2       90                        39,103          1:150 Mio
             3       45                        19,551          1:70 Mio
             4       22.5                      9,776           1:35 Mio
             5       11.25                     4,888           1:15 Mio
             6       5.625                     2,444           1:10 Mio
             7       2.813                     1,222           1:4 Mio
             8       1.406                     610.984         1:2 Mio
             9       0.703   wide area         305.492         1:1 Mio
             10      0.352                     152.746         1:500,000
             11      0.176   area              76.373          1:250,000
             12      0.088                     38.187          1:150,000
             13      0.044   village or town   19.093          1:70,000
             14      0.022                     9.547           1:35,000
             15      0.011                     4.773           1:15,000
             16      0.005   small road        2.387           1:8,000
             17      0.003                     1.193           1:4,000
             18      0.001                     0.596           1:2,000
             19      0.0005                    0.298           1:1,000
             </pre>
3. Copy this script in the chosen "Outputfolder".
4. Run the script with one command line argument, that of the zoom level 
      - e.g. if you chose to download tiles with zoom 12 and you set the "Outputfolder" in JTileDownloader to be "~/downloaded_tiles", add this script in the directory "~/downloaded_tiles" and execute like this:
      <pre>
                 $ cd ~/downloaded_tiles
                 $ ./stitch-osm-tiles.sh 12
                 </pre>
