import requests
import re
from xml.dom.minidom import parseString
import os
from EoasUtils import get_eoas_recordid_if_corporate

BASEURL = "http://oai.esrc.unimelb.edu.au/EOAS/provider?verb=GetRecord&metadataPrefix=eac-cpf&identifier=oai:eoas.oai.esrc.unimelb.edu.au:"
OUTPATH = "source_data"

class EoasOaiClient(object):
    def __init__(self, baseurl=BASEURL, outpath=OUTPATH, verbose=None):
        self.baseurl = baseurl
        self.outpath = outpath
        self.verbose = verbose
        self.known_records = []

        if not os.path.exists(self.outpath):
            os.makedirs(outpath)

    def get_record(self, record_id):
        self.known_records.append(record_id)
        request = requests.get("{}{}".format(self.baseurl, record_id))
        dom = parseString(request.text)
        document = dom.getElementsByTagName("eac-cpf")[0]
        return document

    def download_record(self, record_id):
        document = self.get_record(record_id)
        self.save_record(document, record_id)

    def download_record_and_relations(self, record_id):
        if record_id in self.known_records:
            if self.verbose:
                print("{} already known, skipping".format(record_id))
            return None

        if self.verbose:
            print("Downloading {} and relations".format(record_id))

        document = self.get_record(record_id)
        self.save_record(document, record_id)

        relations = document.getElementsByTagName("cpfRelation")
        relation_types = ["hierarchical-child", "temporal-earlier", "temporal-later"]

        for relation in relations:
            relation_type = relation.getAttribute("cpfRelationType")
            if relation_type in relation_types:
                if self.verbose:
                    print("Getting a {} for {}".format(relation_type, record_id))

                relation_id = get_eoas_recordid_if_corporate(relation)
                if relation_id:
                    self.download_record_and_relations(relation_id)

    def save_record(self, document, record_id):
        outfile = "{}.xml".format(record_id)
        with open(os.path.join(self.outpath, outfile), "w") as file:
            print(document.toprettyxml(), file=file)
