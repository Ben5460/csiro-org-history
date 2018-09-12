#!/usr/bin/env python3

"""
Convert Encylopedia of Australian Science (http://www.eoas.info/) XML records
using EAC-CPF schema into a linked data representation using ORG, PROV and other
vocabs
"""

from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, FOAF, DC, XSD
from xml.dom.minidom import parse
from glob import iglob
import re
from EoasUtils import get_eoas_recordid, get_eoas_recordid_if_corporate

graph = Graph()
ORG = Namespace("http://www.w3.org/ns/org#")
PROV = Namespace("http://www.w3.org/ns/prov#")
CSIRO = Namespace("http://aays.csiro.au/data/csiro/")
LOCN = Namespace("http://www.w3.org/ns/locn#")

known_places = []

def graph_setup():
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("owl", OWL)
    graph.bind("foaf", FOAF)
    graph.bind("dc", DC)
    graph.bind("org", ORG)
    graph.bind("prov", PROV)
    graph.bind("csiro", CSIRO)
    graph.bind("locn", LOCN)

def get_text(element):
    text = ""

    for node in element.childNodes:
        if node.nodeType == node.TEXT_NODE:
            text = text + node.data

    return text

def slugify(value):
    return re.sub('[^\w]', '', value)

def parse_inputfile(filename):
    with open(filename, "r") as file:
        dom = parse(file)

    records = dom.getElementsByTagName("cpfDescription")

    for record in records:
        identifier = get_text(record.getElementsByTagName("entityId")[0])
        eoas_uri = URIRef(identifier.rstrip(".htm"))
        identifier_uri = CSIRO[get_eoas_recordid(identifier)]

        graph.add( (identifier_uri, OWL.sameAs, eoas_uri) )

        identifier_type = get_text(record.getElementsByTagName("entityType")[0])

        if identifier_type == "person":
            process_person(record, identifier_uri)
        elif identifier_type == "corporateBody":
            process_corporatebody(record, identifier_uri)

def process_nameentry(nameEntry):
    parts = {}

    parts_elems = nameEntry.getElementsByTagName("part")
    for part in parts_elems:
        if part.hasAttribute("localType") and part.hasChildNodes():
            parts[part.getAttribute("localType")] = get_text(part)
        elif part.hasChildNodes():
            parts["noattr"] = get_text(part)

    return parts

# FIXME surely there is a better way of doing this
def get_or_add_place(place_stub, place_entry):
    if place_stub in known_places:
        return CSIRO[place_stub]
    else:
        known_places.append(place_stub)

        place_uri = CSIRO[place_stub]
        graph.add( (place_uri, RDF.type, ORG.Site) )

        site_address = BNode()
        graph.add( (place_uri, ORG.siteAddress, site_address))
        graph.add( (site_address, LOCN.fullAddress, Literal(place_entry, datatype=XSD.string)) )
        graph.add( (site_address, RDF.type, LOCN.Address) )

        return place_uri

def process_person(record, identifier_uri):
    graph.add( (identifier_uri, RDF.type, FOAF.Person) )

    name_parts = process_nameentry(record.getElementsByTagName("nameEntry")[0])
    familyname = name_parts.get("familyname", None)
    givenname = name_parts.get("givenname", None)

    if familyname != None:
        graph.add( (identifier_uri, FOAF.familyName, Literal(familyname, datatype=XSD.string)) )
    if givenname != None:
        graph.add( (identifier_uri, FOAF.givenName, Literal(givenname, datatype=XSD.string)) )

