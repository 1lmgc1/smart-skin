using System;
using System.Runtime.InteropServices;
using Rhino;
using Rhino.Commands;
using SmartSkin.Core;

namespace SmartSkin.Rhino8;

public sealed class SmartSurfaceVersionCommand : Command
{
    public override string EnglishName => "SmartSurfaceVersion";

    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
        var objectCountBefore = RhinoDocumentMetrics.ActiveObjectCount(doc);
        var identity = BuildIdentity.FromAssembly(typeof(SmartSurfaceVersionCommand).Assembly);

        RhinoApp.WriteLine("Smart Skin diagnostic bootstrap");
        RhinoApp.WriteLine($"Patch: {identity.Patch}");
        RhinoApp.WriteLine($"Version: {identity.Version}");
        RhinoApp.WriteLine($"Commit: {identity.Commit}");
        RhinoApp.WriteLine($"Rhino: {RhinoApp.Version}");
        RhinoApp.WriteLine($"Runtime: {RuntimeInformation.FrameworkDescription}");
        RhinoApp.WriteLine($"Process: {(Environment.Is64BitProcess ? "x64" : "x86")}");
        RhinoApp.WriteLine("Mode: diagnostic-only; document geometry is not modified.");

        var objectCountAfter = RhinoDocumentMetrics.ActiveObjectCount(doc);
        if (objectCountBefore != objectCountAfter)
        {
            RhinoApp.WriteLine($"SMARTSKIN_{identity.Patch} FAIL | objects={objectCountBefore}->{objectCountAfter}");
            return Result.Failure;
        }

        RhinoApp.WriteLine(identity.ToMachineLine(objectCountAfter));
        return Result.Success;
    }
}
