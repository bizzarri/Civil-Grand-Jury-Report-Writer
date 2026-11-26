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
        FormClosing += delegate(object sender, FormClosingEventArgs args)
        {
            if (preparingPdf) args.Cancel = true;
        };
    }

    private async void PreparePdfForReview(object sender, EventArgs args)
    {
        if (preparingPdf) return;
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

            string validator = FindPdfValidator();
            if (validator == null) return;

            string destination;
            using (var picker = new SaveFileDialog
            {
                Title = "Save the PDF for accessibility review",
                InitialDirectory = Path.GetDirectoryName(document),
                FileName = Path.GetFileNameWithoutExtension(document) + " - Review.pdf",
                Filter = "PDF files (*.pdf)|*.pdf",
                DefaultExt = "pdf",
                AddExtension = true,
                OverwritePrompt = true
            })
            {
                if (picker.ShowDialog(this) != DialogResult.OK) return;
                destination = picker.FileName;
            }

            preparingPdf = true;
            Enabled = false;
            UseWaitCursor = true;
            status.Text = "Preparing and checking the PDF on this PC…";
            await PdfReview.PrepareAsync(document, destination, validator);
            status.Text = "PDF ready for accessibility review";
            MessageBox.Show(this, "The PDF passed the automated checks and is ready for accessibility review. "
                + "Have the reviewer check reading order, tables and links before publication.\n\n"
                + destination, "PDF ready for accessibility review", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception error)
        {
            status.Text = "PDF preparation did not finish.";
            MessageBox.Show(this, error.Message, "Prepare PDF for review", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
        finally
        {
            preparingPdf = false;
            UseWaitCursor = false;
            Enabled = true;
        }
    }

    private string FindPdfValidator()
    {
        string settings = Path.Combine(engine.DataDir, "verapdf-path.txt");
        if (File.Exists(settings))
        {
            string saved = File.ReadAllText(settings).Trim();
            if (PdfReview.IsValidator(saved)) return saved;
        }
        foreach (string folder in new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "veraPDF", "bin"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "veraPDF", "bin")
        })
        {
            if (!Directory.Exists(folder)) continue;
            string[] candidates = Directory.GetFiles(folder, "cli-*.jar");
            if (candidates.Length == 1) return candidates[0];
        }
        MessageBox.Show(this, "One-time setup for the reviewer. Select the veraPDF command-line JAR "
            + "(cli-*.jar) in the bin folder of the official veraPDF installation. If veraPDF is missing, "
            + "cancel and ask the reviewer to install it with the command-line component.",
            "Set up the local accessibility checker", MessageBoxButtons.OK, MessageBoxIcon.Information);
        using (var picker = new OpenFileDialog
        {
            Title = "Choose the veraPDF command-line JAR",
            Filter = "veraPDF command-line JAR (cli-*.jar)|cli-*.jar",
            CheckFileExists = true
        })
        {
            if (picker.ShowDialog(this) != DialogResult.OK) return null;
            if (!PdfReview.IsValidator(picker.FileName))
                throw new IOException("Choose the cli-*.jar file in veraPDF’s bin folder.");
            Directory.CreateDirectory(engine.DataDir);
            File.WriteAllText(settings, picker.FileName);
            return picker.FileName;
        }
    }
}

internal static class PdfReview
{
    public sealed class CheckResult
    {
        public bool ok { get; set; }
        public string message { get; set; }
    }

    internal static bool IsValidator(string path)
    {
        return File.Exists(path)
            && Path.GetFileName(path).StartsWith("cli-", StringComparison.OrdinalIgnoreCase)
            && Path.GetExtension(path).Equals(".jar", StringComparison.OrdinalIgnoreCase);
    }

    internal static Task PrepareAsync(string document, string destination, string validator)
    {
        var completion = new TaskCompletionSource<bool>();
        var worker = new Thread(delegate()
        {
            try
            {
                Prepare(document, destination, validator);
                completion.SetResult(true);
            }
            catch (Exception error) { completion.SetException(error); }
        }) { IsBackground = true };
        worker.SetApartmentState(ApartmentState.STA);
        worker.Start();
        return completion.Task;
    }

    private static void Prepare(string document, string destination, string validator)
    {
        string working = Path.Combine(Path.GetTempPath(), "ReportInterview-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(working);
        string staged = null;
        try
        {
            string taggedPdf = Path.Combine(working, "word.pdf");
            string candidate = Path.Combine(working, "candidate.pdf");
            ExportTaggedPdf(document, taggedPdf);
            CheckAndFinish(taggedPdf, candidate, validator);

            // Stage next to the destination so a checked file can be moved or replaced atomically.
            staged = Path.Combine(Path.GetDirectoryName(destination), Guid.NewGuid().ToString("N") + ".tmp");
            File.Copy(candidate, staged);
            if (File.Exists(destination)) File.Replace(staged, destination, null);
            else File.Move(staged, destination);
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
                Item: 0, KeepIRM: true, CreateBookmarks: 1, DocStructureTags: true, UseISO19005_1: false);
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

    private static void CheckAndFinish(string taggedPdf, string candidate, string validator)
    {
        string helper = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "ReportPdf.exe");
        var start = new ProcessStartInfo(helper, String.Join(" ", new[] { taggedPdf, candidate, validator }
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
            if (!process.WaitForExit(150000))
            {
                process.Kill();
                throw new IOException("The local accessibility check took too long. Try again or ask the reviewer for help.");
            }
            CheckResult result;
            try { result = new JavaScriptSerializer().Deserialize<CheckResult>(output.Result); }
            catch (ArgumentException) { result = null; }
            catch (InvalidOperationException) { result = null; }
            if (result == null)
                throw new IOException("The local PDF helper did not return a result. Ask the reviewer to check the installation.");
            if (!result.ok || process.ExitCode != 0)
                throw new IOException(result.message ?? "The local PDF helper could not check the report.");
        }
    }
}
