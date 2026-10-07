using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

// Tests the production sort helper with synthetic rational curves and a fixed four-side partition.
// This is managed curve arithmetic and ordering evidence, not native Brep/trim or Rhino execution.
public sealed class NativeCompareCornerOrderingTests
{
    private const double PartnerTolerance = 1e-6;

    [Fact]
    public void All720SelectionsAndBothTraversalsHaveOneDirectedSourceSequence()
    {
        var records = Fixture();
        var expected = Canonical(records, false);
        AssertFourRealCorners(records);
        var count = 0;
        foreach (var selection in Permutations(records))
            foreach (var backwards in new[] { false, true })
            {
                Assert.Equal(expected, Canonical(selection, backwards));
                count++;
            }
        Assert.Equal(1440, count);
        // The synthetic endpoint discrepancy actually exercises the former failure.
        Assert.True(new[] { RawCornerSequence(records, false), RawCornerSequence(records, true) }.Distinct().Count() > 1);
    }

    [Fact]
    public void ReversingAnyNativeRecordStillProducesTheSamePhysicalSourceDirections()
    {
        var original = Fixture();
        var expected = Canonical(original, false);
        foreach (var reversedRecord in Enumerable.Range(0, original.Length + 1))
        {
            var records = original.Select((record, i) => reversedRecord == original.Length || i == reversedRecord ? record.Reverse() : record).ToArray();
            foreach (var selection in Permutations(records))
                foreach (var backwards in new[] { false, true }) Assert.Equal(expected, Canonical(selection, backwards));
        }
    }

    [Fact]
    public void ExactRationalSplitsPreserveTheFourCornerPairsAndDirectedSourceCoverage()
    {
        var original = Fixture();
        var expected = Canonical(original, false);
        foreach (var record in original)
        {
            var split = record.Split(0.375);
            Assert.Contains(record.Curve.Weights, weight => weight != 1);
            for (var i = 0; i <= 16; i++)
            {
                var t = i / 16.0;
                EqualPoint(record.Curve.At(0.375 * t), split[0].Curve.At(t), 1e-12);
                EqualPoint(record.Curve.At(0.375 + 0.625 * t), split[1].Curve.At(t), 1e-12);
            }
        }
        // Every original component is genuinely split; its source interval is retained for comparison.
        // Endpoint partners and the four role boundaries are unchanged, with new smooth interior seams.
        var splitRecords = original.SelectMany(record => record.Split(0.375)).ToArray();
        AssertFourRealCorners(original);
        AssertFourRealCorners(splitRecords);
        for (var offset = 0; offset < splitRecords.Length; offset++)
            foreach (var backwards in new[] { false, true })
            {
                var rotated = splitRecords.Skip(offset).Concat(splitRecords.Take(offset)).ToArray();
                Assert.Equal(expected, Canonical(rotated, backwards));
                Assert.Equal(expected, Canonical(Enumerable.Reverse(rotated).ToArray(), backwards));
            }
    }

    [Fact]
    public void ActualHomogeneousDegreeElevationPreservesOrderingAcrossAllSelections()
    {
        var original = Fixture();
        var expected = Canonical(original, false);
        var elevated = original.Select(record => record.WithCurve(record.Curve.Elevate().Elevate().Elevate())).ToArray();
        for (var i = 0; i < original.Length; i++)
        {
            Assert.Equal(original[i].Curve.Degree + 3, elevated[i].Curve.Degree);
            Assert.Equal(original[i].Curve.Degree + 4, elevated[i].Curve.Controls.Length);
            Assert.Contains(elevated[i].Curve.Weights, weight => weight != 1);
            for (var station = 0; station <= 32; station++)
                EqualPoint(original[i].Curve.At(station / 32.0), elevated[i].Curve.At(station / 32.0), 1e-12);
        }
        AssertFourRealCorners(elevated);
        foreach (var selection in Permutations(elevated))
            foreach (var backwards in new[] { false, true }) Assert.Equal(expected, Canonical(selection, backwards));
    }

