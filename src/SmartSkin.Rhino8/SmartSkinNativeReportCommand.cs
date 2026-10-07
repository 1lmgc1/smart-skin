using System;
using Eto.Forms;
using Rhino;
using Rhino.Commands;
using Rhino.UI;

namespace SmartSkin.Rhino8;

/// <summary>Save the last finished native diagnostic report without rerunning geometry.</summary>
public sealed class SmartSkinNativeReportCommand : Rhino.Commands.Command
{
    public override string EnglishName => "SmartSkinNativeReport";
    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
        var report = NativeCompareReportExport.Store.LastCompleted;
        if (report is null)
        {
            NativeCompareReportExport.Message("No native report is retained. Run SmartSkinNativeCompare first.");
            return Result.Nothing;
        }
        var outcome = NativeCompareReportExport.ChooseFolderAndSave(doc, mode, report);
        return outcome == NativeCompareExportOutcome.Saved ? Result.Success
            : outcome == NativeCompareExportOutcome.Cancelled ? Result.Cancel : Result.Failure;
    }
}

internal enum NativeCompareExportOutcome { Saved, Cancelled, Deferred, Failed }

internal static class NativeCompareReportExport
{
    internal static readonly NativeCompareReportStore Store = new();
    internal static void Message(string text) { try { RhinoApp.WriteLine(text); } catch { /* Retained report survives console errors. */ } }
    internal static NativeCompareExportOutcome ChooseFolderAndSave(RhinoDoc doc, RunMode mode, NativeCompareReportBuffer report)
    {
        if (mode != RunMode.Interactive)
        {
            Message("Native report retained for this Rhino session. Export deferred in scripted mode; run SmartSkinNativeReport interactively to choose a folder.");
            return NativeCompareExportOutcome.Deferred;
        }
        try
        {
            var path = Store.SaveLast(() =>
            {
                using var dialog = new SelectFolderDialog { Title = "Choose a folder for the full Smart Skin diagnostic TXT" };
                return dialog.ShowDialog(RhinoEtoApp.MainWindowForDocument(doc)) == DialogResult.Ok ? dialog.Directory : null;
            });
            if (path is null)
            {
                Message("Report save cancelled. The last finished report is retained for this Rhino session; run SmartSkinNativeReport to choose a folder again.");
                return NativeCompareExportOutcome.Cancelled;
            }
            Message("Smart Skin native report SAVED: " + path + " | complete_report=" + report.IsComplete
                + ". The last finished report remains available through SmartSkinNativeReport for this Rhino session.");
            return NativeCompareExportOutcome.Saved;
        }
        catch (Exception exception)
        {
            Message("Could not save the native report (" + exception.GetType().Name + "): " + exception.Message
                + ". The last finished report is retained for this Rhino session; run SmartSkinNativeReport to retry.");
            return NativeCompareExportOutcome.Failed;
        }
    }
}
