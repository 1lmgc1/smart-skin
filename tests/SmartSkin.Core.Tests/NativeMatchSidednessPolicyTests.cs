using System;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class NativeMatchSidednessPolicyTests
{
    [Theory]
    [InlineData(1, 1, 0, true)]
    [InlineData(7, 7, 0, true)]
    [InlineData(0, 0, 0, false)]
    [InlineData(-1, -1, 0, false)]
    [InlineData(7, 0, 0, false)]
    [InlineData(7, 6, 0, false)]
    [InlineData(7, 8, 0, false)]
    [InlineData(7, 7, 1, false)]
    [InlineData(7, 7, -1, false)]
    public void CompletenessRequiresEveryRequiredStationAndNoFailures(int required, int resolved, int failed, bool expected)
    {
        Assert.Equal(expected, NativeMatchSidednessPolicy.Complete(required, resolved, failed));
    }

    [Fact]
    public void SameSideCubicCuspRejectsDespiteEqualBoundaryPlaneNormalAndCurvature()
    {
        // Parent(u,v)=(u,v,0), v>=0; cap(u,w)=(u,w,w^3), w>=0.
        // At w=v=0 their positions, tangent planes and full shape operators agree,
        // but both occupied domains point inward along +y.
        foreach (var u in new[] { -2.0, 0.0, .25, 7.0 })
        {
            Assert.Equal(Parent(u, 0), Cap(u, 0));
            var alongBoundary = new[] { 1.0, 0.0, 0.0 };
            var parentInward = new[] { 0.0, 1.0, 0.0 };
            var capInward = CapFirstDerivative(0);
            Assert.Equal(Cross(alongBoundary, parentInward), Cross(alongBoundary, capInward));
            // The remaining uu and uw second derivatives are also zero.
            Assert.Equal(new double[3], CapSecondDerivative(0));
            Assert.False(NativeMatchSidednessPolicy.Opposed(parentInward, capInward, out var dot));
            Assert.Equal(1, dot);
        }
    }

    [Fact]
    public void CubicExtensionIntoNegativeParameterDomainHasOppositeInwardDirection()
    {
        // The same cap chart with occupied domain w<=0 is a local extension.
        var parentInward = new[] { 0.0, 1.0, 0.0 };
        var capInward = Scale(CapFirstDerivative(0), -1);
        Assert.True(NativeMatchSidednessPolicy.Opposed(parentInward, capInward, out var dot));
        Assert.Equal(-1, dot);
    }

    [Theory]
    [InlineData(false, false)]
    [InlineData(false, true)]
    [InlineData(true, false)]
    [InlineData(true, true)]
    public void CommonRotationAndMirrorPreservePhysicalOccupiedSide(bool rotate, bool mirror)
    {
        var parentInward = Transform(new[] { 0.0, 1.0, 0.0 }, rotate, mirror);
        var sameSide = Transform(CapFirstDerivative(0), rotate, mirror);
        var extension = Transform(Scale(CapFirstDerivative(0), -1), rotate, mirror);
        Assert.False(NativeMatchSidednessPolicy.Opposed(parentInward, sameSide, out var sameDot));
        Assert.True(NativeMatchSidednessPolicy.Opposed(parentInward, extension, out var oppositeDot));
        Assert.InRange(sameDot, 1 - 1e-14, 1);
        Assert.InRange(oppositeDot, -1, -1 + 1e-14);
    }

    [Theory]
    [InlineData(1, 1)]
    [InlineData(1, -1)]
    [InlineData(-1, 1)]
    [InlineData(-1, -1)]
    public void FaceNormalParityDoesNotChangePhysicalInwardVectors(int parentParity, int capParity)
    {
        var tangent = new[] { 1.0, 0.0, 0.0 };
        var normal = new[] { 0.0, 0.0, 1.0 };
        // Occupied-domain signs belong to the physical fixture. Reversing a face
        // normal reverses its frame co-normal and its corresponding occupied sign.
        var parentInward = Scale(Cross(Scale(normal, parentParity), tangent), parentParity);
        var sameSide = Scale(Cross(Scale(normal, capParity), tangent), capParity);
        var extension = Scale(Cross(Scale(normal, capParity), tangent), -capParity);
        Assert.Equal(new[] { 0.0, 1.0, 0.0 }, parentInward);
        Assert.Equal(parentInward, sameSide);
        Assert.Equal(new[] { 0.0, -1.0, 0.0 }, extension);
        Assert.False(NativeMatchSidednessPolicy.Opposed(parentInward, sameSide, out _));
        Assert.True(NativeMatchSidednessPolicy.Opposed(parentInward, extension, out _));
    }

    [Fact]
    public void StrictSignRejectsZeroAndAcceptsNegativeWithoutAnAdditionalAngleGate()
    {
        var first = new[] { 1.0, 0.0, 0.0 };
        Assert.False(NativeMatchSidednessPolicy.Opposed(first, new[] { 0.0, 1.0, 0.0 }, out var zero));
        Assert.Equal(0, zero);
        Assert.False(NativeMatchSidednessPolicy.Opposed(first, new[] { double.Epsilon, 1.0, 0.0 }, out var positive));
        Assert.Equal(double.Epsilon, positive);
        Assert.True(NativeMatchSidednessPolicy.Opposed(first, new[] { -double.Epsilon, 1.0, 0.0 }, out var negative));
        Assert.Equal(-double.Epsilon, negative);
        Assert.True(NativeMatchSidednessPolicy.Opposed(first, new[] { -.01, 1.0, 0.0 }, out _));
    }

    [Fact]
    public void IndependentHugeAndSubnormalMagnitudesNormalizeWithoutOverflowOrUnderflow()
    {
        foreach (var firstScale in new[] { double.MaxValue, 1.0, double.Epsilon })
        foreach (var secondScale in new[] { double.MaxValue, 1.0, double.Epsilon })
        {
            var first = new[] { firstScale, -firstScale, firstScale };
            var second = new[] { -secondScale, secondScale, -secondScale };
            Assert.True(NativeMatchSidednessPolicy.Opposed(first, second, out var oppositeDot));
            Assert.InRange(oppositeDot, -1, -1 + 1e-14);
            Assert.False(NativeMatchSidednessPolicy.Opposed(first, Scale(second, -1), out var sameDot));
            Assert.InRange(sameDot, 1 - 1e-14, 1);
        }
    }

    [Fact]
    public void MissingMalformedZeroOrNonfiniteVectorsFailClosedOnEitherSide()
    {
        var valid = new[] { 0.0, 1.0, 0.0 };
        var invalidVectors = new[]
        {
            null!, Array.Empty<double>(), new[] { 0.0, 1.0 }, new[] { 0.0, 1.0, 0.0, 0.0 },
            new[] { 0.0, -0.0, 0.0 }, new[] { double.NaN, 1.0, 0.0 },
            new[] { 0.0, double.PositiveInfinity, 1.0 }, new[] { 1.0, 0.0, double.NegativeInfinity }
        };
        foreach (var invalid in invalidVectors)
        {
            Assert.False(NativeMatchSidednessPolicy.Opposed(invalid, valid, out var firstDot));
            Assert.True(double.IsNaN(firstDot));
            Assert.False(NativeMatchSidednessPolicy.Opposed(valid, invalid, out var secondDot));
            Assert.True(double.IsNaN(secondDot));
        }
    }

    [Fact]
    public void SkewUvChartUsesMappedTrimTangentRatherThanDifferentlyApproximatedThreeDEdge()
    {
        // A separate 3D edge tilted by .002 radians is intentionally absent from
        // this API. Its representation cannot reverse the trim-domain occupancy.
        Assert.True(NativeMatchSidednessPolicy.TryInward(new[] { 1.0, 0.0, 0.0 },
            new[] { 1000.0, 1.0, 0.0 }, 1, 0, 1, out var inward));
        AssertDirection(new[] { 0.0, 1.0, 0.0 }, inward);
    }

    [Fact]
    public void AnisotropicInwardUsesItsMappedTrimFrameDespiteDifferentThreeDEdgeTangent()
    {
        // The mapped trim tangent is (-1000,1,0). A separate 3D edge tangent
        // (1,.002,0) would select the opposite occupied side if used here. Its
        // approximation belongs to attachment jets, not this trim-domain frame.
        Assert.True(NativeMatchSidednessPolicy.TryInward(new[] { 1000.0, 0.0, 0.0 },
            new[] { 0.0, 1.0, 0.0 }, -1, 1, 1, out var inward));
        AssertDirection(new[] { -.001, -1.0, 0.0 }, inward);
        Assert.True(NativeMatchSidednessPolicy.Opposed(inward, new[] { -.002, 1.0, 0.0 }, out _));
    }

    [Theory]
    [InlineData(1.0, 1.0)]
    [InlineData(.001, 1000.0)]
    [InlineData(-3.0, 7.0)]
    [InlineData(3.0, -7.0)]
    [InlineData(-3.0, -7.0)]
    public void UvDomainReparameterizationPreservesThePhysicalOccupiedDirection(double a, double b)
    {
        // u=a*p, v=b*q; a negative chart determinant reverses UV material-left.
        var su = Scale(new[] { 3.0, 0.0, 0.0 }, a);
        var sv = Scale(new[] { 1.0, 2.0, 0.0 }, b);
        Assert.True(NativeMatchSidednessPolicy.TryInward(su, sv, 2 / a, 1 / b,
            Math.Sign(a) * Math.Sign(b), out var inward));
        AssertDirection(new[] { -2.0, 7.0, 0.0 }, inward);
    }

    [Theory]
    [InlineData(false, 1)]
    [InlineData(false, -1)]
    [InlineData(true, 1)]
    [InlineData(true, -1)]
    public void OrientedLoopReversalAndMirroredGeometryPreserveTheOccupiedDomain(bool mirror, int loopDirection)
    {
        var su = Transform(new[] { 1.0, 0.0, 0.0 }, true, mirror);
        var sv = Transform(new[] { 0.0, 1.0, 0.0 }, true, mirror);
        Assert.True(NativeMatchSidednessPolicy.TryInward(su, sv, loopDirection, 0,
            loopDirection, out var inward));
        AssertDirection(sv, inward);
        // Material on the other side of a trimmed loop changes the actual inward
        // geometry. This is distinct from changing only a face-normal convention.
        Assert.True(NativeMatchSidednessPolicy.TryInward(su, sv, loopDirection, 0,
            -loopDirection, out var otherSide));
        Assert.True(NativeMatchSidednessPolicy.Opposed(inward, otherSide, out _));
    }

    [Fact]
    public void CommonSurfaceAndTrimScalesCanBeHugeOrSubnormal()
    {
        foreach (var surfaceScale in new[] { double.MaxValue, 1.0, double.Epsilon })
        foreach (var trimScale in new[] { double.MaxValue, 1.0, double.Epsilon })
        {
            Assert.True(NativeMatchSidednessPolicy.TryInward(new[] { surfaceScale, 0.0, 0.0 },
                new[] { 0.0, surfaceScale, 0.0 }, trimScale, 0, 1, out var inward));
            AssertDirection(new[] { 0.0, 1.0, 0.0 }, inward);
        }
    }

    [Fact]
    public void UnresolvedInwardInputsAndParallelProjectionFailClosed()
    {
        var su = new[] { 1.0, 0.0, 0.0 };
        var sv = new[] { 0.0, 1.0, 0.0 };
        foreach (var sign in new[] { 0, 2, -2 })
            Assert.False(NativeMatchSidednessPolicy.TryInward(su, sv, 1, 0, sign, out _));
        foreach (var invalid in new[] { double.NaN, double.PositiveInfinity, double.NegativeInfinity })
        {
            Assert.False(NativeMatchSidednessPolicy.TryInward(su, sv, invalid, 0, 1, out _));
            Assert.False(NativeMatchSidednessPolicy.TryInward(su, sv, 1, invalid, 1, out _));
            Assert.False(NativeMatchSidednessPolicy.TryInward(new[] { invalid, 0.0, 0.0 }, sv, 1, 0, 1, out _));
            Assert.False(NativeMatchSidednessPolicy.TryInward(su, new[] { 0.0, invalid, 0.0 }, 1, 0, 1, out _));
        }
        Assert.False(NativeMatchSidednessPolicy.TryInward(su, sv, 0, 0, 1, out _));
        Assert.False(NativeMatchSidednessPolicy.TryInward(new double[3], new double[3], 1, 0, 1, out _));
        Assert.False(NativeMatchSidednessPolicy.TryInward(new double[3], sv, 1, 0, 1, out _));
        Assert.False(NativeMatchSidednessPolicy.TryInward(su, su, 1, -1, 1, out _));
        Assert.False(NativeMatchSidednessPolicy.TryInward(null!, sv, 1, 0, 1, out _));
        Assert.False(NativeMatchSidednessPolicy.TryInward(su, Array.Empty<double>(), 1, 0, 1, out _));
        var diagonal = new[] { 1.0, 1.0, 1.0 };
        Assert.False(NativeMatchSidednessPolicy.TryInward(diagonal, diagonal, 1, 0, 1, out var unresolved));
        Assert.Empty(unresolved);
    }

    private static void AssertDirection(double[] expected, double[] actual)
    {
        var length = Math.Sqrt(expected[0] * expected[0] + expected[1] * expected[1] + expected[2] * expected[2]);
        for (var i = 0; i < 3; i++) Assert.InRange(Math.Abs(expected[i] / length - actual[i]), 0, 1e-12);
    }

    private static double[] Parent(double u, double v) => new[] { u, v, 0.0 };
    private static double[] Cap(double u, double w) => new[] { u, w, w * w * w };
    private static double[] CapFirstDerivative(double w) => new[] { 0.0, 1.0, 3 * w * w };
    private static double[] CapSecondDerivative(double w) => new[] { 0.0, 0.0, 6 * w };
    private static double[] Scale(double[] v, double scale) => new[] { v[0] * scale, v[1] * scale, v[2] * scale };
    private static double[] Cross(double[] a, double[] b) => new[]
    {
        a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]
    };

    private static double[] Transform(double[] v, bool rotate, bool mirror)
    {
        var x = v[0]; var y = v[1]; var z = v[2];
        if (rotate)
        {
            var ry = Math.Cos(.7) * y - Math.Sin(.7) * z;
            var rz = Math.Sin(.7) * y + Math.Cos(.7) * z;
            var rx = Math.Cos(-.4) * x + Math.Sin(-.4) * rz;
            z = -Math.Sin(-.4) * x + Math.Cos(-.4) * rz;
            x = rx; y = ry;
        }
        return new[] { mirror ? -x : x, y, z };
    }
}
