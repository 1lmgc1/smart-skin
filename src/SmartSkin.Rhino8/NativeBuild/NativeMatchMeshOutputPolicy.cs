using System;

namespace SmartSkin.Rhino8;

// Testable ownership and empty-output contract of the exact RhinoCommon 8.21
// MeshMesh_Helper wrapper. This class does not simulate native intersection.
internal sealed class NativeMatchMeshOutputPolicy<TMesh> : IDisposable where TMesh : class, IDisposable
{
    // Pass the owned field directly as the native out argument. Ownership then
    // survives a native false result or an exception after wrapper allocation.
    internal TMesh? OverlapMesh;
    internal int Perforations { get; private set; } = -1;
    internal int OverlapPolylines { get; private set; } = -1;
    internal int OverlapVertices { get; private set; } = -1;
    internal int OverlapFaces { get; private set; } = -1;

    internal string? Failure(bool success, bool cancelled, int? perforations, int? overlapPolylines,
        Func<TMesh, int> vertices, Func<TMesh, int> faces)
    {
        // The wrapper leaves a polyline output null when its native count is zero.
        Perforations = perforations ?? 0; OverlapPolylines = overlapPolylines ?? 0;
        OverlapVertices = OverlapMesh is null ? -1 : vertices(OverlapMesh);
        OverlapFaces = OverlapMesh is null ? -1 : faces(OverlapMesh);
        if (!success || cancelled) return "FINALIST_NATIVE_SELF_INTERSECTION_FAILED_OR_CANCELLED";
        // overlapsMesh=true unconditionally allocates the out mesh before the
        // native call; a null mesh on success is therefore an unresolved result.
        if (OverlapMesh is null || Perforations < 0 || OverlapPolylines < 0 || OverlapVertices < 0 || OverlapFaces < 0)
            return "FINALIST_NATIVE_OVERLAP_OUTPUT_UNRESOLVED";
        if (Perforations != 0 || OverlapPolylines != 0 || OverlapVertices != 0 || OverlapFaces != 0)
            return "FINALIST_MESH_PERFORATION_OR_OVERLAP_DETECTED";
        return null;
    }

    public void Dispose()
    {
        var owned = OverlapMesh; OverlapMesh = null;
        owned?.Dispose();
    }
}
