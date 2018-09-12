import re

def get_eoas_recordid(value):
    pattern = re.compile("\w\d{6}")
    if re.search(pattern, value):
        return re.findall(pattern, value)[0]
    else:
        return None

def get_eoas_recordid_if_corporate(dom):
    relation = dom.getElementsByTagName("relationEntry")[0]

    if relation.getAttribute("localType") != "Corporate Body":
        return None

    url = dom.getAttribute("xlink:href")
    if get_eoas_recordid(url):
        return get_eoas_recordid(url)
    else:
        return None
