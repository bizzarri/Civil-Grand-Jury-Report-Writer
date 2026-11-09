package main

import (
	"archive/zip"
	"bytes"
	"encoding/xml"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func fixture(t *testing.T) (*Template, Draft) {
	t.Helper()
	b, e := assets.ReadFile("template/revised.docx")
	if e != nil {
		t.Fatal(e)
	}
	tpl, e := loadTemplate(b)
	if e != nil {
		t.Fatal(e)
	}
	d := Draft{ID: newID(), TemplateHash: tpl.Hash, Title: "Synthetic export verification", County: "Test County", Term: "Test term", ReleaseDate: "Test date", Answers: map[string]string{}, Findings: []Finding{{ID: newID(), Text: "Synthetic finding <one> & evidence", Evidence: "Test fixture only", Verified: true}, {ID: newID(), Text: "Second synthetic finding", Evidence: "Test fixture only", Verified: true}}}
	for _, s := range tpl.Sections {
		if !s.Optional {
			d.Answers[s.ID] = "Synthetic verification text.\n\nSecond paragraph with Unicode: café."
		}
	}
	d.Recommendations = []Recommendation{{ID: newID(), Owner: "Test owner", Action: "Synthetic action", Due: "Test timing", FindingIDs: []string{d.Findings[1].ID, d.Findings[0].ID}}}
	return tpl, d
}
func parts(t *testing.T, b []byte) map[string][]byte {
	t.Helper()
	z, e := zip.NewReader(bytes.NewReader(b), int64(len(b)))
	if e != nil {
		t.Fatal(e)
	}
	out := map[string][]byte{}
	for _, f := range z.File {
		r, e := f.Open()
		if e != nil {
			t.Fatal(e)
		}
		out[f.Name], e = io.ReadAll(r)
		r.Close()
		if e != nil {
			t.Fatal(e)
		}
	}
	return out
}
func TestTemplateExportPreservesPackage(t *testing.T) {
	tpl, d := fixture(t)
	b, e := tpl.export(d)
	if e != nil {
		t.Fatal(e)
	}
	before, after := parts(t, tpl.data), parts(t, b)
	if len(before) != len(after) {
		t.Fatal("package part count changed")
	}
	for k, v := range before {
		if k != "word/document.xml" && k != "docProps/core.xml" && !bytes.Equal(v, after[k]) {
			t.Errorf("preserved part changed: %s", k)
		}
	}
	doc := string(after["word/document.xml"])
	dec := xml.NewDecoder(strings.NewReader(doc))
	for {
		_, e := dec.Token()
		if e == io.EOF {
			break
		}
		if e != nil {
			t.Fatal(e)
		}
	}
	for _, bad := range []string{"[Highlight", "TemplateInstruction", "Author instructions and publication checklist", "Optional Accessible", "Test fixture only"} {
		if strings.Contains(doc, bad) {
			t.Errorf("leaked placeholder/instruction/evidence %s", bad)
		}
	}
	if !strings.Contains(doc, `w:pStyle w:val="Finding"`) || !strings.Contains(doc, `w:pStyle w:val="Recommendation"`) {
		t.Fatal("numbering styles missing")
	}
	for _, f := range d.Findings {
		if !strings.Contains(doc, `w:anchor="Finding_`+f.ID+`"`) || !strings.Contains(doc, `w:name="Finding_`+f.ID+`"`) {
			t.Fatal("broken finding link")
		}
	}
	if !strings.Contains(doc, "&lt;one&gt; &amp;") {
		t.Fatal("XML escaping failed")
	}
	if strings.Contains(doc, ">GLOSSARY<") {
		t.Fatal("empty optional section retained")
	}
	if dir := os.Getenv("REPORT_QA_DIR"); dir != "" {
		if e = os.WriteFile(filepath.Join(dir, "synthetic-export.docx"), b, 0600); e != nil {
			t.Fatal(e)
		}
	}
}
func TestExportRequiresVerifiedEvidenceAndValidLinks(t *testing.T) {
	tpl, d := fixture(t)
	d.Findings[0].Verified = false
	if _, e := tpl.export(d); e == nil {
		t.Fatal("unverified finding accepted")
	}
	d.Findings[0].Verified = true
	d.Recommendations[0].FindingIDs = []string{newID()}
	if _, e := tpl.export(d); e == nil {
		t.Fatal("dangling link accepted")
	}
	d.Recommendations[0].FindingIDs = []string{d.Findings[0].ID}
	d.TemplateHash = "wrong"
	if _, e := tpl.export(d); e == nil {
		t.Fatal("wrong template accepted")
	}
}
