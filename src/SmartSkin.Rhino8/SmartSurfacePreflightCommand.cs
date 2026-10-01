using System;
using System.Collections.Generic;
using System.Globalization;
using Rhino;
using Rhino.Commands;
using Rhino.DocObjects;
using Rhino.Input.Custom;
using SmartSkin.Core;
using SmartSkin.Core.Preflight;

namespace SmartSkin.Rhino8;

public sealed class SmartSurfacePreflightCommand : Command
{
    public override string EnglishName => "SmartSurfacePreflight";

    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
        var objectCountBefore = RhinoDocumentMetrics.ActiveObjectCount(doc);
        var identity = BuildIdentity.FromAssembly(typeof(SmartSurfacePreflightCommand).Assembly);

        using var selection = new GetObject();
        selection.SetCommandPrompt("Select curves, edges, points, surfaces, or polysurfaces to preflight");
        selection.GeometryFilter = ObjectType.Point
            | ObjectType.Curve
            | ObjectType.Surface
            | ObjectType.Brep
            | ObjectType.Extrusion;
        selection.SubObjectSelect = true;
        selection.GroupSelect = true;
        selection.GetMultiple(1, 0);

        var selectionResult = selection.CommandResult();
        if (selectionResult != Result.Success)
        {
            return selectionResult;
        }

        if (selection.ObjectCount > PreflightOptions.DefaultMaximumItems)
        {
            var objectCountAfterLimit = RhinoDocumentMetrics.ActiveObjectCount(doc);
            RhinoApp.WriteLine(
                $"SMARTSKIN_{identity.Patch} FAIL"
                + $" | version={identity.Version}"
                + $" | commit={identity.Commit}"
                + " | code=P01_SELECTION_LIMIT"
                + $" | selected={selection.ObjectCount.ToString(CultureInfo.InvariantCulture)}"
                + $" | max={PreflightOptions.DefaultMaximumItems.ToString(CultureInfo.InvariantCulture)}"
                + $" | objects={objectCountBefore.ToString(CultureInfo.InvariantCulture)}->{objectCountAfterLimit.ToString(CultureInfo.InvariantCulture)}");
            return Result.Failure;
        }

        try
        {
            var snapshots = new List<GeometrySnapshot>(selection.ObjectCount);
            for (var index = 0; index < selection.ObjectCount; index++)
            {
                var reference = selection.Object(index);
                var label = RhinoGeometrySnapshotFactory.CreateLabel(reference, index + 1);

                try
                {
                    snapshots.Add(RhinoGeometrySnapshotFactory.Create(
                        reference,
                        index + 1,
                        doc.ModelAbsoluteTolerance));
                }
                catch (Exception exception)
                {
                    snapshots.Add(GeometrySnapshot.Failed(
                        label,
                        $"Snapshot extraction failed ({exception.GetType().Name}): {exception.Message}"));
                }
            }

            var analyzer = new GeometryPreflightAnalyzer();
            var report = analyzer.Analyze(
                snapshots,
                new PreflightOptions(doc.ModelAbsoluteTolerance));

            RhinoApp.WriteLine("Smart Skin geometry preflight");
            RhinoApp.WriteLine($"Patch: {identity.Patch}");
            RhinoApp.WriteLine($"Version: {identity.Version}");
            RhinoApp.WriteLine($"Commit: {identity.Commit}");
            RhinoApp.WriteLine($"Units: {doc.ModelUnitSystem}");
            RhinoApp.WriteLine("Mode: read-only; document geometry is not modified.");

            foreach (var line in report.ToDisplayLines())
            {
                RhinoApp.WriteLine(line);
            }

            var objectCountAfter = RhinoDocumentMetrics.ActiveObjectCount(doc);
            if (objectCountBefore != objectCountAfter)
            {
                RhinoApp.WriteLine(
                    $"SMARTSKIN_{identity.Patch} FAIL"
                    + " | code=P01_DOCUMENT_MUTATED"
                    + $" | objects={objectCountBefore.ToString(CultureInfo.InvariantCulture)}->{objectCountAfter.ToString(CultureInfo.InvariantCulture)}");
                return Result.Failure;
            }

            RhinoApp.WriteLine(report.ToMachineLine(identity, objectCountBefore, objectCountAfter));
            return Result.Success;
        }
        catch (Exception exception)
        {
            var objectCountAfterFailure = RhinoDocumentMetrics.ActiveObjectCount(doc);
            RhinoApp.WriteLine(
                $"SMARTSKIN_{identity.Patch} FAIL"
                + " | code=P01_UNHANDLED"
                + $" | exception={exception.GetType().Name}"
                + $" | objects={objectCountBefore.ToString(CultureInfo.InvariantCulture)}->{objectCountAfterFailure.ToString(CultureInfo.InvariantCulture)}");
            return Result.Failure;
        }
    }
}
