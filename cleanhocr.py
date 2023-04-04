"""
cleanhocr.py - weed out OCR results

Usage (see list of options):
    cleanhocr.py [-h] 

For example:
    cleanhocr.py -f file

This rebuilds the HOCR file based
on confidence threshold (per word) and
a possible exception for numbers.

- art rhyno, u. of windsor & ourdigitalworld
"""

import xml.etree.ElementTree as ET
import argparse, glob, math, os, sys, time
from xml.dom import minidom
from subprocess import call

#namespace for HOCR
HOCR_NS = 'http://www.w3.org/1999/xhtml'

#set paths for cat and lynx
#this part is commented out below
#but might be useful for quickly checking
#a text version of the results
"""
CAT_CMD = "/bin/cat"
LYNX_CMD = "/usr/bin/lynx"
"""

""" page_region - a rectangle on the image """
class page_region:
    def __init__(self, x0, y0, x1, y1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

""" word_region - word hocr info """
class word_region:
    def __init__(self, wregion, pident, dident, wtext, wline, wconf):
        self.wregion = wregion
        self.pident = pident
        self.dident = dident
        self.wtext = wtext
        self.wline = wline
        self.wconf = wconf

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

""" look for limits of coord boxes """
def calcBoxLimit(low_x, low_y, high_x, high_y, region):
                
    if low_x == 0 or region.wregion.x0 < low_x:
        low_x = region.wregion.x0
    if low_y == 0 or region.wregion.y0 < low_y:
        low_y = region.wregion.y0
    if high_x == 0 or region.wregion.x1 > high_x:
        high_x = region.wregion.x1
    if high_y == 0 or region.wregion.y1 > high_y:
        high_y = region.wregion.y1

    return low_x, low_y, high_x, high_y

""" remove all divs except for ocr_page parent """
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

""" write hocr file """
def writeModHocr(new_node,hocr_file):

    #use minidom pretty print feature
    xmlstr = minidom.parseString(ET.tostring(new_node)).toprettyxml(indent="   ")
    with open(hocr_file, 'w') as f:
        f.write(xmlstr)
    f.close()

""" add headers for HOCR """
def addHtmlHeaders(result_title):
    html_node = ET.Element(ET.QName(HOCR_NS,"html"))
    head_element = ET.Element(ET.QName(HOCR_NS,"head"))
    title_element = ET.Element(ET.QName(HOCR_NS,"title"))
    title_element.text = result_title
    head_element.append(title_element)
    html_node.append(head_element)

    return html_node

""" add divs for paragraphs """
def runThruPars(img_hocr,par_regions,orig_page,conf,lang,result_title):
    global file_cnt, page_cnt, block_cnt, par_cnt, line_cnt, word_cnt

    orig_node = stripPage(orig_page)
    parent_node = addHtmlHeaders(result_title)
    body_node = ET.Element(ET.QName(HOCR_NS,"body"))

    l_low_x = 0
    l_low_y = 0
    l_high_x = 0
    l_high_y = 0

    p_low_x = 0
    p_low_y = 0
    p_high_x = 0
    p_high_y = 0

    div_element = ET.Element(ET.QName(HOCR_NS,"div"))
    div_element.set('class','ocr_carea')
    div_element.set('id','block_1_%d' % block_cnt)

    p_element = ET.Element(ET.QName(HOCR_NS,"p"))
    p_element.set('class','ocr_par')
    p_element.set('lang',lang)
    p_element.set('id','par_1_%d' % par_cnt)

    wline = ''
    wpar = ''
    wdiv = ''
    l_element = None

    num_pars = len(par_regions) - 1
    par_filled = False
    div_filled = False

    #words in paras
    for cnt, region in enumerate(par_regions):

        w_element = ET.Element(ET.QName(HOCR_NS,"span"))
        w_element.set('class','ocrx_word')

        w_element.text = region.wtext
        w_element.set('title','bbox %d %d %d %d; x_wconf %d' %
            (region.wregion.x0,region.wregion.y0,
            region.wregion.x1,region.wregion.y1,
            region.wconf))
        w_element.set('id','word_1_%d' % word_cnt)
        word_cnt += 1

        if wline != region.wline:
            if l_element is not None:
                l_element.set('title','bbox %d %d %d %d; %s' %
                    (l_low_x,l_low_y,l_high_x,l_high_y,wline))
                l_element.set('id','line_1_%d' % line_cnt)
                line_cnt += 1
                p_element.append(l_element)
                par_filled = True

            l_element = ET.Element(ET.QName(HOCR_NS,"span"))
            l_element.set('class','ocr_line')
            l_low_x = 0
            l_low_y = 0
            l_high_x = 0
            l_high_y = 0

        l_low_x, l_low_y, l_high_x, l_high_y = calcBoxLimit(
            l_low_x, l_low_y, l_high_x, l_high_y, region)

        if l_element is not None:
            l_element.append(w_element)
            wline = region.wline

            if (wpar != region.pident or cnt == num_pars) and len(wpar) > 0:
                p_element.set('title','bbox %d %d %d %d' %
                    (p_low_x, p_low_y, p_high_x, p_high_y))
                p_element.set('id','par_1_%d' % par_cnt)
                par_cnt += 1
                if cnt == num_pars:
                    if (l_low_x + l_low_y + l_high_x + l_high_y) > 0:
                        l_element.set('title','bbox %d %d %d %d; %s' %
                            (l_low_x,l_low_y,l_high_x,l_high_y,wline))
                        l_element.set('id','line_1_%d' % line_cnt)
                    p_element.append(l_element)
                    par_filled = True
                
                if par_filled:
                    div_element.append(p_element)
                    par_filled = False
                    div_filled = True
     
                if cnt != num_pars and not par_filled: 
                    p_element = ET.Element(ET.QName(HOCR_NS,"p"))
                    p_element.set('class','ocr_par')
                    p_element.set('lang',lang)
                    p_low_x = 0
                    p_low_y = 0
                    p_high_x = 0
                    p_high_y = 0

            p_low_x, p_low_y, p_high_x, p_high_y = calcBoxLimit(
                p_low_x, p_low_y, p_high_x, p_high_y, region)

            if (wdiv != region.dident or cnt == num_pars) and len(wdiv) > 0:
                div_element.set('id','block_1_%d' % block_cnt)
                block_cnt += 1
                if div_filled:
                    orig_node.append(div_element)
                    div_filled = False
                    if cnt != num_pars:
                        div_element = ET.Element(ET.QName(HOCR_NS,"div"))
                        div_element.set('class','ocr_carea')

            wpar = region.pident
            wdiv = region.dident

    if len(par_regions) > 0:
        body_node.append(orig_node)
        parent_node.append(body_node)
        writeModHocr(parent_node, img_base + '_odw.hocr')
        #convenience code, this would be one way to get a text version of the results
        """
        if os.path.exists(img_base + '_odw.hocr'):
             cmd_line = "%s %s | %s -stdin --dump > %s_odw.txt" % (CAT_CMD,img_hocr,LYNX_CMD,img_base)
             print("cmd: ", cmd_line)
             call(cmd_line, shell=True)
        """

""" check for any numbers in string """
def hasNumbers(inputString):
    return any(char.isdigit() for char in inputString)

""" pull together paragraphs from hocr file """
def sortOutHocr(tree,HOCRfile,HOCRconf,number,pars):

    #keep words together in paragraphs identified by tesseract
    for div_elem in tree.iterfind('.//{%s}%s' % (HOCR_NS,'div')):
        if 'class' in div_elem.attrib:
            class_name = div_elem.attrib['class']
            if class_name == 'ocr_page': 
                for par_elem in div_elem.iterfind('.//{%s}%s' % (HOCR_NS,'p')):
                    line_info = None
                    if 'class' in par_elem.attrib:
                        class_name = par_elem.attrib['class']
                        if class_name == 'ocr_par': 
                            x0,y0,x1,y1,_ = getBBoxInfo(
                                par_elem.attrib['title'])
                            words = ''
                            for word_elem in par_elem.iterfind('.//{%s}%s' % (HOCR_NS,'span')):
                                class_name = word_elem.attrib['class']
                                if class_name in 'ocr_line,ocr_caption,ocr_header,ocr_textfloat': 
                                    #save line infos
                                    line_info = word_elem.attrib['title']
                                    line_index = line_info.find(';')
                                    line_info = line_info[line_index + 1:]
                                    line_info = ' '.join(line_info.split())
                                if class_name == 'ocrx_word': #word details
                                    word_text = word_elem.text.strip()
                                    if len(word_text) > 0:
                                        x0,y0,x1,y1,conf = getBBoxInfo(
                                            word_elem.attrib['title'])
                                        if conf >= HOCRconf or (number and hasNumbers(word_text)):
                                            pars.append(
                                                word_region(page_region(x0,y0,x1,y1),
                                                par_elem.attrib['id'],
                                                div_elem.attrib['id'],
                                                word_text,line_info,conf))
                                    words += word_text
                            #skip para blocks that don't have any text
                            if len(words.strip()) > 0:
                                print(".",end="",flush=True)

    return pars

""" use word coords to remove already recognized sections """
def runThruHocr(ifile,iconf,number,pars):

    print("sort through hocr words for " + ifile + " ...",end="",flush=True)
    try:
        tree = ET.ElementTree(file=ifile)
    except:
        tree = None
    if tree is not None:
        pars = sortOutHocr(tree,ifile,iconf,number,pars)
    print("!") #hocr processing is done

    return pars

""" write results to file """
def writeHocr(block,fhocr):

    hfile = open(fhocr, "w+b")
    hfile.write(bytearray(block))
    hfile.close()

#parser values
parser = argparse.ArgumentParser()
arg_named = parser.add_argument_group("named arguments")
arg_named.add_argument("-f","--file", 
    help="input file, for example: page.hocr")
arg_named.add_argument("-c","--conf", default=50, type=int,
    help="set confidence number threshold for ocr words")
arg_named.add_argument('-l', '--lang', type=str, 
    default="eng",
    help="language for OCR")
arg_named.add_argument("-n",'--number', action='store_true', 
    default=False,
    help="flag to bypass confidence value for words with number(s)")
arg_named.add_argument('-t', '--title', type=str, 
    help="title to set for HOCR file")

args = parser.parse_args()

if args.file == None or not os.path.exists(args.file):
    print("missing hocr file, use '-h' parameter for syntax")
    sys.exit()

img_base = args.file.rsplit('.', 1)[0]
print("img_base", img_base)

if os.path.exists(img_base + "_odw.hocr"):
    print("odw file exists")
    sys.exit()

result_title = args.title
if args.title == None:
    result_title = img_base + "_odw.hocr"
        
pars = []
pars = runThruHocr(args.file,int(args.conf),args.number,pars)
        
orig_page = ET.parse(args.file)

#hocr numbering starts at 1 (not 0)
page_cnt = 1
block_cnt = 1
par_cnt = 1
line_cnt = 1
word_cnt = 1
        
runThruPars(img_base + "_odw.hocr",pars,orig_page,int(args.conf),
    args.lang, result_title)
