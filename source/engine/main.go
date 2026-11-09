package main

import (
	"archive/zip"
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"encoding/json"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

//go:embed template/revised.docx
var assets embed.FS

const wordNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

type Block struct {
	Start, End       int
	Style, Text, Raw string
}
type Section struct {
	ID       string   `json:"id"`
	Title    string   `json:"title"`
	Guidance []string `json:"guidance"`
	Optional bool     `json:"optional"`
	blocks   []Block
	heading  string
}
type Template struct {
	Hash           string    `json:"hash"`
	Sections       []Section `json:"sections"`
	Instructions   []string  `json:"instructions"`
	data           []byte
	document       string
	prefix, suffix string
}
type Finding struct {
	ID       string `json:"id"`
	Text     string `json:"text"`
	Evidence string `json:"evidence"`
	Verified bool   `json:"verified"`
}
type Recommendation struct {
	ID         string   `json:"id"`
	Action     string   `json:"action"`
	Owner      string   `json:"owner"`
	Due        string   `json:"due"`
	FindingIDs []string `json:"findingIds"`
}
type Draft struct {
	ID              string            `json:"id"`
	Revision        int               `json:"revision"`
	TemplateHash    string            `json:"templateHash"`
	Title           string            `json:"title"`
	County          string            `json:"county"`
	Term            string            `json:"term"`
	ReleaseDate     string            `json:"releaseDate"`
	Updated         string            `json:"updated"`
	Current         int               `json:"current"`
	Answers         map[string]string `json:"answers"`
	Findings        []Finding         `json:"findings"`
	Recommendations []Recommendation  `json:"recommendations"`
}
type Server struct {
	template *Template
	dir      string
	token    string
}

var safeID = regexp.MustCompile(`^[a-f0-9]{32}$`)

func newID() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b)
}
func esc(s string) string { var b bytes.Buffer; xml.EscapeText(&b, []byte(s)); return b.String() }
func attr(s xml.StartElement, name string) string {
	for _, a := range s.Attr {
		if a.Name.Local == name {
			return a.Value
		}
	}
	return ""
}