def process_corporatebody(record, identifier_uri):
    graph.add( (identifier_uri, RDF.type, ORG.Organization) )

    name_parts = process_nameentry(record.getElementsByTagName("nameEntry")[0])
    name = name_parts.get("noattr", None)
    if name != None:
        graph.add( (identifier_uri, FOAF.name, Literal(name, datatype=XSD.string)) )

    if record.getElementsByTagName("abstract"):
        abstract = get_text(record.getElementsByTagName("abstract")[0])
        graph.add( (identifier_uri, DC.description, Literal(abstract, datatype=XSD.string)))

    if record.getElementsByTagName("functions"):
        terms = record.getElementsByTagName("functions")[0].getElementsByTagName("term")
        for term in terms:
            graph.add( (identifier_uri, DC.subject, Literal(get_text(term), datatype=XSD.string)) )

    # FIXME this is gross
    if record.getElementsByTagName("places"):
        places = record.getElementsByTagName("places")

        for place in places:
            place_roles = place.getElementsByTagName("placeRole")
            for place_role in place_roles:
                if place_role.childNodes[0].nodeValue == "Start Place":
                    place_entry = place.getElementsByTagName("placeEntry")[0].childNodes[0].nodeValue
                    place_slug = slugify(place_entry.split(",")[0])
                    place_uri = get_or_add_place(place_slug, place_entry)
                    graph.add( (identifier_uri, ORG.hasPrimarySite, place_uri) )
                    break

    identifier = str(identifier_uri).rsplit("/", 1)[1]
    created_identifier = identifier + "-i"
    created_uri = CSIRO[created_identifier]
    terminated_identifier = identifier + "-x"
    terminated_uri = CSIRO[terminated_identifier]

    graph.add( (created_uri, RDF.type, ORG.ChangeEvent) )
    graph.add( (created_uri, ORG.resultingOrganization, identifier_uri) )
    graph.add( (created_uri, RDFS.label, Literal(name + " - initiated", datatype=XSD.string)) )
    graph.add( (identifier_uri, ORG.resultedFrom, created_uri) )

    graph.add( (terminated_uri, RDF.type, ORG.ChangeEvent) )
    graph.add( (terminated_uri, ORG.originalOrganization, identifier_uri) )
    graph.add( (terminated_uri, RDFS.label, Literal(name + " - terminated", datatype=XSD.string)) )
    graph.add( (identifier_uri, ORG.changedBy, terminated_uri) )

    if record.getElementsByTagName("dateRange"):
        date_range = record.getElementsByTagName("dateRange")[0]

        if date_range.getElementsByTagName("fromDate"):
            from_date = date_range.getElementsByTagName("fromDate")[0].getAttribute("standardDate")
            graph.add( (created_uri, PROV.endedAtTime, Literal(from_date, datatype=XSD.date)) )
            graph.add( (identifier_uri, PROV.generatedAtTime, Literal(from_date, datatype=XSD.date)) )

        if date_range.getElementsByTagName("toDate"):
            to_date = date_range.getElementsByTagName("toDate")[0].getAttribute("standardDate")
            graph.add( (terminated_uri, PROV.endedAtTime, Literal(to_date, datatype=XSD.date)) )
            graph.add( (identifier_uri, PROV.invalidatedAtTime, Literal(to_date, datatype=XSD.date)) )

    """ We want to handle 'associative' relationship types differently depending on whether the associated entity is a corporate body or a person, so fiddle with //@cpfRelationType to indicate the nature of the associated entity """
    relation_elems = record.getElementsByTagName("cpfRelation")
    for elem in relation_elems:
        if elem.getAttribute("cpfRelationType") == "associative":
            relation_entry = elem.getElementsByTagName("relationEntry")[0]
            if relation_entry.getAttribute("localType") == "Corporate Body":
                elem.setAttribute("cpfRelationType", "associative-corporate")
            elif relation_entry.getAttribute("localType") == "Person":
                elem.setAttribute("cpfRelationType", "associative-person")

    relations = build_relations(record.getElementsByTagName("cpfRelation"))
    process_relations(relations, identifier_uri, created_uri, terminated_uri)

def build_relations(relation_elems):
    relations = {}

    for elem in relation_elems:
        relation_type = elem.getAttribute("cpfRelationType")
        relation = elem.getAttribute("xlink:href")

        if get_eoas_recordid_if_corporate(elem):
            relation_uri = CSIRO[get_eoas_recordid_if_corporate(elem)]
        else:
            relation_uri = URIRef(elem.getAttribute("xlink:href").rstrip(".htm"))

        if relation_type not in relations:
            relations[relation_type] = []

        relations[relation_type].append(relation_uri)

    return relations

def process_relations(relations, identifier_uri, created_uri, terminated_uri):
    for type, relation_uris in relations.items():
        for relation_uri in relation_uris:
            if type == "hierarchical-parent":
                graph.add( (identifier_uri, ORG.unitOf, relation_uri) )
            elif type == "hierarchical-child":
                graph.add( (identifier_uri, ORG.hasUnit, relation_uri) )
            elif type == "temporal-earlier":
                graph.add( (created_uri, ORG.originalOrganization, relation_uri) )
            elif type == "associative-corporate":
                graph.add( (identifier_uri, ORG.linkedTo, relation_uri) )
            elif type == "associative-person":
                graph.add( (identifier_uri, ORG.hasMember, relation_uri) )
            elif type == "identity":
                graph.add( (identifier_uri, OWL.sameAs, relation_uri) )
            elif type == "temporal-later":
                identifier = str(identifier_uri).rsplit("/", 1)[1]
                relation = str(relation_uri).rsplit("/", 1)[1]
                successor_uri = CSIRO["{}-{}".format(identifier, relation)]

                graph.add( (successor_uri, RDF.type, ORG.ChangeEvent) )
                graph.add( (successor_uri, ORG.originalOrganization, identifier_uri) )
                graph.add( (successor_uri, ORG.resultingOrganization, relation_uri) )

                graph.add( (identifier_uri, ORG.changedBy, successor_uri) )

def main():
    graph_setup()

    for file in iglob("source_data/*.xml"):
        parse_inputfile(file)

    graph.serialize(destination="output.ttl", format="turtle", encoding="utf-8")
    #graph.serialize(destination="output.rdf", encoding="utf-8")

if __name__ == "__main__":
    main()
