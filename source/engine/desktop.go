package main

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Request struct {
	Op      string `json:"op"`
	Dir     string `json:"dir"`
	ID      string `json:"id"`
	Draft   Draft  `json:"draft"`
	Content string `json:"content"`
}
type Result struct {
	OK       bool      `json:"ok"`
	Error    string    `json:"error,omitempty"`
	Template *Template `json:"template,omitempty"`
	Draft    *Draft    `json:"draft,omitempty"`
	Drafts   []Draft   `json:"drafts,omitempty"`
	Data     string    `json:"data,omitempty"`
}

func (s *Server) read(id string) (Draft, error) {
	var d Draft
	if !safeID.MatchString(id) {
		return d, errors.New("invalid draft ID")
	}
	b, e := os.ReadFile(filepath.Join(s.dir, id+".json"))
	if e != nil {
		return d, e
	}
	e = json.Unmarshal(b, &d)
	if e != nil {
		return d, e
	}
	if d.ID != id || d.TemplateHash != s.template.Hash {
		return d, errors.New("draft identity or template does not match")
	}
	if d.Answers == nil {
		d.Answers = map[string]string{}
	}
	return d, nil
}
func (s *Server) execute(q Request) (Result, error) {
	result := Result{OK: true}
	switch q.Op {
	case "template":
		result.Template = s.template
	case "list":
		result.Drafts = []Draft{}
		files, e := os.ReadDir(s.dir)
		if e != nil {
			return result, e
		}
		for _, f := range files {
			if strings.HasSuffix(f.Name(), ".json") {
				d, e := s.read(strings.TrimSuffix(f.Name(), ".json"))
				if e != nil {
					return result, fmt.Errorf("cannot read draft %s: %w", f.Name(), e)
				}
				result.Drafts = append(result.Drafts, d)
			}
		}
		sort.Slice(result.Drafts, func(i, j int) bool { return result.Drafts[i].Updated > result.Drafts[j].Updated })
	case "new":
		d := Draft{ID: newID(), TemplateHash: s.template.Hash, Answers: map[string]string{}, Findings: []Finding{}, Recommendations: []Recommendation{}}
		if e := s.save(&d); e != nil {
			return result, e
		}
		result.Draft = &d
	case "get":
		d, e := s.read(q.ID)
		if e != nil {
			return result, e
		}
		result.Draft = &d
	case "save":
		old, e := s.read(q.Draft.ID)
		if e != nil {
			return result, e
		}
		if q.Draft.TemplateHash != s.template.Hash {
			return result, errors.New("template mismatch")
		}
		if old.Revision != q.Draft.Revision {
			return result, errors.New("this draft has changed on disk; preserve unsaved text and reopen it before saving")
		}
		if q.Draft.Answers == nil {
			q.Draft.Answers = map[string]string{}
		}
		if e = s.save(&q.Draft); e != nil {
			return result, e
		}
		result.Draft = &q.Draft
	case "import":
		var d Draft
		if e := json.Unmarshal([]byte(q.Content), &d); e != nil {
			return result, errors.New("not a valid report draft JSON file")
		}
		if d.TemplateHash != s.template.Hash {
			return result, errors.New("this file is not a draft from the revised accessible template")
		}
		if d.Answers == nil {
			d.Answers = map[string]string{}
		}
		d.ID = newID()
		d.Revision = 0
		if e := s.save(&d); e != nil {
			return result, e
		}
		result.Draft = &d
	case "export":
		d, e := s.read(q.ID)
		if e != nil {
			return result, e
		}
		b, e := s.template.export(d)
		if e != nil {
			return result, e
		}
		result.Data = base64.StdEncoding.EncodeToString(b)
	default:
		return result, errors.New("unknown operation")
	}
	return result, nil
}
func runEngine(in io.Reader, out io.Writer) {
	result := Result{}
	func() {
		defer func() {
			if recover() != nil {
				result = Result{Error: "local engine failed"}
			}
		}()
		var q Request
		dec := json.NewDecoder(io.LimitReader(in, 4<<20))
		dec.DisallowUnknownFields()
		if e := dec.Decode(&q); e != nil {
			result.Error = "invalid request: " + e.Error()
			return
		}
		var extra any
		if dec.Decode(&extra) != io.EOF {
			result.Error = "unexpected trailing request data"
			return
		}
		if q.Dir == "" || !filepath.IsAbs(q.Dir) {
			result.Error = "absolute draft folder required"
			return
		}
		b, e := assets.ReadFile("template/revised.docx")
		if e != nil {
			result.Error = e.Error()
			return
		}
		t, e := loadTemplate(b)
		if e != nil {
			result.Error = e.Error()
			return
		}
		if e = os.MkdirAll(q.Dir, 0700); e != nil {
			result.Error = e.Error()
			return
		}
		s := &Server{template: t, dir: q.Dir}
		result, e = s.execute(q)
		if e != nil {
			result = Result{Error: e.Error()}
		}
	}()
	json.NewEncoder(out).Encode(result)
}
func main() { runEngine(os.Stdin, os.Stdout) }
