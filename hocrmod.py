"""
hocrmod.py - try to add missed regions after OCR

Usage (see list of options):
    hocrmod.py [-h] 

For example:
    hocrmod.py -f sim1.jpg
    hocrmod.py -f sim1.jpg -d

Assumes that hocr file has the same base name,
e.g. sim1.hocr and is located in the same
directory as the image. If not found, the
image is run against Tesseract to create
the base hocr file from scratch.

If candidate regions are found and there 
are additions to the hocr file as a result, the 
original will be renamed with a 'bak' extension 
and a new hocr file with the additions will
be created.

The method for modifying the original hocr file is
incredibly basic, but will hopefully align
the coordinates properly. 

Use the '-d' flag to see the process. Some simple
opencv tricks to gather up the missing pieces,
kudos to Tesseract for getting most of what's 
there almost all of the time.

- art rhyno, u. of windsor & ourdigitalworld
"""

import xml.etree.ElementTree as ET
import argparse, glob, math, os, sys
import cv2
from subprocess import call

#executable for Tesseract
TESSERACT_EXE = "/usr/local/bin/tesseract"
#namespace for HOCR
HOCR_NS = 'http://www.w3.org/1999/xhtml'

""" page_region - a rectangle on the image """
class page_region:
    def __init__(self, x0, y0, x1, y1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

""" write out modified hocr with adjusted coordinates """
def sortOutLine(line,x0,y0):
    global block_cnt, par_cnt, line_cnt, word_cnt
    hline = line.split("id=",1)
    if len(hline) == 1:
        return line
    bline = hline[1].split("bbox",1)
    nline = ""

    if "class=\'ocr_carea\'" in line:
        block_cnt += 1
        prefix = line.split( "class=\'ocr_carea\'")
        nline = "%sclass=\'ocr_carea\' id=\'block_1_%d\' " % (prefix[0],block_cnt)
        nline += "title=\"bbox"
    elif "class=\'ocr_par\'" in line:
        par_cnt += 1
        prefix = line.split("class=\'ocr_par\'")
        nline = "%sclass=\'ocr_par\' id=\'par_1_%d\' " % (prefix[0],par_cnt)
        nline += "title=\"bbox"
    elif "class=\'ocr_line\'" in line:
        line_cnt += 1
        prefix = line.split("class=\'ocr_line\'")
        nline = "%sclass=\'ocr_line\' id=\'line_1_%d\' " % (prefix[0],line_cnt)
        nline += "title=\"bbox"
    elif "class=\'ocr_caption\'" in line:
        line_cnt += 1
        prefix = line.split("class=\'ocr_caption\'")
        nline = "%sclass=\'ocr_caption\' id=\'line_1_%d\' " % (prefix[0],line_cnt)
        nline += "title=\"bbox"
    elif "class=\'ocr_textfloat\'" in line:
        line_cnt += 1
        prefix = line.split("class=\'ocr_textfloat\'")
        nline = "%sclass=\'ocr_textfloat\' id=\'line_1_%d\' " % (prefix[0],line_cnt)
        nline += "title=\"bbox"
    elif "class=\'ocrx_word\'" in line:
        word_cnt += 1
        prefix = line.split("class=\'ocrx_word\'")
        nline = "%sclass=\'ocrx_word\' id=\'word_1_%d\' " % (prefix[0],word_cnt)
        nline += "title=\'bbox"

    #adjust coordinates for missed regions
    if x0 > 0 or y0 > 0:
        coords = bline[1].strip().split(" ")
        if len(coords) >= 4:
            #last coordinate can pick up cruft
            num_filter = filter(str.isdigit,coords[3])
            coords[3] = "".join(num_filter)
            orig_coords = "%s %s %s %s" % (coords[0],coords[1],coords[2],coords[3])
            adj_coords = "%d %d %d %d" % (int(coords[0]) + x0,
                int(coords[1]) + y0, int(coords[2]) + x0,
                int(coords[3]) + y0)
            bline[1] = bline[1].replace(orig_coords,adj_coords)
        
    if len(bline) == 1:
        return line
    nline += bline[1]
    return nline

""" pull together results from hocr files """
def runThruResults(HOCRbase,ifile,w,h,debug,lregion):
    x0 = 0
    y0 = 0

    lines_added = 0
    started = False
    section = False

    hocrfiles = sorted(glob.glob(HOCRbase + "*.hocr"))
    if len(hocrfiles) == 1:
        return lines_added

    region_str = HOCRbase + "_coords_"
    hout = open(HOCRbase + "_new.hocr","w")

    for hocrfile in hocrfiles:
        if region_str in hocrfile:
           bbox_str = hocrfile.replace(region_str,"")
           bbox_str = bbox_str.replace(".hocr","")
           bbox_info = bbox_str.split('_')
           x0 = int(bbox_info[0])
           y0 = int(bbox_info[1])

        with open(hocrfile) as fp:
             line = fp.readline()
             while line: 
                 if not started:
                     hout.write(line)
                     if "<body>" in line: 
                         started = True
                         hout.write(" <div class=\'ocr_page\' id='page_1' ")
                         hout.write("title=\'image \"%s\"; bbox 0 0 " % ifile)
                         hout.write("%d %d; ppageno 0\'>\n" % (w,h))
                 if not "class=\'ocr_page" in line and "bbox " in line:
                     if "class=\'ocr_header" in line:
                         line = line.replace("class=\'ocr_header","class=\'ocr_line")
                     hout_line = sortOutLine(line,x0,y0)
                     hout.write(hout_line)
                     if (x0 > 0 or y0 > 0) and len(hout_line) > 0:
                         lines_added += 1
                     section = True
                 if section and "</div>" in line:
                     hout.write(line)
                     section = False
                 if section and (line.lstrip().startswith("</span>") or line.lstrip().startswith("</p>")):
                     hout.write(line)
                 line = fp.readline()

        if not debug and region_str in hocrfile:
            os.remove(hocrfile)
        fp.close()

    if lines_added > 0:
        hout.write(" </div>\n </body>\n</html>")
        hout.close()
        os.rename(HOCRbase + ".hocr", HOCRbase + ".hocr.bak")
        os.rename(HOCRbase + "_new.hocr",HOCRbase + ".hocr")
    else:
        #no point in keeping this if nothing added
        hout.close()
        os.remove(HOCRbase + "_new.hocr")

    return lines_added

""" pull together paragraphs from hocr file """
def sortOutHocr(HOCRfile):
    print("sort through hocr paragraphs...",end="",flush=True)
    img_regions = []
    tree = ET.ElementTree(file=HOCRfile)
    for elem in tree.iterfind('.//{%s}%s' % (HOCR_NS,'p')):
        if 'class' in elem.attrib:
           class_name = elem.attrib['class']
           if class_name == 'ocr_par': 
               words = ""
               for word_elem in elem.iterfind('.//{%s}%s' % (HOCR_NS,'span')):
                   class_name = word_elem.attrib['class']
                   if class_name == 'ocrx_word': 
                       words += word_elem.text
               #skip para blocks that don't have any text
               if len(words.strip()) > 0:
                   print(".",end="",flush=True)
                   bbox_info = elem.attrib['title']
                   bbox_info = bbox_info.replace(';',' ')
                   bbox_info = bbox_info.split(' ')
                   x0 = int(bbox_info[1])
                   y0 = int(bbox_info[2])
                   x1 = int(bbox_info[3])
                   y1 = int(bbox_info[4])

                   img_regions.append(page_region(x0,y0,x1,y1))

    print("!")
    return img_regions

""" use paragraph coords to remove already recognized sections """
def runThruHocr(ifile,ibase,iborder,debug):
    lregion = ""
    pg_regions = sortOutHocr(ibase + '.hocr')

    im = cv2.imread(ifile)
    print("block out recognized text...",end="",flush=True)
    for i,region in enumerate(pg_regions):
        print(".",end="",flush=True)
        x0 = region.x0 - iborder
        y0 = region.y0 - iborder
        x1 = region.x1 + iborder
        y1 = region.y1 + iborder
        w = region.x1 - region.x0
        h = region.y1 - region.y0

        if w > 0 and h > 0:
            cv2.rectangle(im, (x0,y0), (x1,y1), (255,255,255), -1)

    print("!")
    if debug:
        print("creating " + ibase +'_regions.jpg')
        #write out blocked image for troubleshooting
        cv2.imwrite(ibase +'_regions.jpg', im)
    return im, lregion

""" weed out horizontal or vertical line """
def getSLine(roi,iborder):
    #Tesseract (rightfully) ignores separator lines for the most part,
    #which means they can be legion afterwards, try to blank them out
    #rather than completely removing since they might be part of some
    #missing text

    dst = cv2.Canny(roi, 50, 200, None, 3)
    #use explicit parameters - see https://stackoverflow.com/questions/35609719/opencv-houghlinesp-parameters
    slines = cv2.HoughLinesP(dst, rho = 1, theta = math.pi / 180,
        threshold = 200, minLineLength=200, maxLineGap=50)

    if slines is None:
        return []

    x0 = 0
    y0 = 0
    x1 = 0
    y1 = 0

    for i in range(0, len(slines)):
        coords = slines[i][0]
        if coords[0] < x0 or x0 == 0:
            x0 = coords[0]
        if coords[1] < y0 or y0 == 0:
            y0 = coords[1]
        if coords[2] > x1 or x1 == 0:
            x1 = coords[2]
        if coords[3] > y1 or y1 == 0:
            y1 = coords[3]
   
    #add some extra space to region to create border (helps recognition)
    if x0 > iborder:
        x0 -= iborder
    if y0 > iborder:
        y0 -= iborder
    return [x0,y0,x1 + iborder,y1 + iborder]

""" extract remaining candidate text blocks """
def runThruContours(ibase,im,debug,tess_args,iborder):
    print("look for missed text blocks...",end="",flush=True)
    img = im.copy()
    #convert the image to gray scale
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    print(".",end="",flush=True)

    #get image ready for detecting text clusters
    bin = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 3, 9)
    bin = cv2.medianBlur(bin, 3)
    print(".",end="",flush=True)

    #use a fairly large kernel to try to keep sentences together
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
    bin = cv2.dilate(bin, kernel, iterations=2)
    bin = cv2.GaussianBlur(bin, (45,45),0)
    print(".",end="",flush=True)

    ret, bin = cv2.threshold(bin, 0,255, cv2.THRESH_BINARY)       
    contours, _ = cv2.findContours( bin, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    print("!")

    print("work through contours...",end="",flush=True)
    cand_cnt = 0
    for cnt in contours:
        print(".",end="",flush=True)
        x, y, w, h = cv2.boundingRect(cnt)
        print(".",end="",flush=True)
        roi = img[y:y + h, x:x + w]
        cg = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        #use threshold to push gradiants to black and white
        ret,th = cv2.threshold(cg,0,255,cv2.THRESH_BINARY+cv2.THRESH_TRIANGLE)
        #often lots of false positives, only consider regions with significant white space
        percent_w = round((cv2.countNonZero(th)/cg.size) * 100,1)

        #use coordinates for file name
        roi_name = "%s_coords_%05d_%05d_%05d_%05d" % (ibase,x,y,x+w,y+h)

        #specify high percentage of white space (70% or higher) for candidate region
        if percent_w > 70.0:
           seps = getSLine(roi,iborder)
           if len(seps) > 0:
               #blank out separator line, Tesseract (rightfully) ignores these
               cv2.rectangle(roi, (seps[0],seps[1]), 
                   (seps[2],seps[3]), 
                   (255,255,255), -1)

           cv2.imwrite(roi_name + ".png", roi)
           cmd_line = "%s %s %s %s" % (TESSERACT_EXE,
               roi_name + ".png", roi_name, tess_args)
           return_code = call(cmd_line, shell=True)

           if return_code != 0:
               print("error executing comamand:", cmd_line)

           if os.path.exists(roi_name + ".png") and not debug:
               os.remove(roi_name + ".png")
            
           if debug:
               #mark region on original image
               cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

           cand_cnt += 1

    print("!")
    #write out image with contour(s) for troubleshooting
    if debug:
        cv2.imwrite(ibase + '_contours.jpg', img)
    return cand_cnt

parser = argparse.ArgumentParser()
arg_named = parser.add_argument_group("named arguments")
arg_named.add_argument("-f","--file", 
    help="input image, for example: imgs/my_image.tif")
arg_named.add_argument("-b","--border", default=10, type=int,
    help="adjust border value for extracted regions")
arg_named.add_argument('-a', '--arguments', type=str, 
    default="-l eng --psm 6 -c tessedit_create_hocr=1 1>/dev/null 2>&1",
    help="arguments for tesseract on missing regions")
arg_named.add_argument("-d","--debug", default=False, 
    action="store_true",
    help="create debug files")

args = parser.parse_args()

if args.file == None or not os.path.exists(args.file):
    print("missing input image, use '-h' parameter for syntax")
    sys.exit()

#use filename to pull everything together
img_base = args.file.split(".")[0]

if not os.path.exists(img_base + ".hocr"):
    print("missing base hocr file: %s.hocr, running Tesseract" % img_base)
    cmd_line = "%s %s %s hocr" % (TESSERACT_EXE,args.file,img_base)
    return_code = call(cmd_line, shell=True)
    if return_code != 0:
        print("error executing comamand:", cmd_line)
        sys.exit()

img,lregion = runThruHocr(args.file,img_base,
    args.border,args.debug)
extras = runThruContours(img_base,img,args.debug,
    args.arguments,args.border)
lines = 0
if extras > 0:
    bimg = cv2.imread(args.file,0)
    h, w = bimg.shape[:2]
    block_cnt = 0 
    par_cnt = 0 
    line_cnt = 0 
    word_cnt = 0
    lines = runThruResults(img_base,args.file,w,h,args.debug,lregion)

print("extra regions: %d" % extras)
print("hocr line(s) added: %d" % lines)
