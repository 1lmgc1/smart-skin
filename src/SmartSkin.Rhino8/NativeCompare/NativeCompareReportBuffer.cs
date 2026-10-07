using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

namespace SmartSkin.Rhino8;

/// <summary>Bounded ordered report storage. Completeness refers to the report, never to geometry acceptance.</summary>
internal sealed class NativeCompareReportBuffer
{
    internal const int DefaultRunCharacterLimit = 2 * 1024 * 1024;
    private const int TerminalCharacterReserve = 32768;
    internal const int MaximumEntryCharacters = 65536;
    private readonly int _runLimit;
    private readonly List<string> _lines = new();
    private int _characters;
    private int _terminalCharacters;
    private int _cleanupCharacters;
    internal const string CleanupPrefix = "SMARTSKIN_NATIVE_COMPARE_CLEANUP |";
    internal NativeCompareReportBuffer(DateTime startedUtc, string reportId, int runCharacterLimit = DefaultRunCharacterLimit)
    {
        if (runCharacterLimit < 128) throw new ArgumentOutOfRangeException(nameof(runCharacterLimit));
        if (string.IsNullOrEmpty(reportId) || reportId.Length > 64)
            throw new ArgumentException("A bounded filename-safe report ID is required.", nameof(reportId));
        foreach (var character in reportId)
            if (!char.IsLetterOrDigit(character) && character != '_' && character != '-')
                throw new ArgumentException("A filename-safe report ID is required.", nameof(reportId));
        StartedUtc = startedUtc.ToUniversalTime();
        ReportId = reportId;
        _runLimit = runCharacterLimit;
    }
    internal DateTime StartedUtc { get; }
    internal string ReportId { get; }
    internal IReadOnlyList<string> Lines => _lines;
    internal bool CapacityExceeded { get; private set; }
    internal int OmittedEntries { get; private set; }
    internal bool CleanupRecorded { get; private set; }
    internal bool IsSealed { get; private set; }
    internal bool IsComplete { get; private set; }

    // Regular entries can never consume terminal/cleanup reserves. A rejected entry is counted,
    // then the caller stops the run. The retained report is explicitly incomplete.
    internal bool Append(string line)
    {
        if (IsSealed) throw new InvalidOperationException("REPORT_ALREADY_SEALED");
        if (line is null) throw new ArgumentNullException(nameof(line));
        if (line.StartsWith(CleanupPrefix, StringComparison.Ordinal)) { AppendTerminal(line); return true; }
        if (line.Length > MaximumEntryCharacters || (long)_characters + line.Length + 2 > _runLimit)
        {
            CapacityExceeded = true;
            OmittedEntries++;
            return false;
        }
        _lines.Add(line);
        _characters += line.Length + 2;
        return true;
    }
    internal void AppendTerminal(string line)
    {
        if (IsSealed) throw new InvalidOperationException("REPORT_ALREADY_SEALED");
        var cleanup = line.StartsWith(CleanupPrefix, StringComparison.Ordinal);
        var used = cleanup ? _cleanupCharacters : _terminalCharacters;
        var limit = cleanup ? 8192 : TerminalCharacterReserve - 8192;
        if ((long)used + line.Length + 2 > limit)
        {
            CapacityExceeded = true;
            OmittedEntries++;
            return;
        }
        _lines.Add(line);
        if (cleanup) { _cleanupCharacters += line.Length + 2; CleanupRecorded = true; }
        else _terminalCharacters += line.Length + 2;
    }
    internal void Seal(string result)
    {
        if (IsSealed) throw new InvalidOperationException("REPORT_ALREADY_SEALED");
        if (string.IsNullOrEmpty(result) || result.Length > 128) result = "UNAVAILABLE";
        IsComplete = !CapacityExceeded && OmittedEntries == 0 && CleanupRecorded;
        // A small fixed terminal footer is reserved separately, even if a pathological entry filled the tail.
        _lines.Add("SMARTSKIN_NATIVE_REPORT_END | run_result=" + result
            + " | complete_report=" + (IsComplete ? "true" : "false")
            + " | report_capacity_exceeded=" + CapacityExceeded + " | omitted_entries=" + OmittedEntries
            + " | cleanup_recorded=" + CleanupRecorded + " | report_id=" + ReportId);
        IsSealed = true;
    }
}

internal sealed class NativeCompareReportCapacityException : Exception { }

