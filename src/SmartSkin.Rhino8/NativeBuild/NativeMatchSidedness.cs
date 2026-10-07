using System;
using System.Collections.Generic;
using System.Linq;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

// Local trim occupancy only. No global parent/cap collision claim is made.
internal sealed class NativeMatchSidedness
{
    private readonly Dictionary<(Brep Owner, int Loop), int> _loopSigns = new();
    internal bool Inward(BrepEdge edge, double parameter, double positionTolerance,
        Action checkpoint, out Vector3d inward, out string reason)
    {
        inward = Vector3d.Unset; reason = "TRIM_SIDEDNESS_UNRESOLVED";
        var indices = edge.TrimIndices();
        if (indices.Length != 1 || edge.Brep is null) return false;
        var trim = edge.Brep.Trims[indices[0]]; var face = trim.Face;
        if (face is null || trim.Loop is null
            || !trim.GetTrimParameter(parameter, out var t) || !trim.Domain.IncludesParameter(t)) return false;
        var sign = LoopSign(trim, checkpoint);
        if (sign == 0) { reason = "TRIM_LOOP_ORIENTATION_UNRESOLVED"; return false; }
        var uv = trim.PointAt(t); var tangent = trim.TangentAt(t);
        if (!uv.IsValid || !tangent.IsValid || !face.Evaluate(uv.X, uv.Y, 1, out var point, out var derivatives)
            || !point.IsValid || derivatives is null || derivatives.Length < 2) return false;
        var edgePoint = edge.PointAt(parameter); var gap = point.DistanceTo(edgePoint);
        if (!edgePoint.IsValid || !NativeCompareMath.Finite(gap) || gap > positionTolerance) return false;
        if (!NativeMatchSidednessPolicy.TryInward(Components(derivatives[0]), Components(derivatives[1]), tangent.X, tangent.Y,
            sign, out var value)) return false;
        inward = new Vector3d(value[0], value[1], value[2]);
        reason = "EXACT_TRIM_LOOP_MATERIAL_SIDE";
        return true;
    }
    private int LoopSign(BrepTrim trim, Action checkpoint)
    {
        var loop = trim.Loop; var key = (trim.Brep, loop.LoopIndex);
        if (_loopSigns.TryGetValue(key, out var existing)) return existing;
        if (_loopSigns.Count >= 256 || (loop.LoopType != BrepLoopType.Outer && loop.LoopType != BrepLoopType.Inner)) return 0;
        checkpoint();
        using var curve = loop.To2dCurve();
        var sign = 0;
        if (curve is not null && curve.IsValid && curve.IsClosed)
        {
            var orientation = curve.ClosedCurveOrientation();
            if (orientation == CurveOrientation.CounterClockwise) sign = 1;
            else if (orientation == CurveOrientation.Clockwise) sign = -1;
            if (loop.LoopType == BrepLoopType.Inner) sign = -sign;
        }
        _loopSigns.Add(key, sign); return sign;
    }
    private static double[] Components(Vector3d value) => new[] { value.X, value.Y, value.Z };
}
