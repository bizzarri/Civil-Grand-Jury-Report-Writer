import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject, RectangleObject, TextStringObject,
)

from prepare_pdf import prepare


HELPER = [sys.executable, str(Path(__file__).with_name("prepare_pdf.py").resolve())]


def pdf_dict(**items):
    return DictionaryObject({NameObject("/" + key): value for key, value in items.items()})


def fixture(path, caption="See Finding F1"):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    link = writer.add_annotation(0, pdf_dict(
        Type=NameObject("/Annot"), Subtype=NameObject("/Link"),
        Rect=RectangleObject([10, 10, 100, 24]),
    ))
    link[NameObject("/StructParent")] = NumberObject(7)
    tag = writer._add_object(pdf_dict(S=NameObject("/Link"), K=NumberObject(42)))
    parent_tree = pdf_dict(Nums=ArrayObject([NumberObject(7), tag]))
    writer.root_object[NameObject("/StructTreeRoot")] = writer._add_object(pdf_dict(ParentTree=parent_tree))
    font = pdf_dict(Type=NameObject("/Font"), Subtype=NameObject("/Type1"), BaseFont=NameObject("/Helvetica"))
    page[NameObject("/Resources")] = pdf_dict(Font=pdf_dict(F1=writer._add_object(font)))
    content = DecodedStreamObject()
    content.set_data(
        f"BT /F1 12 Tf 10 25 Td (Before the link) Tj "
        f"/Link <</MCID 42>> BDC ({caption}) Tj EMC (After the link) Tj ET".encode()
    )
    page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(path)


class PrepareTests(unittest.TestCase):
    def test_link_text_comes_from_its_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, candidate, repeated = (Path(tmp) / name for name in ("source.pdf", "out.pdf", "again.pdf"))
            fixture(source)
            self.assertEqual(prepare(source, candidate), [])
            self.assertEqual(prepare(candidate, repeated), [])
            first, last = PdfReader(candidate), PdfReader(repeated)
            for pdf in (first, last):
                self.assertEqual(pdf.pages[0]["/Annots"][0].get_object()["/Contents"], "See Finding F1")
                xmp = pdf.trailer["/Root"]["/Metadata"].get_data()
                self.assertEqual(xmp.count(b"<pdfuaid:part>1</pdfuaid:part>"), 1)

    def test_unlabeled_internal_link_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, candidate = (Path(tmp) / name for name in ("source.pdf", "out.pdf"))
            fixture(source, "click here")
            self.assertEqual(prepare(source, candidate), [1])
            result = PdfReader(candidate)
            self.assertNotIn("/Contents", result.pages[0]["/Annots"][0].get_object())

    def test_existing_description_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root / "fixture.pdf")
            writer = PdfWriter(clone_from=root / "fixture.pdf")
            writer.pages[0]["/Annots"][0].get_object()[NameObject("/Contents")] = TextStringObject("Finding one")
            writer.write(root / "input.pdf")
            prepare(root / "input.pdf", root / "result.pdf")
            result = PdfReader(root / "result.pdf")
            self.assertEqual(result.pages[0]["/Annots"][0].get_object()["/Contents"], "Finding one")


    def test_helper_prepares_pdf_without_java(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, candidate = (Path(tmp) / name for name in ("source file.pdf", "review file.pdf"))
            fixture(source)
            env = {key: value for key, value in os.environ.items() if key.upper() not in ("JAVA_HOME", "PATH")}
            env["PATH"] = ""
            result = subprocess.run(HELPER + [str(source), str(candidate)], env=env,
                                    timeout=60, capture_output=True, check=True)
            self.assertEqual(json.loads(result.stdout), {"ok": True, "linkPages": []})
            pdf = PdfReader(candidate)
            self.assertEqual(pdf.pages[0]["/Annots"][0].get_object()["/Contents"], "See Finding F1")
            self.assertIn(b"<pdfuaid:part>1</pdfuaid:part>", pdf.trailer["/Root"]["/Metadata"].get_data())


if __name__ == "__main__":
    if "--helper" in sys.argv:
        index = sys.argv.index("--helper")
        HELPER = [str(Path(sys.argv[index + 1]).resolve())]
        del sys.argv[index:index + 2]
    unittest.main()
