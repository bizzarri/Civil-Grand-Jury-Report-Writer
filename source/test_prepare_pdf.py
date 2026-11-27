import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject, BooleanObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject, RectangleObject, TextStringObject,
)

from prepare_pdf import DC, RDF, ReviewError, prepare


HELPER = [sys.executable, str(Path(__file__).with_name("prepare_pdf.py").resolve())]


def pdf_dict(**items):
    return DictionaryObject({NameObject("/" + key): value for key, value in items.items()})


def fixture(path, caption="See Finding F1", title="Synthetic report"):
    writer = PdfWriter()
    if title:
        writer.add_metadata({"/Title": title})
    preferences = writer.create_viewer_preferences()
    preferences[NameObject("/DisplayDocTitle")] = BooleanObject(False)
    preferences[NameObject("/FitWindow")] = BooleanObject(True)
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
            fixture(source, title="")
            report = Path(tmp) / "finished Word report.docx"
            title = "Rural roads: $5 & maintenance — café"
            with ZipFile(report, "w") as package:
                package.writestr("docProps/core.xml",
                    f'<cp:coreProperties xmlns:cp="urn:synthetic" xmlns:dc="{DC}">'
                    f"<dc:title>{escape(title)}</dc:title></cp:coreProperties>")
            env = {key: value for key, value in os.environ.items() if key.upper() not in ("JAVA_HOME", "PATH")}
            env["PATH"] = ""
            result = subprocess.run(HELPER + [str(source), str(candidate), str(report)], env=env,
                                    timeout=60, capture_output=True, check=True)
            self.assertEqual(json.loads(result.stdout), {"ok": True, "linkPages": []})
            pdf = PdfReader(candidate)
            self.assertEqual(pdf.pages[0]["/Annots"][0].get_object()["/Contents"], "See Finding F1")
            self.assertIn(b"<pdfuaid:part>1</pdfuaid:part>", pdf.trailer["/Root"]["/Metadata"].get_data())
            self.assertEqual(pdf.metadata.title, title)
            self.assertEqual(pdf.xmp_metadata.dc_title, {"x-default": title})
            self.assertTrue(pdf.root_object["/ViewerPreferences"]["/DisplayDocTitle"].value)
            self.assertTrue(pdf.root_object["/ViewerPreferences"]["/FitWindow"].value)

    def test_pdf_title_and_translations_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root / "fixture.pdf")
            writer = PdfWriter(clone_from=root / "fixture.pdf")
            writer.xmp_metadata = (
                '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
                f'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="{RDF}">'
                f'<rdf:Description rdf:about="" xmlns:dc="{DC}"><dc:title><rdf:Alt>'
                '<rdf:li xml:lang="x-default">PDF title</rdf:li><rdf:li xml:lang="fr">Titre</rdf:li>'
                '</rdf:Alt></dc:title></rdf:Description></rdf:RDF></x:xmpmeta>\n'
                '<?xpacket end="w"?>'
            ).encode()
            writer.write(root / "before.pdf")
            prepare(root / "before.pdf", root / "after.pdf")
            pdf = PdfReader(root / "after.pdf")
            self.assertEqual(pdf.metadata.title, "PDF title")
            self.assertEqual(pdf.xmp_metadata.dc_title, {"x-default": "PDF title", "fr": "Titre"})
            packet = pdf.root_object["/Metadata"].get_data()
            self.assertTrue(packet.startswith('<?xpacket begin="\ufeff"'.encode()))
            self.assertTrue(packet.endswith(b'<?xpacket end="w"?>'))
            self.assertNotIn(b"<?xml ", packet)

    def test_missing_report_title_gets_an_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, candidate = (Path(tmp) / name for name in ("source.pdf", "out.pdf"))
            fixture(source, title="")
            with self.assertRaisesRegex(ReviewError, "The report needs a document title"):
                prepare(source, candidate)
            self.assertFalse(candidate.exists())



class PublicationWordTests(unittest.TestCase):
    def test_publication_copy_removes_only_the_draft_watermark(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "Word report with edits.docx"
            destination = Path(tmp) / "Temporary publication copy.docx"
            footer = (
                '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                'xmlns:v="urn:schemas-microsoft-com:vml">'
                '<w:p><w:r><w:t>Edited footer text</w:t></w:r><w:r><w:pict>'
                '<v:shape id="ReportConfidentialDraft"><v:textpath string="CONFIDENTIAL DRAFT"/></v:shape>'
                '<v:shape id="Logo"><v:textpath string="Logo"/></v:shape>'
                '</w:pict></w:r></w:p></w:ftr>'
            )
            with ZipFile(source, "w") as document:
                document.writestr("word/footer1.xml", footer)
                document.writestr("word/document.xml", b"Edited Word report body")
                document.writestr("word/media/figure.png", b"Edited figure")
            original = source.read_bytes()
            result = subprocess.run(HELPER + ["--publication-word-copy", str(source), str(destination)],
                                    timeout=60, capture_output=True, check=True)
            self.assertTrue(json.loads(result.stdout)["ok"])
            self.assertEqual(source.read_bytes(), original)
            with ZipFile(destination) as document:
                adjusted = document.read("word/footer1.xml")
                self.assertNotIn(b"CONFIDENTIAL DRAFT", adjusted)
                self.assertIn(b"Edited footer text", adjusted)
                self.assertIn(b'id="Logo"', adjusted)
                self.assertEqual(document.read("word/document.xml"), b"Edited Word report body")
                self.assertEqual(document.read("word/media/figure.png"), b"Edited figure")


if __name__ == "__main__":
    if "--helper" in sys.argv:
        index = sys.argv.index("--helper")
        HELPER = [str(Path(sys.argv[index + 1]).resolve())]
        del sys.argv[index:index + 2]
    unittest.main()
