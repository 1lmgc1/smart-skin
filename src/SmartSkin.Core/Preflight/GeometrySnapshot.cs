using System;
using System.Collections.Generic;
using System.Globalization;

namespace SmartSkin.Core.Preflight;

public enum GeometryKind
{
    Curve,
    BrepEdge,
    Point,
    Surface,
    Brep,
    Extrusion,
    Other
}

public readonly struct Point3Value
{
    public Point3Value(double x, double y, double z)
    {
        X = x;
        Y = y;
        Z = z;
    }

    public double X { get; }

    public double Y { get; }

    public double Z { get; }

    public bool IsFinite => IsFiniteNumber(X) && IsFiniteNumber(Y) && IsFiniteNumber(Z);

    public double DistanceTo(Point3Value other)
    {
        if (!IsFinite || !other.IsFinite)
        {
            return double.NaN;
        }

        var dx = X - other.X;
        var dy = Y - other.Y;
        var dz = Z - other.Z;
        return Math.Sqrt((dx * dx) + (dy * dy) + (dz * dz));
    }

    private static bool IsFiniteNumber(double value)
    {
        return !double.IsNaN(value) && !double.IsInfinity(value);
    }
}

public readonly struct Bounds3Value
{
    public Bounds3Value(Point3Value min, Point3Value max)
    {
        Min = min;
        Max = max;
        IsValid = min.IsFinite
            && max.IsFinite
            && min.X <= max.X
            && min.Y <= max.Y
            && min.Z <= max.Z;
    }

    public Point3Value Min { get; }

    public Point3Value Max { get; }

    public bool IsValid { get; }

    public double DiagonalLength => IsValid ? Min.DistanceTo(Max) : 0.0;

    public Bounds3Value Union(Bounds3Value other)
    {
        if (!IsValid)
        {
            return other;
        }

        if (!other.IsValid)
        {
            return this;
        }

        return new Bounds3Value(
            new Point3Value(
                Math.Min(Min.X, other.Min.X),
                Math.Min(Min.Y, other.Min.Y),
                Math.Min(Min.Z, other.Min.Z)),
            new Point3Value(
                Math.Max(Max.X, other.Max.X),
                Math.Max(Max.Y, other.Max.Y),
                Math.Max(Max.Z, other.Max.Z)));
    }
}

public sealed class GeometrySnapshot
{
    public GeometrySnapshot(
        string label,
        GeometryKind kind,
        bool? isValid,
        Bounds3Value bounds,
        double? length = null,
        bool? isClosed = null,
        Point3Value? startPoint = null,
        Point3Value? endPoint = null,
        bool? isPlanar = null,
        int? degree = null,
        int? spanCount = null,
        int? faceCount = null,
        int? edgeCount = null,
        int? nakedEdgeCount = null,
        int? shortEdgeCount = null,
        string? sourceProblem = null,
        string? analysisLimitReason = null)
    {
        if (string.IsNullOrWhiteSpace(label))
        {
            throw new ArgumentException("A snapshot label is required.", nameof(label));
        }

        Label = label;
        Kind = kind;
        IsValid = isValid;
        Bounds = bounds;
        Length = length;
        IsClosed = isClosed;
        StartPoint = startPoint;
        EndPoint = endPoint;
        IsPlanar = isPlanar;
        Degree = degree;
        SpanCount = spanCount;
        FaceCount = faceCount;
        EdgeCount = edgeCount;
        NakedEdgeCount = nakedEdgeCount;
        ShortEdgeCount = shortEdgeCount;
        SourceProblem = sourceProblem;
        AnalysisLimitReason = analysisLimitReason;
    }

    public string Label { get; }

    public GeometryKind Kind { get; }

    public bool? IsValid { get; }

    public Bounds3Value Bounds { get; }

    public double? Length { get; }

    public bool? IsClosed { get; }

    public Point3Value? StartPoint { get; }

    public Point3Value? EndPoint { get; }

    public bool? IsPlanar { get; }

    public int? Degree { get; }

    public int? SpanCount { get; }

    public int? FaceCount { get; }

    public int? EdgeCount { get; }

    public int? NakedEdgeCount { get; }

    public int? ShortEdgeCount { get; }

    public string? SourceProblem { get; }

    public string? AnalysisLimitReason { get; }

    public static GeometrySnapshot Failed(string label, string sourceProblem)
    {
        return new GeometrySnapshot(
            label,
            GeometryKind.Other,
            false,
            default,
            sourceProblem: sourceProblem);
    }

    public string ToSummaryLine()
    {
        var values = new List<string>
        {
            $"{Label}: {Kind}",
            IsValid == true ? "valid" : IsValid == false ? "INVALID" : "validity=not_checked"
        };

        AddNumber(values, "length", Length);
        AddBoolean(values, "closed", IsClosed);
        AddBoolean(values, "planar", IsPlanar);
        AddInteger(values, "degree", Degree);
        AddInteger(values, "spans", SpanCount);
        AddInteger(values, "faces", FaceCount);
        AddInteger(values, "edges", EdgeCount);
        AddInteger(values, "naked", NakedEdgeCount);
        AddInteger(values, "short_edges", ShortEdgeCount);

        return string.Join(" | ", values);
    }

    private static void AddNumber(ICollection<string> values, string name, double? value)
    {
        if (value.HasValue)
        {
            values.Add($"{name}={value.Value.ToString("G8", CultureInfo.InvariantCulture)}");
        }
    }

    private static void AddBoolean(ICollection<string> values, string name, bool? value)
    {
        if (value.HasValue)
        {
            values.Add($"{name}={(value.Value ? "yes" : "no")}");
        }
    }

    private static void AddInteger(ICollection<string> values, string name, int? value)
    {
        if (value.HasValue)
        {
            values.Add($"{name}={value.Value.ToString(CultureInfo.InvariantCulture)}");
        }
    }
}
