using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

public sealed partial class ReportForm
{
    private bool preparingPdf;

    private void AddPdfReviewCommand(ToolStripMenuItem file)
    {
        file.DropDownItems.Add(new ToolStripMenuItem("Prepare PDF for &review…", null, PreparePdfForReview));
        file.DropDownItems.Add(new ToolStripMenuItem("Prepare PDF for &publication…", null,
            delegate { PreparePdf(true); }));
        FormClosing += delegate(object sender, FormClosingEventArgs args)
        {
            if (preparingPdf) args.Cancel = true;
        };
    }

    private void PreparePdfForReview(object sender, EventArgs args)
    {
        PreparePdf(false);
    }

    private async void PreparePdf(bool publication)
    {
        if (preparingPdf) return;
        string purpose = publication ? "publication" : "review";
        string preparedTitle = "PDF prepared for " + purpose;
        try
        {
            string document;
            using (var picker = new OpenFileDialog
            {
                Title = "Choose the finished Word report",
                Filter = "Word reports (*.docx)|*.docx",
                CheckFileExists = true
            })
            {
                if (picker.ShowDialog(this) != DialogResult.OK) return;
                document = picker.FileName;
            }

            string destination;
            using (var picker = new SaveFileDialog
            {
                Title = "Save the PDF for " + purpose,
                InitialDirectory = Path.GetDirectoryName(document),
                FileName = Path.GetFileNameWithoutExtension(document) + (publication ? " - Publication.pdf" : " - Review.pdf"),
                Filter = "PDF files (*.pdf)|*.pdf",
                DefaultExt = "pdf",
                AddExtension = true,
                OverwritePrompt = true
            })
            {
                if (picker.ShowDialog(this) != DialogResult.OK) return;
                destination = picker.FileName;
            }

            if (!Path.GetExtension(destination).Equals(".pdf", StringComparison.OrdinalIgnoreCase))
                throw new IOException("Choose a file name ending in .pdf.");

            preparingPdf = true;
            Enabled = false;
            UseWaitCursor = true;
            status.Text = "Preparing the PDF on this PC…";
            int[] linkPages = await PdfReview.PrepareAsync(document, destination, publication);
            status.Text = preparedTitle;
            string linkNote = linkPages.Length == 0 ? "" :
                "\n\nCheck link descriptions on these PDF pages: " + String.Join(", ", linkPages) + ".";
            MessageBox.Show(this, "Open the saved PDF in Acrobat Pro. Run Check for accessibility and complete the "
                + "manual checks. In Print Production → Preflight, run Verify compliance with PDF/UA-1 (syntax checks only)."
                + linkNote + "\n\n" + destination,
                preparedTitle, MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception error)
        {
            status.Text = "PDF preparation did not finish.";
            MessageBox.Show(this, error.Message, "Prepare PDF for " + purpose, MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
        finally
        {
            preparingPdf = false;
            UseWaitCursor = false;
            Enabled = true;
        }
    }
}

internal static class PdfReview
{
    public sealed class PreparationResult
    {
        public bool ok { get; set; }
        public string message { get; set; }
        public int[] linkPages { get; set; }
    }

    internal static Task<int[]> PrepareAsync(string document, string destination, bool publication)
    {
        var completion = new TaskCompletionSource<int[]>();
        var worker = new Thread(delegate()
        {
            try
            {
                completion.SetResult(Prepare(document, destination, publication));
            }
            catch (Exception error) { completion.SetException(error); }
        }) { IsBackground = true };
        worker.SetApartmentState(ApartmentState.STA);
        worker.Start();
        return completion.Task;
    }

    private static int[] Prepare(string document, string destination, bool publication)
    {
        string working = Path.Combine(Path.GetTempPath(), "ReportInterview-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(working);
        string staged = null;
        try
        {
            string taggedPdf = Path.Combine(working, "word.pdf");
            string candidate = Path.Combine(working, "candidate.pdf");
            string source = document;
            if (publication)
            {
                source = Path.Combine(working, Path.GetFileName(document));
                RunPdfHelper(source, "--publication-word-copy", document, source);
            }
            ExportTaggedPdf(source, taggedPdf);
            int[] linkPages = RunPdfHelper(candidate, taggedPdf, candidate, document);

            // Stage next to the destination so the prepared file can be moved or replaced atomically.
            staged = Path.Combine(Path.GetDirectoryName(destination), Guid.NewGuid().ToString("N") + ".tmp");
            File.Copy(candidate, staged);
            if (File.Exists(destination)) File.Replace(staged, destination, null);
            else File.Move(staged, destination);
            return linkPages;
        }
        finally
        {
            try { if (staged != null) File.Delete(staged); } catch (IOException) { } catch (UnauthorizedAccessException) { }
            try { Directory.Delete(working, true); } catch (IOException) { } catch (UnauthorizedAccessException) { }
        }
    }

    private static void ExportTaggedPdf(string source, string output)
    {
        Type wordType = Type.GetTypeFromProgID("Word.Application");
        if (wordType == null)
            throw new IOException("Desktop Microsoft Word is needed to prepare a tagged PDF. Ask the reviewer to install it.");

        dynamic word = null, documents = null, doc = null, options = null;
        bool? updateLinks = null;
        try
        {
            word = Activator.CreateInstance(wordType);
            word.Visible = false;
            word.DisplayAlerts = 0;
            word.AutomationSecurity = 3; // msoAutomationSecurityForceDisable
            options = word.Options;
            updateLinks = (bool)options.UpdateLinksAtOpen;
            options.UpdateLinksAtOpen = false;
            documents = word.Documents;
            doc = documents.Open(FileName: source, ReadOnly: true, AddToRecentFiles: false, Visible: false);
            doc.ExportAsFixedFormat(OutputFileName: output, ExportFormat: 17, OpenAfterExport: false,
                Item: 0, IncludeDocProps: true, KeepIRM: true, CreateBookmarks: 1, DocStructureTags: true, UseISO19005_1: false);
        }
        catch (COMException error)
        {
            throw new IOException("Word could not export the report. Save it as a local .docx in desktop Word, "
                + "close it, and then try again.", error);
        }
        finally
        {
            try
            {
                try { if (doc != null) doc.Close(SaveChanges: 0); }
                finally { if (updateLinks.HasValue) options.UpdateLinksAtOpen = updateLinks.Value; }
            }
            finally
            {
                try { if (word != null) word.Quit(SaveChanges: 0); }
                finally
                {
                    foreach (object value in new object[] { doc, documents, options, word })
                        if (value != null) Marshal.FinalReleaseComObject(value);
                }
            }
        }
    }

    private static int[] RunPdfHelper(string outputPath, params string[] arguments)
    {
        string helper = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "ReportPdf.exe");
        var start = new ProcessStartInfo(helper, String.Join(" ", arguments
            .Select(path => "\"" + path + "\"")))
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            StandardOutputEncoding = Encoding.UTF8
        };
        using (Process process = Process.Start(start))
        {
            Task<string> output = process.StandardOutput.ReadToEndAsync();
            if (!process.WaitForExit(60000))
            {
                process.Kill();
                throw new IOException("PDF preparation took too long. Try again or ask the reviewer for help.");
            }
            PreparationResult result;
            try { result = new JavaScriptSerializer().Deserialize<PreparationResult>(output.Result); }
            catch (ArgumentException) { result = null; }
            catch (InvalidOperationException) { result = null; }
            if (result == null)
                throw new IOException("The local PDF helper did not return a result. Ask the reviewer to check the installation.");
            if (!result.ok || process.ExitCode != 0)
                throw new IOException(result.message ?? "The local PDF helper could not prepare the report.");
            if (result.linkPages == null || !File.Exists(outputPath))
                throw new IOException("The local PDF helper did not finish preparing the report.");
            return result.linkPages;
        }
    }
}
