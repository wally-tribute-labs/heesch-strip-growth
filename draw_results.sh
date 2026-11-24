#!/bin/sh
# Run in the experiment directory with the pinned verifier on PYTHONPATH.
set -eu
for pair in "periodic-four periodic-four" "two-ring-finite finite-two" \
            "six-copy-periodic six-copy-periodic" "row63-finite row63-finite"
do
    input=${pair% *}
    output=${pair#* }
    python3 render_witness.py "$input.heesch" "$output.svg"
    rsvg-convert -w 900 -h 720 -o "$output.png" "$output.svg"
done
# Each panel is fitted independently so the outlines of individual tiles stay legible.
font=${FIGURE_FONT:-/System/Library/Fonts/Helvetica.ttc}
magick \
    \( six-copy-periodic.png -resize 720x576 -background '#fbfaf6' -gravity north -splice 0x64 \
       -font "$font" -pointsize 27 -fill '#21303a' -annotate +0+20 'Four rings · tiles the plane' \) \
    \( row63-finite.png -resize 720x576 -background '#fbfaf6' -gravity north -splice 0x64 \
       -font "$font" -pointsize 27 -fill '#21303a' -annotate +0+20 'Two rings · finite' \) \
    +append results.png
