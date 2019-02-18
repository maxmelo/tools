import sys
import os
import xml.etree.ElementTree as ET 
import urllib.request
import json      

REQUIRED_FIELDS = {
    "source": "identifier",
    "title": "title",
    "author": "creator",
    "isbn": "",
    "version": "meta;se:revision-number"
}
POST_URL = "http://ec2-18-219-223-27.us-east-2.compute.amazonaws.com/api/publish"

def postwithjson(url, d):
    req = urllib.request.Request(url)
    req.add_header('Content-Type', 'application/json; charset=utf-8')
    jsond = json.dumps(d)
    je = jsond.encode("utf-8")
    req.add_header('Content-Length', len(je))
    return urllib.request.urlopen(req, je)


def sendtoroe(contentfile):
    if not os.path.exists(contentfile):
        print("Invalid ePUB directory")
        return
    
    data = {}
    try:
        #parse content xml and get metadata
        xml = ET.parse(contentfile)
        root = xml.getroot()
        metadata = [x for x in root if x.tag[-8:] == "metadata"][0]
        
        #iterate through metadata and extract relevant fields by tag
        #if field has semicolon, match tag and also property (there are many meta tags but they have different property attributes)
        for child in metadata:
            for key, value in REQUIRED_FIELDS.items():
                spl = value.split(";")
                tag = spl[0]

                if tag == child.tag[-len(tag):]:
                    if len(spl) == 1:
                        data[key] = child.text
                        break
                    else:
                        if not "property" in child.attrib or child.attrib["property"] != spl[1]:
                            continue

                        data[key] = child.text

        #remove url prefix from source attribute
        if data["source"][:4] == "url:":
            data["source"] = data["source"][4:]
    except:
        print("Error parsing XML or sending to server")
        return

    print(data)
    response = postwithjson(POST_URL, data)
    print(response)

if __name__ == "__main__":
    #take a path to a directory on the command line
    if len(sys.argv) == 2:
        path = sys.argv[1]

        if os.path.isdir(path):
            contentfile = "{}/src/epub/content.opf".format(path)
            print(sendtoroe(contentfile))
        else:
            print("ePUB directory invalid")
    else:
        print("Wrong number of args")
