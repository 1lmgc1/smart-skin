using System;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class NativeMatchMeshOutputPolicyTests
{
    [Theory]
    [InlineData(null, null)]
    [InlineData(0, null)]
    [InlineData(null, 0)]
    [InlineData(0, 0)]
    public void ExactWrapperNullAndEmptyPolylineOutputsPassWithAnAllocatedEmptyMesh(int? perforations, int? polylines)
    {
        using var output = new NativeMatchMeshOutputPolicy<MeshDouble>();
        output.OverlapMesh = new MeshDouble();
        Assert.Null(Check(output, true, false, perforations, polylines));
        Assert.Equal(0, output.Perforations); Assert.Equal(0, output.OverlapPolylines);
        Assert.Equal(0, output.OverlapVertices); Assert.Equal(0, output.OverlapFaces);
    }

    [Fact]
    public void SuccessWithoutTheRequestedAllocatedMeshIsUnresolved()
    {
        using var output = new NativeMatchMeshOutputPolicy<MeshDouble>();
        Assert.Equal("FINALIST_NATIVE_OVERLAP_OUTPUT_UNRESOLVED", Check(output));
    }

    [Theory]
    [InlineData(1, 0, 0, 0)]
    [InlineData(0, 1, 0, 0)]
    [InlineData(0, 0, 1, 0)]
    [InlineData(0, 0, 0, 1)]
    public void EveryNonemptyRequestedOutputRejectsIncludingOrphanMeshVertices(int perforations, int polylines, int vertices, int faces)
    {
        using var output = new NativeMatchMeshOutputPolicy<MeshDouble>();
        output.OverlapMesh = new MeshDouble { Vertices = vertices, Faces = faces };
        Assert.Equal("FINALIST_MESH_PERFORATION_OR_OVERLAP_DETECTED", Check(output, true, false, perforations, polylines));
    }

    [Theory]
    [InlineData(false, false)]
    [InlineData(true, true)]
    [InlineData(false, true)]
    public void FailureAndCancellationCannotPromoteAndDisposeReturnedOutputExactlyOnce(bool success, bool cancelled)
    {
        var mesh = new MeshDouble();
        var output = new NativeMatchMeshOutputPolicy<MeshDouble>();
        using (output)
        {
            WrapperAllocation(mesh, out output.OverlapMesh);
            Assert.Equal("FINALIST_NATIVE_SELF_INTERSECTION_FAILED_OR_CANCELLED", Check(output, success, cancelled));
        }
        output.Dispose();
        Assert.Equal(1, mesh.Disposals); Assert.Null(output.OverlapMesh);
    }

    [Fact]
    public void NativeExceptionAfterWrapperOutAllocationStillDisposesOutput()
    {
        var mesh = new MeshDouble();
        Assert.Throws<InvalidOperationException>((Action)(() =>
        {
            using var output = new NativeMatchMeshOutputPolicy<MeshDouble>();
            WrapperAllocation(mesh, out output.OverlapMesh);
            throw new InvalidOperationException("Simulated native failure after allocation.");
        }));
        Assert.Equal(1, mesh.Disposals);
    }

    [Fact]
    public void CheckpointCancellationAfterNativeReturnStillDisposesOutput()
    {
        var mesh = new MeshDouble();
        Assert.Throws<OperationCanceledException>((Action)(() =>
        {
            using var output = new NativeMatchMeshOutputPolicy<MeshDouble>();
            WrapperAllocation(mesh, out output.OverlapMesh);
            throw new OperationCanceledException();
        }));
        Assert.Equal(1, mesh.Disposals);
    }

    [Fact]
    public void MalformedCountsCannotBeReportedAsEmpty()
    {
        using var output = new NativeMatchMeshOutputPolicy<MeshDouble>();
        output.OverlapMesh = new MeshDouble { Vertices = -1 };
        Assert.Equal("FINALIST_NATIVE_OVERLAP_OUTPUT_UNRESOLVED", Check(output));
    }

    private static string? Check(NativeMatchMeshOutputPolicy<MeshDouble> output, bool success = true, bool cancelled = false,
        int? perforations = null, int? polylines = null) => output.Failure(success, cancelled, perforations, polylines,
            value => value.Vertices, value => value.Faces);
    private static void WrapperAllocation(MeshDouble mesh, out MeshDouble? output) => output = mesh;

    private sealed class MeshDouble : IDisposable
    {
        internal int Vertices, Faces, Disposals;
        public void Dispose() => Disposals++;
    }
}
