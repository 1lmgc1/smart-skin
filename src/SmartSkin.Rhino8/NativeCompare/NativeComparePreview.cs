using System;
using System.Drawing;
using Rhino.Display;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class NativeCompareCandidate : IDisposable
{
    internal string Name { get; }
    internal Brep Brep { get; }
    internal Mesh[] Meshes { get; }
    internal BoundingBox Bounds { get; }
    internal NativeCompareCandidate(string name, Brep brep)
    {
        Name = name; Brep = brep;
        Bounds = brep.GetBoundingBox(true);
        using var parameters = new MeshingParameters(MeshingParameters.FastRenderMesh)
        {
            GridMinCount = 4, GridMaxCount = 1024, RefineGrid = false, ComputeCurvature = false,
        };
        Meshes = Mesh.CreateFromBrep(brep, parameters) ?? Array.Empty<Mesh>();
        long vertices = 0;
        foreach (var mesh in Meshes) vertices += mesh.Vertices.Count;
        if (vertices > 100000)
        {
            foreach (var mesh in Meshes) mesh.Dispose();
            Meshes = Array.Empty<Mesh>();
        }
    }
    public void Dispose() { foreach (var mesh in Meshes) mesh.Dispose(); Brep.Dispose(); }
}

internal sealed class NativeComparePreview : DisplayConduit, IDisposable
{
    internal NativeCompareCandidate? Candidate;
    private readonly DisplayMaterial _material = new(Color.FromArgb(235, 170, 50), 0.35);
    protected override void CalculateBoundingBox(CalculateBoundingBoxEventArgs e)
    {
        if (Candidate is not null && Candidate.Bounds.IsValid) e.IncludeBoundingBox(Candidate.Bounds);
    }
    protected override void PreDrawObjects(DrawEventArgs e)
    {
        if (Candidate is null) return;
        foreach (var mesh in Candidate.Meshes) e.Display.DrawMeshShaded(mesh, _material);
        e.Display.DrawBrepWires(Candidate.Brep, Color.DarkOrange, 1);
    }
    public void Dispose() { Enabled = false; Candidate = null; _material.Dispose(); }
}
