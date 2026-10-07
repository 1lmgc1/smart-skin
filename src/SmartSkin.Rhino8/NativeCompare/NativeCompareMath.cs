using System;

namespace SmartSkin.Rhino8;

/// <summary>Physical ambient Weingarten operator arithmetic, independent of parameterization.</summary>
internal static class NativeCompareMath
{
    internal static void ApplyFaceOrientation(double[] normal, double[] shapeOperator, bool reversed)
    {
        // Both inputs belong to the SAME signed principal-curvature evaluation.
        // Never combine an independently face-oriented NormalAt result with raw curvature.
        if (normal.Length != 3 || shapeOperator.Length != 9) throw new ArgumentException("A 3D normal and full3x3 operator are required.");
        if (!reversed) return;
        for (var i = 0; i < normal.Length; i++) normal[i] = -normal[i];
        for (var i = 0; i < shapeOperator.Length; i++) shapeOperator[i] = -shapeOperator[i];
    }

    internal static double[] Operator(double k0, double[] d0, double k1, double[] d1, double sign)
    {
        var result = new double[9];
        for (var row = 0; row < 3; row++)
            for (var col = 0; col < 3; col++)
                result[3 * row + col] = sign * (k0 * d0[row] * d0[col] + k1 * d1[row] * d1[col]);
        return result;
    }
    internal static double OperatorResidual(double[] a, double[] b, double alignmentSign)
    {
        double sum = 0;
        for (var i = 0; i < 9; i++)
        {
            var delta = a[i] - alignmentSign * b[i];
            sum += delta * delta;
        }
        return Math.Sqrt(sum);
    }
    internal static double OperatorSpectralResidual(double[] a, double[] b, double alignmentSign)
    {
        var matrix = new double[3, 3];
        double scale = 0;
        for (var i = 0; i < 3; i++)
            for (var j = 0; j < 3; j++)
            {
                var value = a[3 * i + j] - alignmentSign * b[3 * i + j];
                if (!Finite(value)) return double.NaN;
                matrix[i, j] = value;
                scale = Math.Max(scale, Math.Abs(value));
            }
        if (scale == 0) return 0;
        for (var i = 0; i < 3; i++) for (var j = 0; j < 3; j++) matrix[i, j] /= scale;
        // Bounded Jacobi diagonalization of a real symmetric ambient 3x3 tensor.
        for (var iteration = 0; iteration < 24; iteration++)
        {
            var p = 0; var q = 1;
            if (Math.Abs(matrix[0, 2]) > Math.Abs(matrix[p, q])) { p = 0; q = 2; }
            if (Math.Abs(matrix[1, 2]) > Math.Abs(matrix[p, q])) { p = 1; q = 2; }
            if (Math.Abs(matrix[p, q]) < 1e-15) break;
            var angle = 0.5 * Math.Atan2(2 * matrix[p, q], matrix[q, q] - matrix[p, p]);
            var cosine = Math.Cos(angle); var sine = Math.Sin(angle);
            var pp = matrix[p, p]; var qq = matrix[q, q]; var pq = matrix[p, q];
            for (var k = 0; k < 3; k++)
            {
                if (k == p || k == q) continue;
                var kp = matrix[k, p]; var kq = matrix[k, q];
                matrix[k, p] = matrix[p, k] = cosine * kp - sine * kq;
                matrix[k, q] = matrix[q, k] = sine * kp + cosine * kq;
            }
            matrix[p, p] = cosine * cosine * pp - 2 * sine * cosine * pq + sine * sine * qq;
            matrix[q, q] = sine * sine * pp + 2 * sine * cosine * pq + cosine * cosine * qq;
            matrix[p, q] = matrix[q, p] = 0;
        }
        return scale * Math.Max(Math.Abs(matrix[0, 0]), Math.Max(Math.Abs(matrix[1, 1]), Math.Abs(matrix[2, 2])));
    }

    internal static bool IsPhysicalContinuation(double tangentAngle, double curvatureDelta,
        double maximumCurvature, double normalAngle, double operatorDelta, double maximumOperator,
        double wholeLoopLength)
    {
        if (!Finite(wholeLoopLength) || wholeLoopLength <= 0 || !Finite(tangentAngle)
            || !Finite(curvatureDelta) || !Finite(maximumCurvature) || !Finite(normalAngle)
            || !Finite(operatorDelta) || !Finite(maximumOperator)) return false;
        return tangentAngle <= 1e-5 && normalAngle <= 1e-5
            && curvatureDelta <= Math.Max(1e-9 / wholeLoopLength, 1e-5 * maximumCurvature)
            && operatorDelta <= Math.Max(1e-9 / wholeLoopLength, 1e-5 * maximumOperator);
    }
    internal static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
}