    [Fact]
    public void PairRepresentativesAreCommutativeAndNeitherEndpointArrayChanges()
    {
        var incoming = new[] { P(1e-12, 0), P(4, 0), P(4, 3), P(-1e-12, 3) };
        var outgoing = new[] { P(-3e-12, 0), P(4 + 1e-12, 0), P(4, 3), P(3e-12, 3) };
        var beforeIncoming = incoming.ToArray(); var beforeOutgoing = outgoing.ToArray();
        Assert.True(NativeCompareCornerOrdering.TryChoose(incoming, outgoing, out var first, out var reverse));
        for (var mask = 0; mask < 16; mask++)
        {
            var a = incoming.Select((point, i) => (mask & (1 << i)) == 0 ? point : outgoing[i]).ToArray();
            var b = outgoing.Select((point, i) => (mask & (1 << i)) == 0 ? point : incoming[i]).ToArray();
            Assert.True(NativeCompareCornerOrdering.TryChoose(a, b, out var nextFirst, out var nextReverse));
            Assert.Equal(first, nextFirst); Assert.Equal(reverse, nextReverse);
        }
        Assert.Equal(beforeIncoming, incoming); Assert.Equal(beforeOutgoing, outgoing);
    }

    [Fact]
    public void TiedOrNonfiniteCornerKeysAreRejectedWithoutAnEncounterOrderFallback()
    {
        var points = new[] { P(0, 0), P(4, 0), P(4, 3), P(0, 3) };
        var tied = points.ToArray(); tied[2] = tied[1];
        Assert.False(NativeCompareCornerOrdering.TryChoose(tied, tied, out _, out _));
        var invalid = points.ToArray(); invalid[1] = P(double.NaN, 0);
        Assert.False(NativeCompareCornerOrdering.TryChoose(points, invalid, out _, out _));
        invalid[1] = P(double.PositiveInfinity, 0);
        Assert.False(NativeCompareCornerOrdering.TryChoose(invalid, points, out _, out _));
    }

    [Fact]
    public void FiniteExtremeCoordinateAveragesDoNotOverflow()
    {
        var points = new[] { P(double.MaxValue, 0), P(double.MaxValue, 1), P(double.MaxValue, 2), P(double.MaxValue, 3) };
        Assert.True(NativeCompareCornerOrdering.TryChoose(points, points, out var first, out var reverse));
        Assert.Equal(0, first); Assert.False(reverse);
    }

    private static NativeCompareCornerPoint P(double x, double y, double z = 0) => new(x, y, z);
    private static void EqualPoint(NativeCompareCornerPoint a, NativeCompareCornerPoint b, double tolerance)
    {
        Assert.InRange(Math.Abs(a.X - b.X), 0, tolerance);
        Assert.InRange(Math.Abs(a.Y - b.Y), 0, tolerance);
        Assert.InRange(Math.Abs(a.Z - b.Z), 0, tolerance);
    }

    private sealed class Record
    {
        internal readonly string Component;
        internal readonly int Role;
        internal readonly RationalBezier Curve;
        internal readonly double From, To;
        internal Record(string component, int role, RationalBezier curve, double from = 0, double to = 1)
        { Component = component; Role = role; Curve = curve; From = from; To = to; }
        internal Record WithCurve(RationalBezier curve) => new(Component, Role, curve, From, To);
        internal Record Reverse() => new(Component, Role, Curve.Reverse(), To, From);
        internal Record[] Split(double t)
        {
            var pieces = Curve.Split(t); var middle = From + (To - From) * t;
            return new[] { new Record(Component, Role, pieces[0], From, middle), new Record(Component, Role, pieces[1], middle, To) };
        }
    }
    private sealed class Directed
    {
        internal readonly Record Record;
        internal bool Reverse;
        internal Directed(Record record, bool reverse) { Record = record; Reverse = reverse; }
        internal NativeCompareCornerPoint Start => Record.Curve.At(Reverse ? 1 : 0);
        internal NativeCompareCornerPoint End => Record.Curve.At(Reverse ? 0 : 1);
    }
    private static Record[] Fixture()
    {
        // Synthetic geometry only. Slightly unequal incident endpoints make raw endpoint sorting unstable.
        var bottom = RationalBezier.Make(P(-2e-12, 0), P(2, -0.4, 0.2), P(4, 0), 0.8).Split(0.5);
        var top = RationalBezier.Make(P(4 + 2e-12, 3), P(2, 3.5, 0.3), P(1e-12, 3), 0.7).Split(0.5);
        return new[]
        {
            new Record("bottom-a", 0, bottom[0]), new Record("bottom-b", 0, bottom[1]).Reverse(),
            new Record("right", 1, RationalBezier.Make(P(4 + 1e-12, 0), P(4.5, 1.5, 0.2), P(4, 3), 1.2)),
            new Record("top-a", 2, top[0]), new Record("top-b", 2, top[1]).Reverse(),
            new Record("left", 3, RationalBezier.Make(P(-1e-12, 3), P(-0.5, 1.5, 0.1), P(4e-12, 0), 0.9)),
        };
    }