internal sealed class NativeCompareReportStore
{
    internal NativeCompareReportBuffer? LastCompleted { get; private set; }
    internal void Retain(NativeCompareReportBuffer report)
    {
        if (!report.IsSealed) throw new InvalidOperationException("UNFINISHED_REPORT_CANNOT_REPLACE_LAST_REPORT");
        LastCompleted = report;
    }
    internal string? SaveLast(Func<string?> chooseFolder, Func<NativeCompareReportBuffer, string, string>? save = null)
    {
        var report = LastCompleted ?? throw new InvalidOperationException("NO_FINISHED_REPORT");
        var folder = chooseFolder();
        if (string.IsNullOrWhiteSpace(folder)) return null;
        return save is null ? NativeCompareReportWriter.Save(report, folder!) : save(report, folder!);
    }
}

internal static class NativeCompareReportWriter
{
    internal static string Save(NativeCompareReportBuffer report, string folder,
        Func<string, Stream>? createNew = null, Action<string>? deletePartial = null)
    {
        if (!report.IsSealed) throw new InvalidOperationException("REPORT_NOT_FINISHED");
        if (string.IsNullOrWhiteSpace(folder)) throw new ArgumentException("Choose an existing report folder.", nameof(folder));
        var fullFolder = Path.GetFullPath(folder);
        if (!Directory.Exists(fullFolder)) throw new DirectoryNotFoundException("The chosen report folder does not exist.");
        var stem = "SmartSkinNativeReport_" + report.StartedUtc.ToString("yyyyMMdd_HHmmss_fff'Z'", CultureInfo.InvariantCulture)
            + "_" + report.ReportId;
        createNew ??= path => new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None);
        for (var suffix = 0; suffix < 100; suffix++)
        {
            var path = Path.Combine(fullFolder, stem + (suffix == 0 ? "" : "_" + suffix.ToString("D2", CultureInfo.InvariantCulture)) + ".txt");
            Stream stream;
            try { stream = createNew(path); }
            catch (IOException) when (File.Exists(path)) { continue; }
            try
            {
                using (stream)
                using (var writer = new StreamWriter(stream, new UTF8Encoding(true, true), 4096))
                {
                    writer.NewLine = "\r\n";
                    foreach (var line in report.Lines) writer.WriteLine(line);
                }
                return path;
            }
            catch (Exception writeError)
            {
                // Only the file just successfully created by this attempt is eligible for partial-file cleanup.
                try { if (deletePartial is null) File.Delete(path); else deletePartial(path); }
                catch (Exception cleanupError) { throw new NativeComparePartialReportException(path, writeError, cleanupError); }
                throw;
            }
        }
        throw new IOException("No unused report filename was available after 100 attempts.");
    }
}

internal static class NativeCompareReportCapture
{
    internal static void Run(NativeCompareReportBuffer report, NativeCompareReportStore store,
        Action<string> console, Func<Action<string>, string> diagnostic)
    {
        void Console(string line) { try { console(line); } catch { /* Console display cannot lose the buffered report. */ } }
        void Terminal(string line) { report.AppendTerminal(line); Console(line); }
        void Write(string line)
        {
            if (report.CapacityExceeded || line.StartsWith(NativeCompareReportBuffer.CleanupPrefix, StringComparison.Ordinal))
            { Terminal(line); return; }
            var continueRun = report.Append(line);
            Console(line);
            if (!continueRun) throw new NativeCompareReportCapacityException();
        }
        var result = "Failure";
        try { result = diagnostic(Write); }
        catch (NativeCompareReportCapacityException)
        {
            Terminal("SMARTSKIN_NATIVE_REPORT_ERROR | status=REPORT_CAPACITY_EXCEEDED | complete_report=false");
        }
        catch (Exception exception)
        {
            Terminal("SMARTSKIN_NATIVE_REPORT_ERROR | status=UNHANDLED_DIAGNOSTIC_ERROR | type=" + exception.GetType().Name);
        }
        finally
        {
            report.Seal(result);
            store.Retain(report);
            Console(report.Lines[report.Lines.Count - 1]);
        }
    }
}

internal sealed class NativeComparePartialReportException : IOException
{
    internal string PartialPath { get; }
    internal NativeComparePartialReportException(string path, Exception writeError, Exception cleanupError)
        : base("An incomplete report may remain at " + path + ". Write failure: " + writeError.GetType().Name
            + "; partial-file cleanup failure: " + cleanupError.GetType().Name + ".", writeError) => PartialPath = path;
}

internal static class NativeCompareReportCleanup
{
    internal static bool Attempt(string name, Action cleanup, ICollection<string> failures)
    {
        try { cleanup(); return true; }
        catch (Exception exception) { failures.Add(name + ":" + exception.GetType().Name); return false; }
    }
}
