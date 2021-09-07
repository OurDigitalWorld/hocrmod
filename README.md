hocrmod
=======

This project attempts to address an edge case with [Tesseract](https://github.com/tesseract-ocr/tesseract) where small
regions are missed for recognition. This seems to occur with page numbers, for example, as seen for page _14_ in the example
below:

![Sample page with missed region](https://github.com/OurDigitalWorld/hocrmod/blob/main/misc/mj0029.jpg?raw=true)

There is an [open issue](https://github.com/tesseract-ocr/tesseract/issues/3446) on this sort of scenario and
it may be sorted out within the core program.  The main program here, _hocrmod.py_, is a simple python script that uses some
simple [OpenCV](https://opencv.org/) tricks to detect missing regions and has several options:

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