    private static List<List<Directed>> Partition(Record[] records, bool backwards)
    {
        // Test fixture adapter: the strict pairing rule and known four roles are unchanged inputs
        // to the production ordering helper. This does not purport to execute native parent recognition.
        var endpoints = records.SelectMany(record => new[] { record.Curve.At(0), record.Curve.At(1) }).ToArray();
        var partners = new int[endpoints.Length];
        for (var i = 0; i < endpoints.Length; i++)
        {
            var matches = Enumerable.Range(0, endpoints.Length).Where(j => i / 2 != j / 2
                && Distance(endpoints[i], endpoints[j]) <= PartnerTolerance).ToArray();
            Assert.Single(matches); partners[i] = matches[0];
        }
        var ordered = new List<Directed>();
        var start = backwards ? 1 : 0; var current = start;
        do
        {
            ordered.Add(new Directed(records[current / 2], current % 2 != 0));
            current = partners[current ^ 1];
            Assert.True(ordered.Count <= records.Length);
        } while (current != start);
        Assert.Equal(records.Length, ordered.Count);
        var firstBoundary = Enumerable.Range(0, ordered.Count).First(i =>
            ordered[i].Record.Role != ordered[(i + ordered.Count - 1) % ordered.Count].Record.Role);
        ordered = ordered.Skip(firstBoundary).Concat(ordered.Take(firstBoundary)).ToList();
        var sides = new List<List<Directed>>();
        foreach (var directed in ordered)
        {
            if (sides.Count == 0 || sides[sides.Count - 1][0].Record.Role != directed.Record.Role) sides.Add(new List<Directed>());
            sides[sides.Count - 1].Add(directed);
        }
        Assert.Equal(4, sides.Count);
        return sides;
    }
    private static void AssertFourRealCorners(Record[] records)
    {
        var walk = Partition(records, false).SelectMany(side => side).ToArray();
        var corners = 0;
        for (var i = 0; i < walk.Length; i++)
        {
            var previous = walk[(i + walk.Length - 1) % walk.Length]; var next = walk[i];
            var a = previous.Record.Curve.EndpointTangent(previous.Reverse ? 0 : 1);
            var b = next.Record.Curve.EndpointTangent(next.Reverse ? 1 : 0);
            var sign = previous.Reverse == next.Reverse ? 1 : -1;
            var dot = sign * (a.X * b.X + a.Y * b.Y + a.Z * b.Z);
            var norm = Math.Sqrt((a.X * a.X + a.Y * a.Y + a.Z * a.Z) * (b.X * b.X + b.Y * b.Y + b.Z * b.Z));
            Assert.True(norm > 0);
            if (dot / norm < Math.Cos(1e-5)) corners++;
        }
        Assert.Equal(4, corners);
    }
    private static double Distance(NativeCompareCornerPoint a, NativeCompareCornerPoint b) =>
        Math.Sqrt((a.X - b.X) * (a.X - b.X) + (a.Y - b.Y) * (a.Y - b.Y) + (a.Z - b.Z) * (a.Z - b.Z));
    private static string Canonical(Record[] records, bool backwards)
    {
        var sides = Partition(records, backwards);
        var incoming = Enumerable.Range(0, 4).Select(i => sides[(i + 3) % 4].Last().End).ToArray();
        var outgoing = sides.Select(side => side[0].Start).ToArray();
        Assert.True(NativeCompareCornerOrdering.TryChoose(incoming, outgoing, out var first, out var reverse));
        sides = Enumerable.Range(0, 4).Select(i => sides[(first + i) % 4]).ToList();
        if (reverse)
        {
            sides.Reverse();
            foreach (var side in sides) { side.Reverse(); foreach (var edge in side) edge.Reverse = !edge.Reverse; }
        }
        // Stable original component IDs and directed original parameter coverage, never encounter owner indices.
        return string.Join("|", sides.Select(side => Signature(side)));
    }
    private static string Signature(List<Directed> side)
    {
        var spans = new List<(string Component, double From, double To)>();
        foreach (var edge in side)
        {
            var from = edge.Reverse ? edge.Record.To : edge.Record.From;
            var to = edge.Reverse ? edge.Record.From : edge.Record.To;
            if (spans.Count > 0 && spans.Last().Component == edge.Record.Component && spans.Last().To == from)
            {
                var previous = spans.Last(); spans[spans.Count - 1] = (previous.Component, previous.From, to);
            }
            else spans.Add((edge.Record.Component, from, to));
        }
        return string.Join(",", spans.Select(span => span.Component + ":" + span.From.ToString("R", CultureInfo.InvariantCulture)
            + "->" + span.To.ToString("R", CultureInfo.InvariantCulture)));
    }
    private static string RawCornerSequence(Record[] records, bool backwards)
    {
        var sides = Partition(records, backwards);
        var first = Enumerable.Range(0, 4).OrderBy(i => sides[i][0].Start.X)
            .ThenBy(i => sides[i][0].Start.Y).ThenBy(i => sides[i][0].Start.Z).First();
        return sides[first][0].Record.Role.ToString(CultureInfo.InvariantCulture);
    }
    private static IEnumerable<Record[]> Permutations(Record[] records)
    {
        var working = records.ToArray();
        IEnumerable<Record[]> Walk(int position)
        {
            if (position == working.Length) { yield return working.ToArray(); yield break; }
            for (var i = position; i < working.Length; i++)
            {
                (working[position], working[i]) = (working[i], working[position]);
                foreach (var result in Walk(position + 1)) yield return result;
                (working[position], working[i]) = (working[i], working[position]);
            }
        }
        return Walk(0);
    }

