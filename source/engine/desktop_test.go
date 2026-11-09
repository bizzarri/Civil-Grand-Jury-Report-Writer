package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDesktopSaveImportAndConflict(t *testing.T) {
	tpl, d := fixture(t)
	s := &Server{template: tpl, dir: t.TempDir()}
	if e := s.save(&d); e != nil {
		t.Fatal(e)
	}
	copy := d
	copy.Title = "Changed title"
	r, e := s.execute(Request{Op: "save", Draft: copy})
	if e != nil || r.Draft.Revision != 2 {
		t.Fatal(e)
	}
	if _, e = s.execute(Request{Op: "save", Draft: d}); e == nil {
		t.Fatal("stale save accepted")
	}
	b, _ := json.Marshal(d)
	r, e = s.execute(Request{Op: "import", Content: string(b)})
	if e != nil || r.Draft.ID == d.ID || r.Draft.Title != d.Title {
		t.Fatal("import did not preserve content as a new draft", e)
	}
	original, e := s.read(d.ID)
	if e != nil || original.Title != "Changed title" {
		t.Fatal("import overwrote original", e)
	}
	r, e = s.execute(Request{Op: "export", ID: d.ID})
	if e != nil || r.Data == "" {
		t.Fatal("export failed", e)
	}
	if _, e = s.execute(Request{Op: "get", ID: "../../outside"}); e == nil {
		t.Fatal("invalid path accepted")
	}
	if _, e = s.execute(Request{Op: "import", Content: `{"templateHash":"wrong"}`}); e == nil {
		t.Fatal("wrong template accepted")
	}
}
func TestDesktopProtocol(t *testing.T) {
	q := Request{Op: "new", Dir: t.TempDir()}
	b, _ := json.Marshal(q)
	var out bytes.Buffer
	runEngine(bytes.NewReader(b), &out)
	var r Result
	if json.Unmarshal(out.Bytes(), &r) != nil || !r.OK || r.Draft == nil {
		t.Fatal(out.String())
	}
	if _, e := os.Stat(filepath.Join(q.Dir, r.Draft.ID+".json")); e != nil {
		t.Fatal(e)
	}
	out.Reset()
	runEngine(strings.NewReader(`{"op":"new","dir":"relative"}`), &out)
	if json.Unmarshal(out.Bytes(), &r) != nil || r.OK {
		t.Fatal("relative data directory accepted")
	}
}