// Offsets refer to the original XML bytes. Unmodified package parts are copied verbatim.
func readBlocks(doc string) ([]Block, error) {
	d := xml.NewDecoder(strings.NewReader(doc))
	depth := 0
	bodyDepth := -1
	start := -1
	var b Block
	var blocks []Block
	inText := false
	for {
		before := int(d.InputOffset())
		t, e := d.Token()
		if e == io.EOF {
			break
		}
		if e != nil {
			return nil, e
		}
		switch v := t.(type) {
		case xml.StartElement:
			depth++
			if v.Name.Space == wordNS && v.Name.Local == "body" {
				bodyDepth = depth
			}
			if bodyDepth > 0 && depth == bodyDepth+1 {
				start = before
				b = Block{Start: start}
			}
			if start >= 0 {
				if v.Name.Local == "pStyle" {
					b.Style = attr(v, "val")
				}
				if v.Name.Local == "t" {
					inText = true
				}
			}
		case xml.CharData:
			if start >= 0 && inText {
				b.Text += string(v)
			}
		case xml.EndElement:
			if v.Name.Local == "t" {
				inText = false
			}
			if start >= 0 && depth == bodyDepth+1 {
				b.End = int(d.InputOffset())
				b.Raw = doc[start:b.End]
				blocks = append(blocks, b)
				start = -1
			}
			if depth == bodyDepth {
				bodyDepth = -1
			}
			depth--
		}
	}
	return blocks, nil
}
func loadTemplate(data []byte) (*Template, error) {
	z, e := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if e != nil {
		return nil, e
	}
	var doc string
	for _, f := range z.File {
		if f.Name == "word/document.xml" {
			r, e := f.Open()
			if e != nil {
				return nil, e
			}
			b, e := io.ReadAll(io.LimitReader(r, 8<<20))
			r.Close()
			if e != nil {
				return nil, e
			}
			doc = string(b)
		}
	}
	if doc == "" {
		return nil, errors.New("Word document.xml missing")
	}
	blocks, e := readBlocks(doc)
	if e != nil {
		return nil, e
	}
	sum := sha256.Sum256(data)
	t := &Template{Hash: hex.EncodeToString(sum[:]), data: data, document: doc}
	current := -1
	checklist := false
	for _, b := range blocks {
		if b.Style == "Heading1" {
			if b.Text == "Author instructions and publication checklist" {
				checklist = true
				current = -1
				continue
			}
			if !checklist {
				id := strings.ToLower(strings.ReplaceAll(b.Text, " ", "-"))
				t.Sections = append(t.Sections, Section{ID: id, Title: b.Text, Optional: strings.Contains("|GLOSSARY|INVITED RESPONSES|BIBLIOGRAPHY|APPENDIX|DISCLAIMER|", "|"+b.Text+"|"), heading: b.Raw})
				current = len(t.Sections) - 1
			}
		}
		if checklist {
			if b.Text != "" {
				t.Instructions = append(t.Instructions, b.Text)
			}
			continue
		}
		if current >= 0 {
			t.Sections[current].blocks = append(t.Sections[current].blocks, b)
			if b.Style == "TemplateInstruction" || (b.Text != "" && !strings.Contains(b.Text, "[Highlight") && b.Style != "Heading1") {
				t.Sections[current].Guidance = append(t.Sections[current].Guidance, b.Text)
			}
		}
	}
	if len(t.Sections) != 12 {
		return nil, fmt.Errorf("expected revised CGJA template with 12 report sections; got %d", len(t.Sections))
	}
	first := t.Sections[0].blocks[0].Start
	t.prefix = doc[:first]
	for _, b := range blocks {
		if strings.Contains(b.Raw, "<w:sectPr") && strings.HasPrefix(b.Raw, "<w:sectPr") {
			t.suffix = doc[b.Start:]
			break
		}
	}
	if t.suffix == "" {
		return nil, errors.New("template section properties missing")
	}
	return t, nil
}
func para(style, text string) string {
	text = strings.ReplaceAll(strings.ReplaceAll(text, "\r\n", "\n"), "\r", "\n")
	p := "<w:p>"
	if style != "" {
		p += `<w:pPr><w:pStyle w:val="` + esc(style) + `"/></w:pPr>`
	}
	p += "<w:r>"
	for i, line := range strings.Split(text, "\n") {
		if i > 0 {
			p += "<w:br/>"
		}
		p += `<w:t xml:space="preserve">` + esc(line) + `</w:t>`
	}
	return p + "</w:r></w:p>"
}
func paragraphs(style, text string) string {
	text = strings.ReplaceAll(strings.ReplaceAll(text, "\r\n", "\n"), "\r", "\n")
	var s strings.Builder
	for _, p := range strings.Split(strings.TrimSpace(text), "\n\n") {
		if strings.TrimSpace(p) != "" {
			s.WriteString(para(style, p))
		}
	}
	return s.String()
}
func (t *Template) export(d Draft) ([]byte, error) {
	if e := validate(d, t); e != nil {
		return nil, e
	}
	var out strings.Builder
	// Retain the original XML declaration, namespaces and body opening; replace cover slots.
	prefixBlocks, e := readBlocks(t.document)
	if e != nil {
		return nil, e
	}
	first := prefixBlocks[0].Start
	out.WriteString(t.document[:first])
	out.WriteString(para("Subtitle", d.Term+" "+d.County+" County Grand Jury"))
	out.WriteString(para("Subtitle", "PUBLIC RELEASE DATE: "+d.ReleaseDate))
	out.WriteString(para("Title", d.Title))
	findingIndex := map[string]int{}
	for i, f := range d.Findings {
		findingIndex[f.ID] = i + 1
	}
	for _, s := range t.Sections {
		answer := strings.TrimSpace(d.Answers[s.ID])
		if s.Optional && answer == "" {
			continue
		}
		out.WriteString(s.heading)
		switch s.ID {
		case "findings":
			for i, f := range d.Findings {
				p := para("Finding", f.Text)
				at := strings.Index(p, "<w:r>")
				p = p[:at] + fmt.Sprintf(`<w:bookmarkStart w:id="%d" w:name="Finding_%s"/>`, 1000+i, f.ID) + p[at:]
				p = strings.Replace(p, "</w:p>", fmt.Sprintf(`<w:bookmarkEnd w:id="%d"/></w:p>`, 1000+i), 1)
				out.WriteString(p)
			}
		case "recommendations":
			out.WriteString(para("", "The Grand Jury recommends that:"))
			for _, r := range d.Recommendations {
				out.WriteString(para("Recommendation", r.Owner+": "+r.Action+" By: "+r.Due+"."))
				out.WriteString(`<w:p><w:r><w:t xml:space="preserve">Related findings: </w:t></w:r>`)
				for j, id := range r.FindingIDs {
					if j > 0 {
						out.WriteString(`<w:r><w:t xml:space="preserve">, </w:t></w:r>`)
					}
					out.WriteString(`<w:hyperlink w:anchor="Finding_` + id + `" w:history="1"><w:r><w:rPr><w:rStyle w:val="Hyperlink"/></w:rPr><w:t>` + fmt.Sprintf("F%d", findingIndex[id]) + `</w:t></w:r></w:hyperlink>`)
				}
				out.WriteString(`</w:p>`)
			}
		default:
			style := ""
			if s.ID == "glossary" {
				style = "GlossaryTerm"
			}
			if s.ID == "bibliography" {
				style = "ListBullet"
			}
			out.WriteString(paragraphs(style, answer))
		}
	}
	out.WriteString(t.suffix)
	z, e := zip.NewReader(bytes.NewReader(t.data), int64(len(t.data)))
	if e != nil {
		return nil, e
	}
	var buf bytes.Buffer
	w := zip.NewWriter(&buf)
	for _, f := range z.File {
		r, e := f.Open()
		if e != nil {
			return nil, e
		}
		b, e := io.ReadAll(r)
		r.Close()
		if e != nil {
			return nil, e
		}
		if f.Name == "word/document.xml" {
			b = []byte(out.String())
		}
		if f.Name == "docProps/core.xml" {
			re := regexp.MustCompile(`(?s)<dc:title(?:\s[^>]*)?>.*?</dc:title>|<dc:title\s*/>`)
			b = re.ReplaceAll(b, []byte("<dc:title>"+esc(d.Title)+"</dc:title>"))
		}
		h := f.FileHeader
		dst, e := w.CreateHeader(&h)
		if e != nil {
			return nil, e
		}
		if _, e = dst.Write(b); e != nil {
			return nil, e
		}
	}
	if e = w.Close(); e != nil {
		return nil, e
	}
	return buf.Bytes(), nil
}
func validate(d Draft, t *Template) error {
	if d.TemplateHash != t.Hash {
		return errors.New("draft uses a different template")
	}
	if strings.TrimSpace(d.Title) == "" || strings.TrimSpace(d.County) == "" || strings.TrimSpace(d.Term) == "" || strings.TrimSpace(d.ReleaseDate) == "" {
		return errors.New("complete title, county, jury term and release date")
	}
	for _, id := range []string{"summary", "background", "methodology", "discussion", "required-responses"} {
		if strings.TrimSpace(d.Answers[id]) == "" {
			return fmt.Errorf("complete %s", id)
		}
	}
	if len(d.Findings) == 0 || len(d.Recommendations) == 0 {
		return errors.New("enter at least one finding and recommendation")
	}
	seen := map[string]bool{}
	for _, f := range d.Findings {
		if !safeID.MatchString(f.ID) || seen[f.ID] {
			return errors.New("invalid or duplicate finding ID")
		}
		seen[f.ID] = true
		if strings.TrimSpace(f.Text) == "" || strings.TrimSpace(f.Evidence) == "" || !f.Verified {
			return errors.New("each finding needs text, an evidence reference and author verification")
		}
	}
	rs := map[string]bool{}
	for _, r := range d.Recommendations {
		if !safeID.MatchString(r.ID) || rs[r.ID] {
			return errors.New("invalid or duplicate recommendation ID")
		}
		rs[r.ID] = true
		if strings.TrimSpace(r.Action) == "" || strings.TrimSpace(r.Owner) == "" || strings.TrimSpace(r.Due) == "" || len(r.FindingIDs) == 0 {
			return errors.New("each recommendation needs action, owner, timing and a linked finding")
		}
		links := map[string]bool{}
		for _, id := range r.FindingIDs {
			if !seen[id] || links[id] {
				return errors.New("invalid or duplicate finding link")
			}
			links[id] = true
		}
	}
	return nil
}
func (s *Server) save(d *Draft) error {
	d.Revision++
	d.Updated = time.Now().UTC().Format(time.RFC3339)
	b, e := json.MarshalIndent(d, "", "  ")
	if e != nil {
		return e
	}
	f, e := os.CreateTemp(s.dir, ".draft-*")
	if e != nil {
		return e
	}
	name := f.Name()
	defer os.Remove(name)
	if e = f.Chmod(0600); e != nil {
		f.Close()
		return e
	}
	if _, e = f.Write(b); e != nil {
		f.Close()
		return e
	}
	if e = f.Sync(); e != nil {
		f.Close()
		return e
	}
	if e = f.Close(); e != nil {
		return e
	}
	return os.Rename(name, filepath.Join(s.dir, d.ID+".json"))
}
