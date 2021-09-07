hocrmod
=======

This project attempts to address an edge case with [Tesseract](https://github.com/tesseract-ocr/tesseract) where small
regions are missed for recognition, and uses Tesseract's support of [hocr](https://en.wikipedia.org/wiki/HOCR) to merge 
the OCR from missing regions. This seems to most often occur with page numbers, for example, as seen for page _14_ in the 
example below:

<img src="https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/mj0029.jpg?raw=true" width="30%" height="30%">

There is an [open issue](https://github.com/tesseract-ocr/tesseract/issues/3446) on this sort of scenario and
it may be sorted out within the core program.  The main program here, _hocrmod.py_, is a simple python script that uses some
[OpenCV](https://opencv.org/) tricks to detect missing regions and has several options:

```
usage: hocrmod.py [-h] [-f FILE] [-b BORDER] [-a ARGUMENTS] [-d]

optional arguments:
  -h, --help            show this help message and exit

named arguments:
  -f FILE, --file FILE  input image, for example: imgs/my_image.tif
  -b BORDER, --border BORDER
                        adjust border value for extracted regions
  -a ARGUMENTS, --arguments ARGUMENTS
                        arguments for tesseract on missing regions
  -d, --debug           create debug files
```

The easiest way to see what's happening with this approach is to run the script with the _-d_ option. For example:

```
python -f mj0029.jpg -d
```

The script will look for a corresponding _hocr_ file with the same path as the image. If one is not found, then
Tesseract will be run on the image. To use a slightly more ambitious image from the kind folks at the
[Internet Archive](https://archive.org/), consider this image:

<img src="https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/sim5.jpg?raw=true" width="30%" height="30%">

Tesseract does an amazing job on most of this image. With the _-d_ option, we can look in the _regions_ image
to inspect what's left afterwards. The script uses the base _hocr_ file (which provides coordinates), to blank out 
regions that have been identified by Tesseract, leaving the following:

<img src="https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/sim5_regions.jpg?raw=true" width="30%" height="30%">

Again, Tesseract does an amazing job, there really isn't much left here. But, in this case, we want what's left, particularly
the page number. Tesseract also, rightfully, ignores the _separator_ lines. These are usually stylistic and 
are not appropriate for OCR. However, the script tries to use _OpenCV_ to identify these and blank them out rather
than skipping the regions altogether. This is because of situations like the following:

<img src="https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/sim5_ex.jpg?raw=true" width="50%" height="50%">

Here the line overlaps with a textual area. The line identification is not infallible, but the associated
_contours_ image will show what regions will be subject to OCR:

<img src="https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/sim5_contours.jpg?raw=true" width="30%" height="30%">

The script doesn't use [pytesseract](https://pypi.org/project/pytesseract/) and the parameters can be overridden for
the Tesseract executable. In most cases, the results will not be of much interest, but the main concern is usually
to get the line number, which may be picked up by this approach:

<img src="https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/sim5_coords_00169_02971_00334_03082.png?raw=true" width="50%" height="50%">

With the _-d_ option, the resulting _hocr_ files will have the coordinates of the regions in the file name, e.g.
_sim5_coords_00169_02971_00334_03082.png_, but otherwise these files will be created and removed as needed. The
original _hocr_ file will be renamed with a _.bak_ extension, unless no text is produced with the script, in
which case the original _hocr_ file will be untouched.

The merging of the _hocr_ files is simplistic, and there are probably existing utilities for this. Our use case
(ETDs and Major Papers) really does not lean much on the _hocr_ files but the script is hopefully enough
to give some ideas on how to incorporate an _OpenCV_ step into an existing workflow if there are regions
that are being missed for OCR that are of interest.

Thanks, as always, to the Internet Archive for all of the great work they do,
and to my colleagues at [OurDigitalWorld](https://ourdigitalworld.net/) as well as the 
[Centre for Digital Scholarship](https://cdigs.uwindsor.ca/) for supporting
and encouraging these kinds of projects to help digitize analogue collections.

art rhyno [ourdigitalworld/cdigs](https://github.com/artunit)