    private sealed class RationalBezier
    {
        internal readonly double[][] Controls; // Homogeneous (wx, wy, wz, w), not metadata-only degree labels.
        internal int Degree => Controls.Length - 1;
        internal IEnumerable<double> Weights => Controls.Select(point => point[3]);
        internal RationalBezier(double[][] controls) => Controls = controls;
        internal static RationalBezier Make(NativeCompareCornerPoint a, NativeCompareCornerPoint b, NativeCompareCornerPoint c, double weight) =>
            new(new[] { new[] { a.X, a.Y, a.Z, 1 }, new[] { b.X * weight, b.Y * weight, b.Z * weight, weight }, new[] { c.X, c.Y, c.Z, 1 } });
        private static double[] Mix(double[] a, double[] b, double t) => Enumerable.Range(0, 4).Select(i => (1 - t) * a[i] + t * b[i]).ToArray();
        internal NativeCompareCornerPoint At(double t)
        {
            var row = Controls.ToArray();
            for (var size = row.Length; size > 1; size--)
                for (var i = 0; i < size - 1; i++) row[i] = Mix(row[i], row[i + 1], t);
            return P(row[0][0] / row[0][3], row[0][1] / row[0][3], row[0][2] / row[0][3]);
        }
        internal NativeCompareCornerPoint EndpointTangent(int end)
        {
            var h = end == 0 ? Controls[0] : Controls.Last();
            var before = end == 0 ? Controls[0] : Controls[Controls.Length - 2];
            var after = end == 0 ? Controls[1] : Controls.Last();
            var derivative = Enumerable.Range(0, 4).Select(i => Degree * (after[i] - before[i])).ToArray();
            return P((derivative[0] - h[0] / h[3] * derivative[3]) / h[3],
                (derivative[1] - h[1] / h[3] * derivative[3]) / h[3],
                (derivative[2] - h[2] / h[3] * derivative[3]) / h[3]);
        }
        internal RationalBezier Reverse() => new(Enumerable.Reverse(Controls).Select(point => point.ToArray()).ToArray());
        internal RationalBezier[] Split(double t)
        {
            var row = Controls.Select(point => point.ToArray()).ToArray();
            var left = new List<double[]> { row[0] }; var right = new List<double[]> { row.Last() };
            for (var size = row.Length; size > 1; size--)
            {
                row = Enumerable.Range(0, size - 1).Select(i => Mix(row[i], row[i + 1], t)).ToArray();
                left.Add(row[0]); right.Add(row.Last());
            }
            right.Reverse();
            return new[] { new RationalBezier(left.ToArray()), new RationalBezier(right.ToArray()) };
        }
        internal RationalBezier Elevate()
        {
            var raised = new double[Controls.Length + 1][];
            raised[0] = Controls[0].ToArray(); raised[raised.Length - 1] = Controls.Last().ToArray();
            for (var i = 1; i < raised.Length - 1; i++) raised[i] = Mix(Controls[i], Controls[i - 1], i / (double)(Degree + 1));
            return new RationalBezier(raised);
        }
    }
}
