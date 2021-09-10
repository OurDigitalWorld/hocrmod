hocrmod
=======

_TO DO: I have been asked to make some fundamental changes to the script here. Just a note that I will
be updating the approach in the next week or so (2021-09-10) to include a confidence threshold (to remove
questionable regions in the "missed" category), and address a reading-order/paragraph layout request.
Still, the basic OpenCV/image steps will remain the same._

This project attempts to address an edge case with [Tesseract](https://github.com/tesseract-ocr/tesseract) where small
regions are missed for recognition, and uses Tesseract's support of [hocr](https://en.wikipedia.org/wiki/HOCR) to merge 
the OCR from missing regions. This seems to most often occur with page numbers, for example, as seen for page _14_ in the 
example below:

<img src="https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/mj0029.jpg?raw=true" width="30%" height="30%">

There is an [open issue](https://github.com/tesseract-ocr/tesseract/issues/3446) on this sort of scenario and
it may be sorted out within the _Tesseract_ itself.  The main program here, _hocrmod.py_, is a simple python script that uses some
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
[Internet Archive](https://archive.org/), consider this:

<img src="https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/sim5.jpg?raw=true" width="30%" height="30%">

_Tesseract_ does an amazing job on most of this image. With the _-d_ option, we can look in the _regions_ image
to inspect what's left afterwards. The script uses the base _hocr_ file (which provides coordinates), to blank out 
regions that have been identified by _Tesseract_, leaving the following:

<img src="https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/sim5_regions.jpg?raw=true" width="30%" height="30%">

Again, _Tesseract_ does a lot of good things here, there really isn't much left. But, in this case, 
the small regions cover some important semantic content, particularly
the page number. _Tesseract_ also, rightfully, ignores the _separator_ lines. These are usually stylistic and 
are not appropriate for OCR. However, the script tries to use _OpenCV_ to identify these and blank them out rather
than skipping regions with separators altogether. This is because of situations like the following:

<img src="https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/sim5_ex.jpg?raw=true" width="50%" height="50%">

Here the line overlaps with a textual area. The line identification is not infallible, and there will often be
questionable regions in the mix, but the associated
_contours_ image will show what regions will be subject to OCR with this approach:

<img src="https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/sim5_contours.jpg?raw=true" width="30%" height="30%">

The script doesn't currently use [pytesseract](https://pypi.org/project/pytesseract/) and the parameters 
can be overridden for the Tesseract executable. It might make sense to add a check for the confidence number, since
bogus regions would be easy to identify, or add some kind of check to limit the additions to the following, i.e., 
the elusive page number:

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
