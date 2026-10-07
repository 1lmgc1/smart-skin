using System;
using System.Linq;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class NativeBuildCapPolicyTests
{
    [Fact]
    public void OrthogonalAndSkewDirectionsHaveRankButParallelAndZeroDoNot()
    {
        Assert.True(Rank(new[] { 1.0, 0, 0 }, new[] { 0.0, 1, 0 }));
        Assert.True(Rank(new[] { 1.0, 2, 3 }, new[] { -2.0, 3, -1 }));
        Assert.False(Rank(new[] { 1.0, 2, 3 }, new[] { 2.0, 4, 6 }));
        Assert.False(Rank(new[] { 1.0, 2, 3 }, new[] { -2.0, -4, -6 }));
        Assert.False(Rank(new[] { 0.0, 0, 0 }, new[] { 0.0, 1, 0 }));
        Assert.False(Rank(new[] { 1.0, 0, 0 }, new[] { 0.0, 0, 0 }));
    }

    [Fact]
    public void ThresholdUsesMachineSpacingAndRejectsUnresolvedRankAtTheBoundary()
    {
        var threshold = NativeBuildCapPolicy.MinimumRelativeJacobian;
        Assert.Equal(Math.Pow(2, -46), threshold);
        Assert.False(Rank(new[] { 1.0, 0, 0 }, new[] { 1.0, threshold / 2, 0 }));
        Assert.False(Rank(new[] { 1.0, 0, 0 }, new[] { 1.0, threshold, 0 }));
        Assert.True(Rank(new[] { 1.0, 0, 0 }, new[] { 1.0, threshold * 2, 0 }));
    }

    [Fact]
    public void IndependentDomainScalingAndReversalPreserveClassification()
    {
        var threshold = NativeBuildCapPolicy.MinimumRelativeJacobian;
        var u = new[] { 1.0, 0, 0 };
        foreach (var transverse in new[] { threshold / 4, threshold * 4, .5 })
        {
            var v = new[] { 1.0, transverse, 0 };
            var expected = Rank(u, v);
            foreach (var uScale in new[] { -1e250, 1e-250, 1.0, 1e250 })
            foreach (var vScale in new[] { -1e-250, 1e-250, 1.0, 1e250 })
                Assert.Equal(expected, Rank(Scale(u, uScale), Scale(v, vScale)));
        }
    }

    [Fact]
    public void RigidRotationAndModelUnitScalingPreserveWellResolvedRank()
    {
        // Rodrigues rotation about (1,1,1), with all axes mixed.
        double[] Rotate(double[] p)
        {
            const double angle = .713;
            var c = Math.Cos(angle); var s = Math.Sin(angle) / Math.Sqrt(3);
            var along = (p[0] + p[1] + p[2]) * (1 - c) / 3;
            return new[] { p[0] * c + (p[2] - p[1]) * s + along,
                p[1] * c + (p[0] - p[2]) * s + along, p[2] * c + (p[1] - p[0]) * s + along };
        }
        var u = new[] { 1.0, 2, 3 };
        foreach (var v in new[] { new[] { -2.0, 3, -1 }, new[] { 2.0, 4, 6 } })
        foreach (var unitScale in new[] { 1e-250, .001, 1.0, 1000, 1e250 })
            Assert.Equal(Rank(u, v), Rank(Scale(Rotate(u), unitScale), Scale(Rotate(v), unitScale)));
    }

    [Fact]
    public void ExtremeFiniteAndSubnormalVectorsAvoidCrossProductOverflowOrUnderflow()
    {
        foreach (var magnitude in new[] { double.Epsilon, 1e-300, 1e300, double.MaxValue })
        {
            Assert.True(Rank(new[] { magnitude, 0, 0 }, new[] { 0, magnitude, 0 }));
            Assert.False(Rank(new[] { magnitude, magnitude, 0 }, new[] { magnitude, magnitude, 0 }));
        }
    }

    [Fact]
    public void NonfiniteOrMalformedDerivativeNeverPasses()
    {
        var valid = new[] { 1.0, 2, 3 };
        foreach (var nonfinite in new[] { double.NaN, double.NegativeInfinity, double.PositiveInfinity })
        for (var component = 0; component < 3; component++)
        {
            var broken = (double[])valid.Clone(); broken[component] = nonfinite;
            Assert.False(Rank(broken, valid)); Assert.False(Rank(valid, broken));
        }
        Assert.False(Rank(null!, valid)); Assert.False(Rank(valid, null!));
        Assert.False(Rank(new[] { 1.0, 2 }, valid));
        Assert.False(Rank(valid, new[] { 1.0, 2, 3, 4 }));
    }

    private static bool Rank(double[] u, double[] v) => NativeBuildCapPolicy.RegularJacobian(u, v);
    private static double[] Scale(double[] vector, double factor) => vector.Select(value => value * factor).ToArray();
}
