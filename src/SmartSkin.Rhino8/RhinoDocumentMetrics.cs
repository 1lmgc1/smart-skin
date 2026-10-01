using System;
using Rhino;
using Rhino.DocObjects;

namespace SmartSkin.Rhino8;

internal static class RhinoDocumentMetrics
{
    public static int ActiveObjectCount(RhinoDoc doc)
    {
        if (doc is null)
        {
            throw new ArgumentNullException(nameof(doc));
        }

        var settings = new ObjectEnumeratorSettings
        {
            ActiveObjects = true,
            DeletedObjects = false,
            NormalObjects = true,
            LockedObjects = true,
            HiddenObjects = true,
            ReferenceObjects = false,
            IdefObjects = false,
            IncludeGrips = false,
            IncludeLights = false,
            IncludePhantoms = false
        };

        var count = 0;
        foreach (var _ in doc.Objects.GetObjectList(settings))
        {
            count++;
        }

        return count;
    }
}
