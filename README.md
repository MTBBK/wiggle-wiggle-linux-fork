# Original Project
`https://github.com/JCLemme/wiggle-wiggle`
Modified for support systems other than MacOS and fixed really large sized gif file problem.

# wiggle-wiggle
find and extract wiggle stereographs from your photos

### What is that?

![like this](/media/example.gif)

This script goes through a bunch of pictures, computes a set of perceptual hashes on them, then uses them to try and find runs of images that might be stereo wigglegrams.

It's a little overbuilt in some places and underbuilt in others. Please give it a try and report back.


### Usage

Make a venv, install the requirements, etc.

Pass `-d <directory>` to point it at a folder full of pictures.

Run `hash` to calculate hashes for the images. It'll save a database file so you can rerun this when you take more pictures.

Then you can run `export` to see the wigglegrams.

```
./wigglewiggle.py -d home/photos hash      # hash your photos
./wigglewiggle.py -d home/photos export    # build gifs
./wigglewiggle.py -d home/photos export -s 1200 # build gifs with width 1200
```
