using System;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

// Pure managed arithmetic only. These tests do not load Rhino or execute geometry.
public sealed class NativeCompareMathTests
{
    [Fact]
    public void AnalyticPlaneAndCylinderFramesKeepNormalAndOperatorParityTogether()
    {
        // Analytic references, not native Rhino calls. Plane has W=0; a radius2
        // cylinder has one principal curvature of magnitude1/2 and one zero.
        var s = Math.Sqrt(0.5);
        foreach (var curvature in new[] { 0.0, -0.5 })
            foreach (var reversedA in new[] { false, true })
                foreach (var reversedB in new[] { false, true })
                {
                    var aNormal = new[] { s, 0.0, s }; var bNormal = new[] { s, 0.0, s };
                    var a = NativeCompareMath.Operator(curvature, new[] { 0.0, 1, 0 }, 0, new[] { s, 0.0, -s }, 1);
                    var b = (double[])a.Clone();
                    NativeCompareMath.ApplyFaceOrientation(aNormal, a, reversedA);
                    NativeCompareMath.ApplyFaceOrientation(bNormal, b, reversedB);
                    var dot = aNormal[0] * bNormal[0] + aNormal[1] * bNormal[1] + aNormal[2] * bNormal[2];
                    Assert.Equal(0, NativeCompareMath.OperatorSpectralResidual(a, b, dot < 0 ? -1 : 1), 12);
                }
    }

    [Fact]
    public void MixedNormalConventionProducesFalseTwiceCurvatureResidual()
    {
        var cylinder = NativeCompareMath.Operator(-0.5, new[] { 1.0, 0, 0 }, 0, new[] { 0.0, 1, 0 }, 1);
        var reversed = (double[])cylinder.Clone(); var normal = new[] { 0.0, 0, 1 };
        NativeCompareMath.ApplyFaceOrientation(normal, reversed, true);
        Assert.Equal(-1, normal[2]);
        Assert.Equal(0, NativeCompareMath.OperatorSpectralResidual(cylinder, reversed, -1), 12);
        // A double-flipped normal would incorrectly select +1 alignment while W
        // was flipped only once, producing2/R rather than zero.
        Assert.Equal(1, NativeCompareMath.OperatorSpectralResidual(cylinder, reversed, 1), 12);
    }

    [Fact]
    public void DetectsMixedCurvatureInvisibleToOneAcrossDirection()
    {
        var r = Math.Sqrt(0.5);
        var plane = NativeCompareMath.Operator(0, new[] { 1.0, 0, 0 }, 0, new[] { 0.0, 1, 0 }, 1);
        var saddle = NativeCompareMath.Operator(1, new[] { r, r, 0 }, -1, new[] { r, -r, 0 }, 1);
        Assert.Equal(plane[0], saddle[0], 12); // One normal curvature can match while mixed curvature fails.
        Assert.Equal(Math.Sqrt(2), NativeCompareMath.OperatorResidual(plane, saddle, 1), 12);
        Assert.Equal(1, NativeCompareMath.OperatorSpectralResidual(plane, saddle, 1), 12);
    }

    [Fact]
    public void ReversedNormalChangesSignedOperatorAndIsAlignedExplicitly()
    {
        var a = NativeCompareMath.Operator(2, new[] { 1.0, 0, 0 }, 3, new[] { 0.0, 1, 0 }, 1);
        var b = NativeCompareMath.Operator(2, new[] { 1.0, 0, 0 }, 3, new[] { 0.0, 1, 0 }, -1);
        Assert.Equal(0, NativeCompareMath.OperatorResidual(a, b, -1), 12);
        Assert.True(NativeCompareMath.OperatorResidual(a, b, 1) > 0);
    }

    [Fact]
    public void PrincipalAxisSignsAndOrderDoNotChangePhysicalOperator()
    {
        var a = NativeCompareMath.Operator(2, new[] { 1.0, 0, 0 }, 3, new[] { 0.0, 1, 0 }, 1);
        var b = NativeCompareMath.Operator(3, new[] { 0.0, -1, 0 }, 2, new[] { -1.0, 0, 0 }, 1);
        Assert.Equal(0, NativeCompareMath.OperatorResidual(a, b, 1), 12);
    }

    [Fact]
    public void PhysicalCurvatureScalesWithInverseLength()
    {
        var a = NativeCompareMath.Operator(2, new[] { 1.0, 0, 0 }, 3, new[] { 0.0, 1, 0 }, 1);
        var b = NativeCompareMath.Operator(0.2, new[] { 1.0, 0, 0 }, 0.3, new[] { 0.0, 1, 0 }, 1);
        var zero = new double[9];
        Assert.Equal(NativeCompareMath.OperatorResidual(zero, a, 1) / 10,
            NativeCompareMath.OperatorResidual(zero, b, 1), 12);
    }

    [Fact]
    public void ShallowRealCornerIsNotMergedUsingDocumentAngleAcceptance()
    {
        const double physicalTurn = 0.002;
        Assert.True(physicalTurn < Math.PI / 180); // Below a possible one-degree document acceptance.
        Assert.False(NativeCompareMath.IsPhysicalContinuation(physicalTurn, 0, 0, 0, 0, 0, 20));
    }

    [Fact]
    public void RepresentationSeamWithEqualPhysicalJetsDoesNotBecomeCorner()
    {
        Assert.True(NativeCompareMath.IsPhysicalContinuation(0, 0, 4, 0, 0, 5, 20));
        // The decision has no knot count, degree, edge count, or segment-length input.
        Assert.True(NativeCompareMath.IsPhysicalContinuation(1e-8, 1e-8, 4, 1e-8, 1e-8, 5, 20));
    }

    [Fact]
    public void ParentOperatorBreakRemainsARealBranchEvenWhenBoundaryCurveIsSmooth()
    {
        Assert.False(NativeCompareMath.IsPhysicalContinuation(0, 0, 4, 0, 0.02, 5, 20));
    }

    [Fact]
    public void SpectralNormRetainsTheLargestAbsolutePrincipalResidualAfterRotation()
    {
        var r = 1 / Math.Sqrt(3);
        var q = 1 / Math.Sqrt(2);
        var tensor = NativeCompareMath.Operator(-7, new[] { r, r, r }, 2, new[] { q, -q, 0 }, 1);
        Assert.Equal(7, NativeCompareMath.OperatorSpectralResidual(tensor, new double[9], 1), 11);
        Assert.Equal(0, NativeCompareMath.OperatorSpectralResidual(tensor, tensor, 1), 12);
    }
}
