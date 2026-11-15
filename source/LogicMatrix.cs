using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;

public class Fact
{
    public string id { get; set; }
    public string text { get; set; }
    public string sources { get; set; }
    public bool verified { get; set; }
}

public sealed partial class ReportForm
{
    private ToolStripMenuItem matrixMenu;
    private ToolStripMenuItem draftExportMenu;

    private void OpenMatrixFromToolbar()
    {
        if (draft == null) NewDraft();
        else ShowLogicMatrix();
    }

    private void AddMatrixCommands(ToolStripMenuItem file)
    {
        matrixMenu = new ToolStripMenuItem("Report logic &matrix…", null, delegate { Guard(ShowLogicMatrix); });
        draftExportMenu = new ToolStripMenuItem("Export &confidential draft…", null, delegate { Guard(ExportConfidentialDraft); });
        file.DropDownItems.Add(matrixMenu);
        file.DropDownItems.Add(draftExportMenu);
    }

    private void ShowLogicMatrix()
    {
        if (draft == null) return;
        bool openDiscussion = false;
        using (var dialog = new Form { Text = "Report Logic Matrix", Size = new Size(960, 620),
            StartPosition = FormStartPosition.CenterParent, MinimumSize = new Size(760, 480), Font = Font })
        {
            var tabs = new TabControl { Dock = DockStyle.Fill };
            var factsPage = new TabPage("Facts and sources");
            var findingsPage = new TabPage("Findings");
            var recommendationsPage = new TabPage("Recommendations");
            var reviewPage = new TabPage("Review links");
            tabs.TabPages.Add(factsPage);
            tabs.TabPages.Add(findingsPage);
            tabs.TabPages.Add(recommendationsPage);
            tabs.TabPages.Add(reviewPage);
            dialog.Controls.Add(tabs);
            var navigation = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 48 };
            dialog.Controls.Add(navigation);
            var openReport = AddButton(navigation, "Open report", delegate { dialog.Close(); });
            AddButton(navigation, "Add verified facts to Discussion…", delegate {
                Guard(delegate {
                    if (!AddFactsToDiscussion(dialog)) return;
                    openDiscussion = true;
                    dialog.Close();
                });
            });
            var findingEditor = AddMatrixEditor(findingsPage);
            var recommendationEditor = AddMatrixEditor(recommendationsPage);
            Action refreshFindings = null;
            Action refreshRecommendations = null;
            refreshFindings = delegate { RefreshMatrixEditor(findingEditor, delegate { RenderFindings(findingEditor, refreshFindings); }); };
            refreshRecommendations = delegate { RefreshMatrixEditor(recommendationEditor, delegate { RenderRecommendations(recommendationEditor, refreshRecommendations); }); };
            var facts = new ListBox { Dock = DockStyle.Fill, AccessibleName = "Recorded facts", HorizontalScrollbar = true };
            var commands = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 48 };
            factsPage.Controls.Add(facts);
            factsPage.Controls.Add(commands);

