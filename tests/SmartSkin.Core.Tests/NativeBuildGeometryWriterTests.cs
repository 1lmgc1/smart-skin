using System;
using System.Linq;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class NativeBuildGeometryWriterTests
{
    [Fact]
    public void SignedZeroIsEquivalentButTheSmallestFiniteValueIsNot()
    {
        Assert.Equal(NumericSignature(0.0), NumericSignature(-0.0));
        Assert.NotEqual(NumericSignature(0.0), NumericSignature(double.Epsilon));
        Assert.NotEqual(NumericSignature(1.0), NumericSignature(double.BitIncrement(1.0)));
    }
    [Theory]
    [InlineData(double.NaN)]
    [InlineData(double.PositiveInfinity)]
    [InlineData(double.NegativeInfinity)]
    public void NonfiniteDefiningGeometryIsRejected(double value)
    {
        using var writer = new NativeBuildGeometryWriter();
        Assert.Throws<ArgumentException>(() => writer.Numbers("vertex", 0, value, 0));
    }
    [Fact]
    public void HomogeneousWeightsCannotBeLostByEuclideanProjection()
    {
        // Both control points project to the same xyz; differing relative NURBS weights
        // change the curve between controls and must remain part of the witness.
        Assert.NotEqual(CurveSignature(point: new[] { 2.0, 4, 6, 2 }), CurveSignature(point: new[] { 3.0, 6, 9, 3 }));
    }
    [Theory]
    [InlineData("dimension")]
    [InlineData("degree")]
    [InlineData("rational")]
    [InlineData("domain")]
    [InlineData("knot")]
    [InlineData("control")]
    [InlineData("weight")]
    [InlineData("count")]
    public void EveryCurveDefinitionComponentAffectsTheSignature(string changed)
    {
        Assert.NotEqual(CurveSignature(), CurveSignature(changed));
    }
    [Fact]
    public void SurfaceTensorOrderDegreesKnotsAndDomainsAreDistinct()
    {
        byte[] Signature(string mutation)
        {
            using var writer = new NativeBuildGeometryWriter();
            var points = new[] { new[] { 0.0, 0, 0, 1 }, new[] { 0.0, 1, 0, 1 }, new[] { 1.0, 0, .25, 1 }, new[] { 1.0, 1, 0, 1 } };
            if (mutation == "order") Array.Reverse(points);
            writer.Surface("support", 3, mutation == "degree" ? 2 : 1, 1, false, 2, 2,
                0, mutation == "domain" ? 2 : 1, 0, 1,
                mutation == "knots" ? new[] { 0.0, .5, 1 } : new[] { 0.0, 1 }, new[] { 0.0, 1 }, points);
            return writer.Finish();
        }
        foreach (var mutation in new[] { "order", "degree", "domain", "knots" }) Assert.NotEqual(Signature(""), Signature(mutation));
    }
    [Fact]
    public void TopologyIncidenceTrimOrderAndOrientationCannotAlias()
    {
        byte[] Signature(string role, int[] values)
        {
            using var writer = new NativeBuildGeometryWriter(); writer.Integers(role, values); return writer.Finish();
        }
        Assert.NotEqual(Signature("loop_trim_order", new[] { 0, 1, 2, 3 }), Signature("loop_trim_order", new[] { 0, 2, 1, 3 }));
        Assert.NotEqual(Signature("edge", new[] { 0, 0, 1, 0 }), Signature("edge", new[] { 0, 1, 0, 0 }));
        Assert.NotEqual(Signature("trim", new[] { 0, 1, 0 }), Signature("trim", new[] { 0, 1, 1 }));
        Assert.NotEqual(Signature("face", new[] { 0, 0 }), Signature("face", new[] { 0, 1 }));
        Assert.NotEqual(Signature("face", new[] { 0, 1 }), Signature("trim", new[] { 0, 1 }));
    }
    [Fact]
    public void ProxyDomainAndEffectiveCurveHaveIndependentRecords()
    {
        byte[] Signature(double domainEnd, double proxyControl)
        {
            using var writer = new NativeBuildGeometryWriter();
            writer.Numbers("edge_proxy_domain", 0, domainEnd);
            writer.Numbers("edge_effective_proxy_curve3d", 0, proxyControl, 0, 1);
            return writer.Finish();
        }
        Assert.NotEqual(Signature(1, 0), Signature(2, 0));
        Assert.NotEqual(Signature(1, 0), Signature(1, 1e-12));
    }
    [Fact]
    public void FramingDistinguishesArrayBoundariesAndNumericTypes()
    {
        using var a = new NativeBuildGeometryWriter(); using var b = new NativeBuildGeometryWriter();
        a.Numbers("p", 1, 2); a.Numbers("p", 3);
        b.Numbers("p", 1); b.Numbers("p", 2, 3);
        Assert.NotEqual(a.Finish(), b.Finish());
        using var c = new NativeBuildGeometryWriter(); using var d = new NativeBuildGeometryWriter();
        c.Numbers("p", 1); d.Integers("p", 1); Assert.NotEqual(c.Finish(), d.Finish());
    }
    [Fact]
    public void HomogeneousAndTensorCountErrorsAreRejected()
    {
        using var writer = new NativeBuildGeometryWriter();
        Assert.Throws<ArgumentException>(() => writer.Curve("curve", 3, 1, true, 0, 1, new[] { 0.0, 1 }, new[] { new[] { 1.0, 2, 3 } }));
        Assert.Throws<ArgumentException>(() => writer.Surface("surface", 3, 1, 1, false, 2, 2, 0, 1, 0, 1,
            new[] { 0.0, 1 }, new[] { 0.0, 1 }, Array.Empty<double[]>()));
    }
    [Fact]
    public void WriterRejectsMoreThanFourMebibytesOfDefiningData()
    {
        using var writer = new NativeBuildGeometryWriter();
        var error = Assert.Throws<InvalidOperationException>(() => writer.Numbers("large_control_net", new double[512 * 1024]));
        Assert.Equal("GEOMETRY_SIGNATURE_SIZE_LIMIT", error.Message);
    }
    private static byte[] NumericSignature(double value)
    { using var writer = new NativeBuildGeometryWriter(); writer.Numbers("value", value); return writer.Finish(); }
    private static byte[] CurveSignature(string mutation = "", double[]? point = null)
    {
        using var writer = new NativeBuildGeometryWriter();
        var p = point ?? new[] { 1.0, 2, 3, 1 };
        if (mutation == "control") p[0] = double.BitIncrement(p[0]);
        if (mutation == "weight") p[3] = 2;
        var points = new[] { new[] { 0.0, 0, 0, 1 }, p, new[] { 2.0, 1, 0, 1 } };
        if (mutation == "count") points = points.Concat(new[] { new[] { 3.0, 1, 0, 1 } }).ToArray();
        writer.Curve("curve", mutation == "dimension" ? 2 : 3, mutation == "degree" ? 1 : 2, mutation != "rational", 0,
            mutation == "domain" ? 2 : 1, mutation == "knot" ? new[] { 0.0, 0, .5, 1, 1 } : new[] { 0.0, 0, 1, 1 }, points);
        return writer.Finish();
    }
}
