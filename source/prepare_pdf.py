"""Prepare a tagged Word PDF locally for review in Acrobat Pro."""

from copy import copy
import json
import re
import sys
from xml.dom import minidom

from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject, ContentStream, DecodedStreamObject, DictionaryObject,
    NameObject, NumberObject, TextStringObject,
)

UA = "http://www.aiim.org/pdfua/ns/id/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
GENERIC_LINKS = {"click here", "here", "read more", "more", "learn more", "link"}
TEXT_OPERATORS = {b"Tj", b"TJ", b"'", b'"'}


class ReviewError(Exception):
    pass


def set_pdfua_identifier(writer):
    source = writer.root_object.get("/Metadata")
    if source is None:
        doc = minidom.parseString(
            f'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="{RDF}"/></x:xmpmeta>'
        )
    else:
        doc = minidom.parseString(source.get_object().get_data())
    rdf, = doc.getElementsByTagNameNS(RDF, "RDF")
    declarations = [
        node.firstChild.data.strip() if node.firstChild else ""
        for node in doc.getElementsByTagNameNS(UA, "part")
    ]
    for description in doc.getElementsByTagNameNS(RDF, "Description"):
        if description.hasAttributeNS(UA, "part"):
            declarations.append(description.getAttributeNS(UA, "part").strip())
    if declarations:
        if declarations != ["1"]:
            raise ReviewError("The exported file already declares a conflicting PDF/UA version.")
        return
    description = doc.createElementNS(RDF, "rdf:Description")
    description.setAttribute("xmlns:rdf", RDF)
    description.setAttributeNS(RDF, "rdf:about", "")
    description.setAttribute("xmlns:pdfuaid", UA)
    part = doc.createElementNS(UA, "pdfuaid:part")
    part.appendChild(doc.createTextNode("1"))
    description.appendChild(part)
    rdf.appendChild(description)
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


def prepare(source, candidate):
    writer = PdfWriter(clone_from=source)
    link_pages = fill_link_contents(writer)
    set_pdfua_identifier(writer)
    writer.write(candidate)
    return link_pages


def main():
    source, candidate = sys.argv[1:]
    try:
        link_pages = prepare(source, candidate)
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
