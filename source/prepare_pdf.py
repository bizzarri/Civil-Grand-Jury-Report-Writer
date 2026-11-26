"""Prepare a tagged Word PDF locally for review in Acrobat Pro."""

from copy import copy
import json
import re
import sys
from xml.dom import Node, minidom
from xml.etree import ElementTree
from zipfile import ZipFile

from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject, BooleanObject, ContentStream, DecodedStreamObject, DictionaryObject,
    NameObject, NumberObject, TextStringObject,
)

DC = "http://purl.org/dc/elements/1.1/"
XML = "http://www.w3.org/XML/1998/namespace"
UA = "http://www.aiim.org/pdfua/ns/id/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
GENERIC_LINKS = {"click here", "here", "read more", "more", "learn more", "link"}
TEXT_OPERATORS = {b"Tj", b"TJ", b"'", b'"'}


class ReviewError(Exception):
    pass


def read_word_title(report):
    with ZipFile(report) as package:
        try:
            core_properties = package.read("docProps/core.xml")
        except KeyError:
            return ""
    return ElementTree.fromstring(core_properties).findtext(f"{{{DC}}}title", "").strip()


def text_content(element):
    return "".join(
        child.data for child in element.childNodes
        if child.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE)
    ).strip()


def set_document_title(writer, doc, rdf, word_title):
    descriptions = [
        node for node in rdf.getElementsByTagNameNS(RDF, "Description")
        if node.parentNode is rdf and node.getAttributeNS(RDF, "about") == ""
    ]
    title_elements = [
        child for description in descriptions for child in description.childNodes
        if child.namespaceURI == DC and child.localName == "title"
    ]
    titles = {}
    for element in title_elements:
        for item in element.getElementsByTagNameNS(RDF, "li"):
            language = item.getAttributeNS(XML, "lang")
            value = text_content(item)
            if language and value:
                titles.setdefault(language, value)
        value = text_content(element)
        if value:
            titles.setdefault("x-default", value)
    for description in descriptions:
        value = description.getAttributeNS(DC, "title").strip()
        if value:
            titles.setdefault("x-default", value)

    info_title = (writer.metadata or {}).get("/Title", "")
    if not isinstance(info_title, str):
        info_title = ""
    title = word_title or titles.get("x-default") or info_title.strip() or next(iter(titles.values()), "")
    if not title:
        raise ReviewError(
            "The report needs a document title. In Word, go to File → Info, enter a Title, "
            "save the report, and try again."
        )

    writer.add_metadata({"/Title": title})
    preferences = writer.viewer_preferences
    if preferences is None:
        preferences = writer.create_viewer_preferences()
    preferences[NameObject("/DisplayDocTitle")] = BooleanObject(True)

    for element in title_elements:
        element.parentNode.removeChild(element)
    for description in descriptions:
        if description.hasAttributeNS(DC, "title"):
            description.removeAttributeNS(DC, "title")

    if descriptions:
        description = descriptions[0]
    else:
        description = doc.createElementNS(RDF, "rdf:Description")
        description.setAttribute("xmlns:rdf", RDF)
        description.setAttributeNS(RDF, "rdf:about", "")
        rdf.appendChild(description)
    element = doc.createElementNS(DC, "dc:title")
    element.setAttribute("xmlns:dc", DC)
    description.appendChild(element)
    alternative = doc.createElementNS(RDF, "rdf:Alt")
    alternative.setAttribute("xmlns:rdf", RDF)
    element.appendChild(alternative)
    titles.pop("x-default", None)
    for language, value in {"x-default": title, **titles}.items():
        item = doc.createElementNS(RDF, "rdf:li")
        item.setAttributeNS(XML, "xml:lang", language)
        item.appendChild(doc.createTextNode(value))
        alternative.appendChild(item)


def set_review_metadata(writer, word_title):
    source = writer.root_object.get("/Metadata")
    if source is None:
        doc = minidom.parseString(
            f'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="{RDF}"/></x:xmpmeta>'
        )
    else:
        doc = minidom.parseString(source.get_object().get_data())
    rdf, = doc.getElementsByTagNameNS(RDF, "RDF")
    declarations = [text_content(node) for node in doc.getElementsByTagNameNS(UA, "part")]
    for description in doc.getElementsByTagNameNS(RDF, "Description"):
        if description.hasAttributeNS(UA, "part"):
            declarations.append(description.getAttributeNS(UA, "part").strip())
    if declarations and declarations != ["1"]:
        raise ReviewError("The exported file already declares a conflicting PDF/UA version.")
    if not declarations:
        description = doc.createElementNS(RDF, "rdf:Description")
        description.setAttribute("xmlns:rdf", RDF)
        description.setAttributeNS(RDF, "rdf:about", "")
        description.setAttribute("xmlns:pdfuaid", UA)
        part = doc.createElementNS(UA, "pdfuaid:part")
        part.appendChild(doc.createTextNode("1"))
        description.appendChild(part)
        rdf.appendChild(description)

    set_document_title(writer, doc, rdf, word_title)
    stream = DecodedStreamObject()
    stream.set_data(doc.toxml(encoding="utf-8"))
    stream[NameObject("/Type")] = NameObject("/Metadata")
    stream[NameObject("/Subtype")] = NameObject("/XML")
    writer.root_object[NameObject("/Metadata")] = writer._add_object(stream)