            Action refresh = delegate {
                int selected = facts.SelectedIndex;
                facts.Items.Clear();
                for (int i = 0; i < draft.facts.Count; i++)
                    facts.Items.Add("Fact " + (i + 1) + (draft.facts[i].verified ? " (verified)  " : " (unverified)  ") + draft.facts[i].text);
                if (facts.Items.Count > 0) facts.SelectedIndex = Math.Max(0, Math.Min(selected, facts.Items.Count - 1));
            };
            AddButton(commands, "Add fact…", delegate {
                var fact = new Fact { id = ID() };
                if (!EditFact(dialog, fact)) return;
                draft.facts.Add(fact);
                Changed();
                refresh();
                facts.SelectedIndex = facts.Items.Count - 1;
            });
            AddButton(commands, "Edit fact…", delegate {
                if (facts.SelectedIndex < 0) return;
                Fact fact = draft.facts[facts.SelectedIndex];
                string oldText = fact.text;
                string oldSources = fact.sources;
                bool wasVerified = fact.verified;
                if (!EditFact(dialog, fact)) return;
                ReviewFindingsAfterFactEdit(fact, oldText, oldSources, wasVerified);
                Changed();
                refresh();
            });
            AddButton(commands, "Remove fact", delegate {
                if (facts.SelectedIndex < 0) return;
                Fact fact = draft.facts[facts.SelectedIndex];
                if (draft.findings.Any(f => f.factIds.Contains(fact.id)))
                {
                    MessageBox.Show(dialog, "Unlink this fact from its findings before removing it.");
                    return;
                }
                if (MessageBox.Show(dialog, "Remove this fact and its source references?", "Remove fact",
                    MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
                draft.facts.Remove(fact);
                Changed();
                refresh();
            });
            var findingPicker = new ComboBox { Dock = DockStyle.Top, DropDownStyle = ComboBoxStyle.DropDownList,
                AccessibleName = "Finding to review" };
            var detail = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 3, RowCount = 2, Padding = new Padding(8) };
            var columns = new TextBox[3];
            string[] labels = { "Facts and sources", "Finding", "Recommendations" };
            for (int i = 0; i < 3; i++)
            {
                detail.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f / 3));
                detail.Controls.Add(new Label { Text = labels[i], AutoSize = true }, i, 0);
                columns[i] = new TextBox { Dock = DockStyle.Fill, Multiline = true, ReadOnly = true,
                    ScrollBars = ScrollBars.Vertical, AccessibleName = labels[i] };
                detail.Controls.Add(columns[i], i, 1);
            }
            detail.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            detail.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            reviewPage.Controls.Add(detail);
            reviewPage.Controls.Add(findingPicker);
            findingPicker.SelectedIndexChanged += delegate {
                int index = findingPicker.SelectedIndex;
                if (index < 0) return;
                Finding finding = draft.findings[index];
                var supporting = draft.facts.Where(f => finding.factIds.Contains(f.id)).ToList();
                columns[0].Text = supporting.Count == 0 ? "No linked facts." : String.Join("\r\n\r\n", supporting.Select(f =>
                    "Fact " + (draft.facts.IndexOf(f) + 1) + (f.verified ? " (verified)" : " (unverified)") +
                    "\r\n" + f.text + "\r\nSources: " + f.sources));
                int verifiedCount = supporting.Where(IsVerifiedFact).Select(f => f.id).Distinct().Count();
                columns[1].Text = "F" + (index + 1) + "\r\n" + finding.text +
                    "\r\n\r\nVerified supporting facts: " + verifiedCount +
                    (verifiedCount < 2 ? " (CGJA recommends at least two)" : "") +
                    (finding.verified ? "" : "\r\nFinding needs author review.");
                var recommendations = draft.recommendations.Where(r => r.findingIds.Contains(finding.id)).ToList();
                columns[2].Text = recommendations.Count > 0
                    ? String.Join("\r\n\r\n", recommendations.Select(r => "R" + (draft.recommendations.IndexOf(r) + 1) +
                        "\r\n" + r.owner + "\r\n" + r.action + "\r\nBy: " + r.due))
                    : (finding.noRecommendation ? "Reviewed: no recommendation needed." : "No recommendation linked.");
            };
            tabs.SelectedIndexChanged += delegate {
                if (tabs.SelectedTab == findingsPage) refreshFindings();
                if (tabs.SelectedTab == recommendationsPage) refreshRecommendations();
                if (tabs.SelectedTab != reviewPage) return;
                int selected = findingPicker.SelectedIndex;
                findingPicker.Items.Clear();
                for (int i = 0; i < draft.findings.Count; i++) findingPicker.Items.Add("Finding F" + (i + 1));
                if (findingPicker.Items.Count > 0) findingPicker.SelectedIndex = Math.Max(0, Math.Min(selected, findingPicker.Items.Count - 1));
                else
                {
                    columns[0].Clear();
                    columns[1].Text = "Add a finding to review its links.";
                    columns[2].Clear();
                }
            };
            refresh();
            bool openedOnFacts = false;
            if (testMode)
            {
                dialog.Shown += delegate {
                    openedOnFacts = tabs.SelectedTab == factsPage;
                    tabs.SelectedTab = findingsPage;
                    tabs.SelectedTab = recommendationsPage;
                    tabs.SelectedTab = reviewPage;
                    openReport.PerformClick();
                };
            }
            dialog.ShowDialog(this);
            if (testMode && !openedOnFacts) throw new InvalidOperationException("The matrix did not open on Facts and sources.");
        }
        Save();
        if (openDiscussion)
            Navigate(1 + template.sections.FindIndex(section => section.id == "discussion"));
        else
            Render();
    }

    private FlowLayoutPanel AddMatrixEditor(TabPage page)
    {
        var panel = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoScroll = true,
            WrapContents = false, FlowDirection = FlowDirection.TopDown, Padding = new Padding(10) };
        page.Controls.Add(panel);
        panel.SizeChanged += delegate { SizeMatrixCards(panel); };
        return panel;
    }

    private static void SizeMatrixCards(FlowLayoutPanel panel)
    {
        foreach (FlowLayoutPanel card in panel.Controls.OfType<FlowLayoutPanel>())
        {
            card.AutoSize = false;
            card.Width = Math.Max(300, panel.ClientSize.Width - 44);
            card.Height = card.GetPreferredSize(new Size(card.Width, 0)).Height;
        }
    }

    private static void RefreshMatrixEditor(FlowLayoutPanel panel, Action render)
    {
        panel.SuspendLayout();
        try
        {
            while (panel.Controls.Count > 0) panel.Controls[0].Dispose();
            render();
            SizeMatrixCards(panel);
        }
        finally { panel.ResumeLayout(true); }
    }

    private static bool IsVerifiedFact(Fact fact)
    {
        return fact.verified && !Blank(fact.text) && !Blank(fact.sources);
    }

    private void ReviewFindingsAfterFactEdit(Fact fact, string oldText, string oldSources, bool wasVerified)
    {
        if (oldText == fact.text && oldSources == fact.sources && (!wasVerified || fact.verified)) return;
        foreach (Finding finding in draft.findings.Where(f => f.factIds.Contains(fact.id)))
            finding.verified = false;
    }

    private bool AddFactsToDiscussion(Form owner)
    {
        var eligible = draft.facts.Where(IsVerifiedFact).ToList();
        if (eligible.Count == 0)
        {
            MessageBox.Show(owner, "Verify a sourced fact in the Report Logic Matrix first.");
            return false;
        }

        using (var dialog = new Form { Text = "Add verified facts to Discussion", Size = new Size(740, 480),
            StartPosition = FormStartPosition.CenterParent, MinimumSize = new Size(540, 390), Font = Font })
        {
            var instructions = new Label { Dock = DockStyle.Top, Height = 48,
                Text = "Select fact statements suitable for the report. They will be appended to Discussion. Source references stay in the matrix." };
            var list = new CheckedListBox { Dock = DockStyle.Fill, CheckOnClick = true,
                AccessibleName = "Verified fact statements", HorizontalScrollbar = true };
            var preview = new TextBox { Dock = DockStyle.Bottom, Height = 104, Multiline = true, ReadOnly = true,
                ScrollBars = ScrollBars.Vertical, AccessibleName = "Selected fact statement" };
            var commands = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 46 };
            dialog.Controls.Add(list);
            dialog.Controls.Add(preview);
            dialog.Controls.Add(commands);
            dialog.Controls.Add(instructions);
            foreach (Fact fact in eligible)
                list.Items.Add("Fact " + (draft.facts.IndexOf(fact) + 1) + ": " + fact.text.Replace("\r", " ").Replace("\n", " "));
            list.SelectedIndexChanged += delegate { preview.Text = list.SelectedIndex < 0 ? "" : eligible[list.SelectedIndex].text; };
            list.SelectedIndex = 0;
            var append = AddButton(commands, "Append selected statements", delegate {
                if (list.CheckedIndices.Count == 0) return;
                AppendDiscussionFacts(list.CheckedIndices.Cast<int>().Select(i => eligible[i]));
                dialog.DialogResult = DialogResult.OK;
            });
            append.Enabled = false;
            list.ItemCheck += delegate(object sender, ItemCheckEventArgs e) {
                int checkedElsewhere = list.CheckedIndices.Cast<int>().Count(i => i != e.Index);
                append.Enabled = checkedElsewhere > 0 || e.NewValue == CheckState.Checked;
            };
            var cancel = new Button { Text = "Cancel", DialogResult = DialogResult.Cancel, AutoSize = true };
            commands.Controls.Add(cancel);
            dialog.CancelButton = cancel;
            if (dialog.ShowDialog(owner) != DialogResult.OK) return false;
        }
        Save();
        if (owner == this) Render();
        return true;
    }

    private void AppendDiscussionFacts(IEnumerable<Fact> selected)
    {
        string statements = String.Join("\r\n\r\n", selected.Where(IsVerifiedFact).Select(f => f.text));
        if (String.IsNullOrEmpty(statements)) return;
        string discussion = Answer("discussion");
        draft.answers["discussion"] = String.IsNullOrWhiteSpace(discussion)
            ? statements : discussion + "\r\n\r\n" + statements;
        Changed();
    }

    internal void TestMatrixFactTransfer()
    {
        Fact fact = draft.facts.Single();
        Finding finding = draft.findings.Single();
        string original = Answer("discussion");
        AppendDiscussionFacts(new[] { fact, new Fact { text = "Unverified statement", verified = false } });
        string appended = Answer("discussion");
        if (appended != original + "\r\n\r\n" + fact.text)
            throw new InvalidOperationException("Discussion transfer did not preserve the original prose or exclude source notes and unverified text.");
        ReviewFindingsAfterFactEdit(fact, fact.text, fact.sources, fact.verified);
        if (!finding.verified) throw new InvalidOperationException("Saving an unchanged fact reset the finding.");
        string sources = fact.sources;
        fact.sources += "\r\nSynthetic additional source";
        ReviewFindingsAfterFactEdit(fact, fact.text, sources, true);
        if (finding.verified || Answer("discussion") != appended)
            throw new InvalidOperationException("Changed support must flag its finding and preserve Discussion.");
        draft.answers["discussion"] = original;
        fact.sources = sources;
        finding.verified = true;
        Changed();
    }

    private bool EditFact(Form owner, Fact fact)
    {
        using (var dialog = new Form { Text = "Fact and source references", Size = new Size(640, 435),
            StartPosition = FormStartPosition.CenterParent, Font = Font })
        {
            var panel = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown,
                WrapContents = false, Padding = new Padding(10), AutoScroll = true };
            dialog.Controls.Add(panel);
            panel.Controls.Add(new Label { Text = "Fact", AutoSize = true });
            var statement = new TextBox { Text = fact.text, Multiline = true, Width = 570, Height = 92,
                AccessibleName = "Fact statement", ScrollBars = ScrollBars.Vertical };
            panel.Controls.Add(statement);
            panel.Controls.Add(new Label { Text = "Source references (one per line)", AutoSize = true });
            var sources = new TextBox { Text = fact.sources, Multiline = true, Width = 570, Height = 104,
                AccessibleName = "Source references", ScrollBars = ScrollBars.Vertical };
            panel.Controls.Add(sources);
            var verified = new CheckBox { Text = "I checked this fact against its sources.", Checked = fact.verified, AutoSize = true };
            statement.TextChanged += delegate { verified.Checked = false; };
            sources.TextChanged += delegate { verified.Checked = false; };
            panel.Controls.Add(verified);
            var done = AddButton(panel, "Save fact", delegate {
                if (Blank(statement.Text) || (verified.Checked && Blank(sources.Text)))
                {
                    MessageBox.Show(dialog, "Enter a fact statement and list its sources before marking it verified.");
                    return;
                }
                dialog.DialogResult = DialogResult.OK;
            });
            var cancel = new Button { Text = "Cancel", DialogResult = DialogResult.Cancel, AutoSize = true };
            panel.Controls.Add(cancel);
            dialog.CancelButton = cancel;
            dialog.AcceptButton = done;
            if (dialog.ShowDialog(owner) != DialogResult.OK) return false;
            fact.text = statement.Text.Trim();
            fact.sources = sources.Text.Trim();
            fact.verified = verified.Checked;
            return true;
        }
    }

    private void AddFindingFactLinks(FlowLayoutPanel card, Finding finding, CheckBox verification)
    {
        Note(card, "Supporting facts", true);
        if (draft.facts.Count == 0) Note(card, "Record facts and sources in the Report Logic Matrix.");
        for (int i = 0; i < draft.facts.Count; i++)
        {
            Fact fact = draft.facts[i];
            string summary = (fact.text ?? "").Replace("\r", " ").Replace("\n", " ");
            if (summary.Length > 95) summary = summary.Substring(0, 92) + "…";
            var link = new CheckBox { Text = "Fact " + (i + 1) + ": " + summary,
                Checked = finding.factIds.Contains(fact.id), AutoSize = false, Height = 42 };
            link.CheckedChanged += delegate {
                if (link.Checked) finding.factIds.Add(fact.id);
                else finding.factIds.RemoveAll(id => id == fact.id);
                finding.verified = false;
                verification.Checked = false;
                Changed();
            };
            card.Controls.Add(link);
        }
        var reviewed = new CheckBox { Text = "Reviewed and no recommendation is needed.",
            Checked = finding.noRecommendation, AutoSize = true };
        reviewed.CheckedChanged += delegate { finding.noRecommendation = reviewed.Checked; Changed(); };
        card.Controls.Add(reviewed);
    }

    private void ShowLogicWarnings()
    {
        Note(fields, "Report logic matrix review", true);
        for (int i = 0; i < draft.findings.Count; i++)
        {
            Finding finding = draft.findings[i];
            string number = "F" + (i + 1);
            int count = draft.facts.Where(f => IsVerifiedFact(f) &&
                finding.factIds.Contains(f.id)).Select(f => f.id).Distinct().Count();
            if (count < 2) Note(fields, number + " has " + count + " linked verified facts. CGJA recommends at least two per finding.");
            if (!draft.recommendations.Any(r => r.findingIds.Contains(finding.id)))
                Note(fields, number + (finding.noRecommendation ? " was reviewed and needs no recommendation." : " has no linked recommendation. Review whether one is needed."));
        }
        AddButton(fields, "Open report logic matrix…", delegate { Guard(ShowLogicMatrix); });
    }

    private void ExportConfidentialDraft()
    {
        if (draft == null) return;
        using (var dialog = new SaveFileDialog { Title = "Export confidential Word draft",
            Filter = "Word document (*.docx)|*.docx", DefaultExt = "docx", AddExtension = true,
            OverwritePrompt = true, FileName = SafeFilename(draft.title ?? "") + " - Confidential Draft.docx" })
        {
            if (dialog.ShowDialog(this) == DialogResult.OK)
            {
                ExportTo(dialog.FileName, true);
                status.Text = "Confidential Word draft exported.";
            }
        }
    }
}
