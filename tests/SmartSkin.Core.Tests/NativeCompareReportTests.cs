using System;
using System.IO;
using System.Linq;
using System.Text;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class NativeCompareReportTests
{
    private const string Cleanup = "SMARTSKIN_NATIVE_COMPARE_CLEANUP | source_archive=VERIFIED_UNCHANGED | added=0 | replaced=0";
    private static NativeCompareReportBuffer NewReport(int limit = NativeCompareReportBuffer.DefaultRunCharacterLimit) =>
        new(new DateTime(2026, 1, 2, 3, 4, 5, DateTimeKind.Utc), "synthetic_run", limit);
    private static NativeCompareReportBuffer Finished(NativeCompareReportStore store, string result = "Success")
    {
        var report = NewReport();
        NativeCompareReportCapture.Run(report, store, _ => { }, write =>
        {
            write("header: synthetic version and full commit");
            write("Unicode: café 日本語 Привет");
            write(Cleanup);
            return result;
        });
        return report;
    }
    private sealed class Folder : IDisposable
    {
        internal string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "native report 日本語 " + Guid.NewGuid().ToString("N"));
        internal Folder() => Directory.CreateDirectory(Path);
        public void Dispose() => Directory.Delete(Path, true);
    }

    [Theory]
    [InlineData("Success")]
    [InlineData("Cancel")]
    [InlineData("Failure")]
    public void FullyCapturedOutcomesKeepExactOrderAndCleanupBeforeFooter(string result)
    {
        var store = new NativeCompareReportStore();
        var report = Finished(store, result);
        Assert.Same(report, store.LastCompleted);
        Assert.True(report.IsComplete);
        Assert.Equal("header: synthetic version and full commit", report.Lines[0]);
        Assert.Equal(Cleanup, report.Lines[2]);
        Assert.Contains("run_result=" + result, report.Lines[3]);
        Assert.Contains("complete_report=true", report.Lines[3]);
    }

    [Fact]
    public void EarlyFailureStillRecordsFinallyCleanupAndRetainsWholeReport()
    {
        var report = NewReport();
        var store = new NativeCompareReportStore();
        NativeCompareReportCapture.Run(report, store, _ => { }, write =>
        {
            try { write("selection failed"); throw new InvalidOperationException(); }
            finally { write(Cleanup); }
        });
        Assert.True(report.IsComplete);
        Assert.Equal(Cleanup, report.Lines[1]);
        Assert.Contains("UNHANDLED_DIAGNOSTIC_ERROR", report.Lines[2]);
        Assert.Same(report, store.LastCompleted);
    }

    [Fact]
    public void ConsoleFailureCannotPreventCaptureCleanupOrCompletion()
    {
        var report = NewReport();
        var store = new NativeCompareReportStore();
        NativeCompareReportCapture.Run(report, store, _ => throw new IOException(), write =>
        {
            write("native result"); write(Cleanup); return "Success";
        });
        Assert.True(report.IsComplete);
        Assert.Equal("native result", report.Lines[0]);
        Assert.Same(report, store.LastCompleted);
    }

    [Fact]
    public void PickerCancellationAndWriteFailureRetainReportForLaterRetry()
    {
        var store = new NativeCompareReportStore();
        var report = Finished(store);
        var saves = 0;
        Assert.Null(store.SaveLast(() => null, (_, _) => { saves++; return "unused"; }));
        Assert.Equal(0, saves);
        Assert.Same(report, store.LastCompleted);
        Assert.Throws<IOException>(() => store.SaveLast(() => "some folder", (_, _) => throw new IOException()));
        Assert.Same(report, store.LastCompleted);
        using var folder = new Folder();
        Assert.True(File.Exists(store.SaveLast(() => folder.Path)));
        Assert.Same(report, store.LastCompleted);
    }

    [Fact]
    public void Utf8ReportUsesChosenUnicodeFolderAndNeverOverwritesACollision()
    {
        using var folder = new Folder();
        var report = Finished(new NativeCompareReportStore());
        var first = NativeCompareReportWriter.Save(report, folder.Path);
        var firstBytes = File.ReadAllBytes(first);
        var second = NativeCompareReportWriter.Save(report, folder.Path);
        Assert.NotEqual(first, second);
        Assert.StartsWith("SmartSkinNativeReport_20260102_030405_000Z_", System.IO.Path.GetFileName(first));
        Assert.Equal(firstBytes, File.ReadAllBytes(first));
        Assert.Equal(firstBytes, File.ReadAllBytes(second));
        Assert.Equal(new byte[] { 0xef, 0xbb, 0xbf }, firstBytes.Take(3).ToArray());
        var expected = string.Join("\r\n", report.Lines) + "\r\n";
        Assert.Equal(expected, File.ReadAllText(first, Encoding.UTF8));
    }

    [Fact]
    public void IncompleteActiveRunCannotReplacePreviouslyRetainedReport()
    {
        var store = new NativeCompareReportStore();
        var first = Finished(store);
        var active = NewReport();
        active.Append("new run begins");
        Assert.Throws<InvalidOperationException>(() => store.Retain(active));
        Assert.Throws<InvalidOperationException>(() => NativeCompareReportWriter.Save(active, "."));
        Assert.Same(first, store.LastCompleted);
    }

    [Fact]
    public void OverflowStopsFurtherWorkReservesCleanupAndMarksReportIncomplete()
    {
        var report = NewReport(128);
        var furtherWork = false;
        NativeCompareReportCapture.Run(report, new NativeCompareReportStore(), _ => { }, write =>
        {
            try { write(new string('x', 129)); furtherWork = true; return "Success"; }
            finally { write(Cleanup); }
        });
        Assert.False(furtherWork);
        Assert.True(report.CapacityExceeded);
        Assert.True(report.CleanupRecorded);
        Assert.False(report.IsComplete);
        Assert.DoesNotContain(new string('x', 129), report.Lines);
        Assert.Equal(1, report.OmittedEntries);
        Assert.Contains(Cleanup, report.Lines);
        Assert.Contains("complete_report=false", report.Lines.Last());
    }

    [Fact]
    public void OversizedEntryIsExplicitlyOmittedAndNeverReportedComplete()
    {
        var report = NewReport();
        NativeCompareReportCapture.Run(report, new NativeCompareReportStore(), _ => { }, write =>
        {
            try { write(new string('x', NativeCompareReportBuffer.MaximumEntryCharacters + 1)); return "Success"; }
            finally { write(Cleanup); }
        });
        Assert.Equal(1, report.OmittedEntries);
        Assert.False(report.IsComplete);
        Assert.Contains("omitted_entries=1", report.Lines.Last());
        Assert.DoesNotContain(report.Lines, line => line.Length > NativeCompareReportBuffer.MaximumEntryCharacters);
    }

    [Fact]
    public void MissingCleanupCannotBeLabeledACompleteReport()
    {
        var report = NewReport();
        NativeCompareReportCapture.Run(report, new NativeCompareReportStore(), _ => { }, write => "Failure");
        Assert.False(report.IsComplete);
        Assert.Contains("cleanup_recorded=False", report.Lines.Last());
    }

    [Fact]
    public void PartialWriteFailureRemovesOnlyItsNewFileAndAllowsRetry()
    {
        using var folder = new Folder();
        var report = Finished(new NativeCompareReportStore());
        var sentinel = System.IO.Path.Combine(folder.Path, "existing.txt");
        File.WriteAllText(sentinel, "keep");
        Assert.Throws<IOException>(() => NativeCompareReportWriter.Save(report, folder.Path,
            path => new BrokenWriteStream(new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))));
        Assert.Equal(new[] { sentinel }, Directory.GetFiles(folder.Path));
        Assert.Equal("keep", File.ReadAllText(sentinel));
        Assert.True(File.Exists(NativeCompareReportWriter.Save(report, folder.Path)));
    }

    [Fact]
    public void LargeOverflowEntryCannotConsumeCleanupReserve()
    {
        var report = NewReport(128);
        NativeCompareReportCapture.Run(report, new NativeCompareReportStore(), _ => { }, write =>
        {
            try { write(new string('a', 120)); write(new string('b', 32700)); return "Success"; }
            finally { write(Cleanup); }
        });
        Assert.True(report.CleanupRecorded);
        Assert.Contains(Cleanup, report.Lines);
        Assert.Equal(1, report.OmittedEntries);
        Assert.False(report.IsComplete);
        Assert.True(report.Lines.Sum(line => line.Length) < 2048);
    }

    [Fact]
    public void FinalCleanupUsesItsReserveEvenWhenRegularPrefixIsNearlyFull()
    {
        var report = NewReport(128);
        NativeCompareReportCapture.Run(report, new NativeCompareReportStore(), _ => { }, write =>
        {
            write(new string('a', 120)); write(Cleanup); return "Success";
        });
        Assert.Contains(Cleanup, report.Lines);
        Assert.True(report.CleanupRecorded);
        Assert.True(report.IsComplete);
        Assert.Equal(0, report.OmittedEntries);
    }

    [Fact]
    public void ErrorCaptureAtTheLimitCannotEscapeOrLoseFinalCleanup()
    {
        var report = NewReport(128);
        NativeCompareReportCapture.Run(report, new NativeCompareReportStore(), _ => { }, write =>
        {
            try { write(new string('a', 120)); throw new InvalidOperationException(); }
            finally { write(Cleanup); }
        });
        Assert.True(report.IsSealed);
        Assert.True(report.IsComplete);
        Assert.Contains(report.Lines, line => line.Contains("UNHANDLED_DIAGNOSTIC_ERROR"));
        Assert.Contains(Cleanup, report.Lines);
    }

    [Fact]
    public void OneCleanupFailureDoesNotSkipOtherDisposalsOrHonestFinalStatus()
    {
        var report = NewReport();
        var secondDisposed = false;
        NativeCompareReportCapture.Run(report, new NativeCompareReportStore(), _ => { }, write =>
        {
            var failures = new System.Collections.Generic.List<string>();
            var first = NativeCompareReportCleanup.Attempt("first", () => throw new IOException(), failures);
            var second = NativeCompareReportCleanup.Attempt("second", () => secondDisposed = true, failures);
            write(NativeCompareReportBuffer.CleanupPrefix + " all_candidates_disposed=" + (first && second)
                + " | cleanup_failures=" + string.Join(",", failures));
            return "Failure";
        });
        Assert.True(secondDisposed);
        Assert.True(report.IsComplete); // A complete account of failed cleanup, not a cleanup success claim.
        Assert.Contains(report.Lines, line => line.Contains("all_candidates_disposed=False") && line.Contains("first:IOException"));
    }

    [Fact]
    public void FailedPartialCleanupDisclosesThePathAndPreservesRetryBuffer()
    {
        using var folder = new Folder();
        var store = new NativeCompareReportStore();
        var report = Finished(store);
        var error = Assert.Throws<NativeComparePartialReportException>(() => NativeCompareReportWriter.Save(report, folder.Path,
            path => new BrokenWriteStream(new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None)),
            path => throw new IOException("Synthetic cleanup failure")));
        Assert.True(File.Exists(error.PartialPath));
        Assert.Contains(error.PartialPath, error.Message);
        Assert.Same(report, store.LastCompleted);
        var retry = store.SaveLast(() => folder.Path);
        Assert.NotEqual(error.PartialPath, retry);
        Assert.True(File.Exists(retry));
    }

    private sealed class BrokenWriteStream : Stream
    {
        private readonly Stream _inner;
        internal BrokenWriteStream(Stream inner) => _inner = inner;
        public override bool CanRead => false;
        public override bool CanSeek => false;
        public override bool CanWrite => true;
        public override long Length => _inner.Length;
        public override long Position { get => _inner.Position; set => throw new NotSupportedException(); }
        public override void Flush() => throw new IOException("Synthetic disk failure");
        public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count)
        {
            if (count > 0) _inner.Write(buffer, offset, Math.Min(count, 8));
            throw new IOException("Synthetic disk failure");
        }
        protected override void Dispose(bool disposing) { if (disposing) _inner.Dispose(); base.Dispose(disposing); }
    }
}
