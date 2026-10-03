using System;
using System.Collections.Generic;
using System.Linq;

namespace SmartSkin.Core.Construction;

/// <summary>Topology only: a self-loop and a segmented cycle are equivalent.
/// This deliberately makes no assertion about geometric distance or continuity.</summary>
public sealed class BoundaryCycleTopology
{
    private BoundaryCycleTopology(int components, int ends, int junctions, string reason)
    {
        Components = components;
        Ends = ends;
        Junctions = junctions;
        Reason = reason;
    }

    public int Components { get; }
    public int Ends { get; }
    public int Junctions { get; }
    public string Reason { get; }
    public bool IsSingleCycle => Reason == "CLOSED_BOUNDARY";

    public static BoundaryCycleTopology Analyze(IReadOnlyList<(int Start, int End)> edges)
    {
        if (edges is null) throw new ArgumentNullException(nameof(edges));
        if (edges.Count == 0) return new BoundaryCycleTopology(0, 0, 0, "NO_NAKED_BOUNDARY");
        var adjacent = new Dictionary<int, List<int>>();
        foreach (var edge in edges)
        {
            if (edge.Start < 0 || edge.End < 0)
                return new BoundaryCycleTopology(0, 0, 0, "INVALID_BOUNDARY_VERTEX");
            if (!adjacent.TryGetValue(edge.Start, out var from))
                adjacent[edge.Start] = from = new List<int>();
            if (!adjacent.TryGetValue(edge.End, out var to))
                adjacent[edge.End] = to = new List<int>();
            from.Add(edge.End);
            to.Add(edge.Start); // a self-loop contributes degree two
        }
        var components = 0;
        var visited = new HashSet<int>();
        foreach (var vertex in adjacent.Keys)
        {
            if (!visited.Add(vertex)) continue;
            components++;
            var pending = new Stack<int>();
            pending.Push(vertex);
            while (pending.Count > 0)
                foreach (var next in adjacent[pending.Pop()])
                    if (visited.Add(next)) pending.Push(next);
        }
        var ends = adjacent.Count(pair => pair.Value.Count == 1);
        var junctions = adjacent.Count(pair => pair.Value.Count > 2);
        var reason = components != 1 ? "MULTIPLE_BOUNDARY_COMPONENTS"
            : junctions > 0 ? "BRANCHED_BOUNDARY"
            : ends > 0 ? "OPEN_BOUNDARY_CHAIN" : "CLOSED_BOUNDARY";
        return new BoundaryCycleTopology(components, ends, junctions, reason);
    }
}
