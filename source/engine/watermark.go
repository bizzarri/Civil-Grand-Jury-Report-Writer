package main

// The template already uses a repeating footer. Anchor the background shape
// there so it appears on each page without adding a header or changing margins.
const confidentialWatermark = `<w:r><w:pict>
<v:shapetype id="ReportDraftText" coordsize="21600,21600" o:spt="136" adj="10800" path="m@7,l@8,m@5,21600l@6,21600e">
<v:formulas>
<v:f eqn="sum #0 0 10800"/><v:f eqn="prod #0 2 1"/><v:f eqn="sum 21600 0 @1"/>
<v:f eqn="sum 0 0 @2"/><v:f eqn="sum 21600 0 @3"/><v:f eqn="if @0 @3 0"/>
<v:f eqn="if @0 21600 @1"/><v:f eqn="if @0 0 @2"/><v:f eqn="if @0 @4 21600"/>
</v:formulas><v:path textpathok="t"/><v:textpath on="t" fitshape="t"/>
</v:shapetype>
<v:shape id="ReportConfidentialDraft" type="#ReportDraftText" fillcolor="#dddddd" stroked="f"
style="position:absolute;width:440pt;height:65pt;rotation:315;z-index:-251654144;mso-position-horizontal:center;mso-position-horizontal-relative:page;mso-position-vertical:center;mso-position-vertical-relative:page">
<v:textpath on="t" fitshape="t" style="font-family:Arial;font-size:1pt" string="CONFIDENTIAL DRAFT"/>
<w10:wrap type="none"/>
</v:shape></w:pict></w:r>`
