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
image is run against Tesseract, using
pytesseract,  to create the base hocr file 
from scratch.

If candidate regions are found and there 
are additions to the hocr file as a result, the 
original will be renamed with a 'bak' extension 
and a new hocr file with the additions will
be created.

Use the '-d' flag to see the process. Some simple
opencv tricks to gather up the missing pieces,
kudos to Tesseract for getting most of what's 
there almost all of the time.

- art rhyno, u. of windsor & ourdigitalworld
"""

import xml.etree.ElementTree as ET
import argparse, glob, math, os, sys
import cv2
import pytesseract
import copy

#namespace for HOCR
HOCR_NS = 'http://www.w3.org/1999/xhtml'
ET.register_namespace('html', HOCR_NS)

""" page_region - a rectangle on the image """
class page_region:
    def __init__(self, x0, y0, x1, y1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

""" word_region - word hocr info """
class word_region:
    def __init__(self, wregion, wident, wtext, wline, wconf):
        self.wregion = wregion
        self.wident = wident
        self.wtext = wtext
        self.wline = wline
        self.wconf = wconf
        self.added = False

""" par - paragraph hocr """
class par_region:
    def __init__(self, phocr, pregion):
        self.phocr = phocr
        self.pregion = pregion

""" avoid passing through divs with no text """
def isTextinDiv(elem):
    words = ''

    for word_elem in elem.iterfind('.//{%s}%s' % (HOCR_NS,'span')):
        class_name = word_elem.attrib['class']
        if class_name == 'ocrx_word':
            words += word_elem.text

    if len(words.strip()) > 0:
        return True

    return False

""" pull coords and sometimes conf from bbox string """
def getBBoxInfo(bbox_str):
    conf = None

    if ';' in bbox_str:
        bbox_info = bbox_str.split(';')
        bbox_info = bbox_info[1].strip()
        bbox_info = bbox_info.split(' ')
        conf = int(bbox_info[1])
    bbox_info = bbox_str.replace(';',' ')
    bbox_info = bbox_info.split(' ')
    x0 = int(bbox_info[1])
    y0 = int(bbox_info[2])
    x1 = int(bbox_info[3])
    y1 = int(bbox_info[4])

    return x0,y0,x1,y1,conf

""" adjust numbers for hocr to reflect additions """
def adjustCounts(element):
    global page_cnt, block_cnt, par_cnt, line_cnt, word_cnt

    for elem in element.iter():
        elem_tag = '%s' % elem.tag
        if elem_tag.startswith("{"):
            elem_tag = elem_tag.split('}', 1)[1]  #strip namespace
        if elem_tag == "div":
            if elem.attrib["class"] == 'ocr_carea':
                elem.set('id','block_%d_%d' % (page_cnt,block_cnt))
                block_cnt += 1
        if elem_tag == "p":
            if elem.attrib["class"] == 'ocr_par':
                elem.set('id','par_%d_%d' % (page_cnt,par_cnt))
                par_cnt += 1
        if elem_tag == "span":
            if elem.attrib["class"] == 'ocr_line':
                elem.set('id','line_%d_%d' % (page_cnt,line_cnt))
                line_cnt += 1
            if elem.attrib["class"] == 'ocrx_word':
                elem.set('id','word_%d_%d' % (page_cnt,word_cnt))
                word_cnt += 1
            
""" look for limits of coord boxes """
def calcBoxLimit(low_x, low_y, high_x, high_y, region):
                
    if low_x == 0 or region.wregion.x0 < low_x:
        low_x = region.wregion.x0
    if low_y == 0 or region.wregion.y0 < low_y:
        low_y = region.wregion.y0
    if high_x == 0 or region.wregion.x1 > high_x:
        high_x = region.wregion.x1
    if low_y == 0 or region.wregion.y1 > low_y:
        high_y = region.wregion.y1

    return low_x, low_y, high_x, high_y

""" create div for entry representing missed regions """
def sortOutDiv(wident,div_element,par_regions,lang):
    global lines

    l_low_x = 0
    l_low_y = 0
    l_high_x = 0
    l_high_y = 0
    p_low_x = 0
    p_low_y = 0
    p_high_x = 0
    p_high_y = 0

    p_element = ET.Element(ET.QName(HOCR_NS,"p"))
    p_element.set('class','ocr_par')
    p_element.set('lang',lang)

    for regions in par_regions:
        wline = ''
        l_element = None

        for region in regions:
            if not region.added and wident==region.wident:
                w_element = ET.Element(ET.QName(HOCR_NS,"span"))
                w_element.set('class','ocrx_word')
                w_element.text = region.wtext
                w_element.set('title','bbox %d %d %d %d; x_wconf %d' %
                    (region.wregion.x0,region.wregion.y0,
                    region.wregion.x1,region.wregion.y1,
                    region.wconf))

                if wline != region.wline:
                    if l_element is not None:
                        p_element.append(l_element)
                        lines += 1

                    l_element = ET.Element(ET.QName(HOCR_NS,"span"))
                    l_element.set('class','ocr_line')
                    l_low_x = 0
                    l_low_y = 0
                    l_high_x = 0
                    l_high_y = 0

                l_low_x, l_low_y, l_high_x, l_high_y = calcBoxLimit(
                    l_low_x, l_low_y, l_high_x, l_high_y, region)
                l_element.append(w_element)
                wline = region.wline
                l_element.set('title','bbox %d %d %d %d; %s' %
                    (l_low_x,l_low_y,l_high_x,l_high_y,wline))
               
                p_low_x, p_low_y, p_high_x, p_high_y = calcBoxLimit(
                    p_low_x, p_low_y, p_high_x, p_high_y, region)
                region.added = True

        if l_element is not None:
            p_element.append(l_element)
            lines += 1
            p_element.set('title','bbox %d %d %d %d' %
                (p_low_x, p_low_y, p_high_x, p_high_y))
            div_element.append(p_element)
            p_element = ET.Element(ET.QName(HOCR_NS,"p"))
            p_element.set('class','ocr_par')
                    
""" add new div and put comments before/after """
def addAndComment(wident,regions,parent_node,lang):

    div_element = ET.Element(ET.QName(HOCR_NS,"div"))
    div_element.set('class','ocr_carea')
    sortOutDiv(wident,div_element,regions,lang)
    adjustCounts(div_element)
    div_comment = ET.Comment(' START HOCRMOD ')
    parent_node.append(div_comment)
    parent_node.append(div_element)
    div_comment = ET.Comment(' END HOCRMOD ')
    parent_node.append(div_comment)

""" try to insert new divs for missed regions based on coordinates """
def sortOutElement(elem, par_regions, parent_node,lang):
    global page_cnt, block_cnt, par_cnt, line_cnt, word_cnt

    x0,y0,x1,y1,_ = getBBoxInfo(elem.attrib['title'])
    for regions in par_regions:
        for region in regions:
            #coordinate placement could be more sophisticated but basic for now
            if x0 > region.wregion.x0 or (x0 == region.wregion.x0 and y0 > region.wregion.y0):
                if not region.added:
                    addAndComment(region.wident,par_regions,parent_node,lang)

""" remove all divs except for parent page """
def stripPage(orig_page):
    parent_node = None

    for elem in orig_page.iter():
        if elem.tag.startswith("{"):
            elem_tag = elem.tag.split('}', 1)[1]  #strip namespace
        if elem_tag == "div":
            if elem.attrib["class"] == 'ocr_page':
                parent_node = elem
                for child in list(elem): #list is needed for this to work
                    elem.remove(child)

    return parent_node

""" sort by coordnates """
def coordSort(k):

    return (k[0].wregion.x0,k[0].wregion.y0,k[0].wregion.x1,k[0].wregion.y1)
        
""" write hocr file, try to keep xml output in line with Tesseract """
def writeModHocr(orig_page,hocr_file):

    with open(hocr_file, 'wb') as f:
        f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n".encode('utf8'))
        f.write("<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.0 Transitional//EN\"\n".encode('utf8'))
        f.write("    \"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd\">\n".encode('utf8'))
        root = orig_page.getroot()
        rstr = ET.tostring(root)
        rstr = rstr.decode('utf8')
        #clean up hocr additions - could use minidom pretty printing but this covers most scenarios
        rstr = rstr.replace('--><','-->\n   <')
        rstr = rstr.replace('\"><html:p','\">\n    <html:p')
        rstr = rstr.replace('><html:span class=\"ocr_line\"',
            '>\n     <html:span class=\"ocr_line\"')
        rstr = rstr.replace('><html:span class=\"ocrx_word\"',
            '>\n      <html:span class=\"ocrx_word\"')
        rstr = rstr.replace('><html:span class=\"ocrx_word\"',
            '>\n      <html:span class=\"ocrx_word\"')
        rstr = rstr.replace('span></html:span',
            'span>\n     </html:span')
        rstr = rstr.replace('span></html:p',
            'span>\n    </html:p')
        rstr = rstr.replace('p></html:div',
            'p>\n   </html:div')
        rstr = rstr.replace('div><html',
            'div>\n   <html')
        rstr = rstr.replace('div><!--',
            'div>\n   <!--')
        #remove blank lines (if any) - these sometimes creep in hocr files for some reason
        rstr = os.linesep.join([s for s in rstr.splitlines() if s])
        f.write(rstr.encode('utf8'))

""" these are the paragraph regions coming from missed regions """
def runThruPars(img_base,pars,orig_page,conf,lang):
    global page_cnt, block_cnt, par_cnt, line_cnt, word_cnt

    par_regions = []
    for par in pars:
        regions = sortOutHocr(str(len(par_regions)),par.phocr,par.pregion,conf)
        if (len(regions) > 0):
            par_regions.append(regions)

    par_regions.sort(key=coordSort)

    #make a copy - this will be used for stepping through existing divs
    ref_copy = copy.deepcopy(orig_page)
    parent_node = stripPage(orig_page)

    for elem in ref_copy.iterfind('.//{%s}%s' % (HOCR_NS,'div')):
        #weed out empty divs
        if isTextinDiv(elem):
            class_name = elem.attrib['class']
            if class_name == 'ocr_carea':
                sortOutElement(elem, par_regions, parent_node,lang)
                adjustCounts(elem)
                parent_node.append(elem)

    #add anything that's left at the end of page div
    for regions in par_regions:
        for region in regions:
            if not region.added:
                addAndComment(region.wident,par_regions,parent_node,lang)

    if len(par_regions) > 0:
        if os.path.exists(img_base + '.hocr'):
            os.rename(img_base + '.hocr', img_base + '.hocr.bak')
        writeModHocr(orig_page,img_base + '.hocr')

""" pull together paragraphs from hocr file """
def sortOutHocr(HOCRfile,HOCRimg,HOCRregion,HOCRconf):
    img_regions = []

    if HOCRimg is None:
        tree = ET.ElementTree(file=HOCRfile)
    else:
        tree = ET.ElementTree(ET.fromstring(HOCRimg))

    for elem in tree.iterfind('.//{%s}%s' % (HOCR_NS,'p')):
        line_info = None
        if 'class' in elem.attrib:
            class_name = elem.attrib['class']
            if class_name == 'ocr_par': 
                words = ''
                for word_elem in elem.iterfind('.//{%s}%s' % (HOCR_NS,'span')):
                    class_name = word_elem.attrib['class']
                    if class_name == 'ocr_line': #save line infos
                        line_info = word_elem.attrib['title']
                        line_index = line_info.find(';')
                        line_info = line_info[line_index + 1:]
                    if class_name == 'ocrx_word': #word details
                        word_text = word_elem.text.strip()
                        if HOCRimg is not None and len(word_text) > 0:
                            x0,y0,x1,y1,conf = getBBoxInfo(
                                word_elem.attrib['title'])
                            if conf >= HOCRconf:
                                img_regions.append(
                                    word_region(page_region(HOCRregion.x0+x0,
                                    HOCRregion.y0+y0,HOCRregion.x0+x1,
                                    HOCRregion.y0+y1),
                                    HOCRfile + '_' + elem.attrib['id'],
                                    word_text,line_info,conf))
                        words += word_text
                #skip para blocks that don't have any text
                if len(words.strip()) > 0 and HOCRimg is None:
                    print(".",end="",flush=True)
                    x0,y0,x1,y1,_ = getBBoxInfo(elem.attrib['title'])
                    img_regions.append(page_region(x0,y0,x1,y1))

    return img_regions

""" use paragraph coords to remove already recognized sections """
def runThruHocr(ifile,ibase,iborder,debug):

    print("sort through hocr paragraphs...",end="",flush=True)
    pg_regions = sortOutHocr(ibase + '.hocr',None,None,None)
    print("!") #hocr processing is done

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
        #write out blocked image for troubleshooting
        cv2.imwrite(ibase +'_regions.jpg', im)

    return im

""" weed out horizontal or vertical line """
def getSLine(roi,iborder):

    #Tesseract (rightfully) ignores separator lines for the most part,
    #which means they can be legion afterwards, try to blank them out
    #rather than completely removing since they might be part of extrude
    #into missing text

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
def runThruContours(ibase,im,debug,tess_args,iborder,lang):
    pars = []
 
    print("look for missed text blocks...",end="",flush=True)
    img = im.copy()
    #convert the image to gray scale
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    print(".",end="",flush=True)

    #get image ready for detecting text clusters
    bin = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
        cv2.THRESH_BINARY_INV, 3, 9)
    bin = cv2.medianBlur(bin, 3)
    print(".",end="",flush=True)

    #use a fairly large kernel to try to keep sentences together
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
    bin = cv2.dilate(bin, kernel, iterations=2)
    bin = cv2.GaussianBlur(bin, (45,45),0)
    print(".",end="",flush=True)

    ret, bin = cv2.threshold(bin, 0,255, cv2.THRESH_BINARY)       
    contours, _ = cv2.findContours( bin, cv2.RETR_CCOMP, 
        cv2.CHAIN_APPROX_SIMPLE)
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
        ret,th = cv2.threshold(cg,0,255,
            cv2.THRESH_BINARY+cv2.THRESH_TRIANGLE)
        #only consider regions with significant white space
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

           cv2.imwrite(roi_name + '.png', roi)
           missed_par = pytesseract.image_to_pdf_or_hocr(
               roi_name + '.png', 
               config = ("-l %s %s" % (lang,tess_args)),
               extension='hocr')
           pars.append(par_region(missed_par,page_region(x,y,x+w,y+h)))

           writeHocr(missed_par,roi_name + ".hocr")
           if not debug:
               os.remove(roi_name + ".hocr")
               os.remove(roi_name + ".png")
            
           if debug:
               #mark region on original image
               cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

           cand_cnt += 1

    print("!")
    #write out image with contour(s) for troubleshooting
    if debug:
        cv2.imwrite(ibase + '_contours.jpg', img)

    return cand_cnt, pars

def writeHocr(block,fhocr):

    hfile = open(fhocr, "w+b")
    hfile.write(bytearray(block))
    hfile.close()

parser = argparse.ArgumentParser()
arg_named = parser.add_argument_group("named arguments")
arg_named.add_argument("-f","--file", 
    help="input image, for example: imgs/my_image.tif")
arg_named.add_argument("-b","--border", default=10, type=int,
    help="adjust border value for extracted regions")
arg_named.add_argument('-a', '--arguments', type=str, 
    default="--psm 6",
    help="arguments for tesseract on missing regions")
arg_named.add_argument("-d","--debug", default=False, 
    action="store_true",
    help="create debug files")
arg_named.add_argument("-c","--conf", default=75, type=int,
    help="set confidence number threshold for mised regions")
arg_named.add_argument('-l', '--lang', type=str, 
    default="eng",
    help="language for OCR")

args = parser.parse_args()

if args.file == None or not os.path.exists(args.file):
    print("missing input image, use '-h' parameter for syntax")
    sys.exit()

#use filename to pull everything together
img_base = args.file.split(".")[0]

orig_page = None
if not os.path.exists(img_base + ".hocr"):
    print("missing base hocr file: %s.hocr, running Tesseract" % img_base)
    orig_page = pytesseract.image_to_pdf_or_hocr(args.file,
        config=("-l %s" % args.lang),
        extension='hocr')
    #always want a copy of original
    writeHocr(orig_page,img_base + ".hocr")

img = runThruHocr(args.file,img_base,
    args.border,args.debug)
extras, pars = runThruContours(img_base,img,args.debug,
    args.arguments,args.border,args.lang)

lines = 0
if extras > 0: 
    orig_page = ET.parse(img_base + ".hocr")

    #hocr numbering starts at 1
    page_cnt = 1
    block_cnt = 1
    par_cnt = 1
    line_cnt = 1
    word_cnt = 1

    runThruPars(img_base,pars,orig_page,args.conf,args.lang)

print("hocr line(s) added: %d" % lines)
