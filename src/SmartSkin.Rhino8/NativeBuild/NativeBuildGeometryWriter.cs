using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace SmartSkin.Rhino8;

// A deterministic, length-framed signature of defining numeric geometry records.
// No tolerance comparison: only signed zero is normalized. Metadata is not an input.
internal sealed class NativeBuildGeometryWriter : IDisposable
{
    private const int MaximumBytes = 4 * 1024 * 1024;
    private readonly MemoryStream _stream = new();
    private readonly BinaryWriter _writer;
    internal NativeBuildGeometryWriter()
    {
        _writer = new BinaryWriter(_stream, Encoding.UTF8, true);
        _writer.Write("SMARTSKIN_EXACT_INSERTED_CAP_V1");
    }
    internal void Integers(string role, params int[] values)
    {
        _writer.Write((byte)1); _writer.Write(role); _writer.Write(values.Length);
        foreach (var value in values) _writer.Write(value);
        CheckSize();
    }
    internal void Numbers(string role, params double[] values)
    {
        _writer.Write((byte)2); _writer.Write(role); _writer.Write(values.Length);
        foreach (var value in values)
        {
            if (double.IsNaN(value) || double.IsInfinity(value)) throw new ArgumentException("NONFINITE_GEOMETRY_SIGNATURE_VALUE");
            _writer.Write(value == 0.0 ? 0.0 : value);
        }
        CheckSize();
    }
    internal void Curve(string role, int dimension, int degree, bool rational, double start, double end,
        IReadOnlyList<double> knots, IReadOnlyList<double[]> homogeneousPoints)
    {
        Integers(role, dimension, degree, rational ? 1 : 0, knots.Count, homogeneousPoints.Count);
        Numbers("domain", start, end);
        WriteKnots("knots", knots);
        WritePoints(homogeneousPoints);
    }
    internal void Surface(string role, int dimension, int degreeU, int degreeV, bool rational, int countU, int countV,
        double u0, double u1, double v0, double v1, IReadOnlyList<double> knotsU, IReadOnlyList<double> knotsV,
        IReadOnlyList<double[]> homogeneousPoints)
    {
        if ((long)countU * countV != homogeneousPoints.Count) throw new ArgumentException("SURFACE_CONTROL_COUNT_MISMATCH");
        Integers(role, dimension, degreeU, degreeV, rational ? 1 : 0, countU, countV, knotsU.Count, knotsV.Count);
        Numbers("domains", u0, u1, v0, v1);
        WriteKnots("knots_u", knotsU); WriteKnots("knots_v", knotsV);
        WritePoints(homogeneousPoints);
    }
    private void WriteKnots(string role, IReadOnlyList<double> knots)
    {
        var copy = new double[knots.Count];
        for (var i = 0; i < copy.Length; i++) copy[i] = knots[i];
        Numbers(role, copy);
    }
    private void WritePoints(IReadOnlyList<double[]> points)
    {
        foreach (var point in points)
        {
            if (point.Length != 4) throw new ArgumentException("HOMOGENEOUS_POINT_REQUIRES_XYZW");
            Numbers("xyzw", point);
        }
    }
    private void CheckSize()
    { if (_stream.Length > MaximumBytes) throw new InvalidOperationException("GEOMETRY_SIGNATURE_SIZE_LIMIT"); }
    internal byte[] Finish()
    {
        _writer.Flush();
        using var sha = SHA256.Create();
        return sha.ComputeHash(_stream.ToArray());
    }
    public void Dispose() { _writer.Dispose(); _stream.Dispose(); }
}