def number_tree(node):
    numbers = node.get("/Nums", [])
    for index in range(0, len(numbers), 2):
        yield int(numbers[index]), numbers[index + 1]
    for child in node.get("/Kids", []):
        yield from number_tree(child.get_object())


def marked_ids(node, page_ref, inherited_page, depth=0):
    if depth > 32:
        raise ReviewError("The PDF has a damaged link tag.")
    node = node.get_object()
    if isinstance(node, NumberObject):
        if inherited_page == page_ref:
            yield int(node)
    elif isinstance(node, ArrayObject):
        for child in node:
            yield from marked_ids(child, page_ref, inherited_page, depth + 1)
    elif isinstance(node, DictionaryObject):
        if "/Pg" in node:
            inherited_page = node.raw_get("/Pg")
        if "/MCID" in node and "/Stm" not in node and inherited_page == page_ref:
            yield int(node["/MCID"])
        if "/K" in node:
            yield from marked_ids(node["/K"], page_ref, inherited_page, depth + 1)


def link_caption(page, tag, operations):
    ids = set(marked_ids(tag, page.indirect_reference, page.indirect_reference))
    if not ids:
        return ""
    selected = []
    stack = []
    for args, op in operations:
        if op == b"BDC":
            properties = args[1]
            stack.append(isinstance(properties, DictionaryObject) and properties.get("/MCID") in ids)
        elif op == b"BMC":
            stack.append(False)
        elif op == b"EMC":
            stack.pop()
        if op in TEXT_OPERATORS and not any(stack):
            continue
        # Word's links are text marked on the page. Exclude unscoped XObjects.
        if op == b"Do":
            continue
        selected.append((args, op))
    isolated = ContentStream(None, page.pdf)
    isolated.operations = selected
    extraction_page = copy(page)
    extraction_page[NameObject("/Contents")] = isolated
    return " ".join(extraction_page.extract_text().split())


def useful_text(value):
    if not isinstance(value, str):
        return ""
    value = " ".join(value.split())
    return value if value.casefold().strip(".!?") not in GENERIC_LINKS else ""


def fill_link_contents(writer):
    tree = writer.root_object.get("/StructTreeRoot")
    if tree is None:
        raise ReviewError("Word exported a PDF without document tags. Ask the reviewer to check the Word export.")
    parent_tree = tree.get_object().get("/ParentTree")
    parents = dict(number_tree(parent_tree.get_object())) if parent_tree else {}
    link_pages = set()
    for number, page in enumerate(writer.pages, start=1):
        operations = None
        for reference in page.get("/Annots", []):
            annotation = reference.get_object()
            if annotation.get("/Subtype") != "/Link" or useful_text(annotation.get("/Contents")):
                continue
            parent = parents.get(annotation.get("/StructParent"))
            tag = parent.get_object() if parent is not None else None
            caption = ""
            if isinstance(tag, DictionaryObject):
                caption = useful_text(tag.get("/Alt")) or useful_text(tag.get("/ActualText"))
                if not caption:
                    if operations is None:
                        operations = ContentStream(page.get_contents(), writer).operations
                    caption = useful_text(link_caption(page, tag, operations))
            if not caption:
                action = annotation.get("/A")
                if action:
                    action = action.get_object()
                    if action.get("/S") == "/URI":
                        uri = useful_text(action.get("/URI"))
                        if re.match(r"^(https?://|mailto:)", uri, re.IGNORECASE):
                            caption = uri
            if not caption:
                link_pages.add(number)
                continue
            annotation[NameObject("/Contents")] = TextStringObject(caption)
    return sorted(link_pages)


def prepare(source, candidate, word_title=""):
    writer = PdfWriter(clone_from=source)
    link_pages = fill_link_contents(writer)
    set_review_metadata(writer, word_title)
    writer.write(candidate)
    return link_pages


def main():
    source, candidate, report = sys.argv[1:]
    try:
        link_pages = prepare(source, candidate, read_word_title(report))
    except ReviewError as exc:
        result = {"ok": False, "message": str(exc)}
    except Exception:
        result = {"ok": False, "message": "The exported PDF could not be prepared. Ask the reviewer to check the Word file."}
    else:
        result = {"ok": True, "linkPages": link_pages}
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
