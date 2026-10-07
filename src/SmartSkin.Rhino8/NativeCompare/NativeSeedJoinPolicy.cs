using System;
using System.Collections.Generic;
using System.Linq;

namespace SmartSkin.Rhino8;

// Pure decisions for the read-only Join probe. These do not infer smoothness from topology.
internal static class NativeSeedJoinPolicy
{
    internal readonly struct FaceEvidence
    {
        internal Guid Tag { get; }
        internal bool SurfaceAndDomainUnchanged { get; }
        internal FaceEvidence(Guid tag, bool surfaceAndDomainUnchanged)
        { Tag = tag; SurfaceAndDomainUnchanged = surfaceAndDomainUnchanged; }
    }

    internal static bool ResolveFaceProvenance(IReadOnlyDictionary<Guid, int> expectedFaces,
        IReadOnlyList<IReadOnlyList<FaceEvidence>> outputFaces, IReadOnlyList<int[]>? nativeMap,
        int inputCount, out int[][] tagDerivedContributors)
    {
        tagDerivedContributors = new int[outputFaces.Count][];
        var seen = new HashSet<Guid>();
        var resolved = inputCount >= 2 && expectedFaces.Count > 0 && outputFaces.Count > 0
            && expectedFaces.Keys.All(tag => tag != Guid.Empty)
            && expectedFaces.Values.All(input => input >= 0 && input < inputCount)
            && expectedFaces.Values.Distinct().Count() == inputCount;
        for (var output = 0; output < outputFaces.Count; output++)
        {
            var contributors = new HashSet<int>();
            resolved &= outputFaces[output].Count > 0;
            foreach (var face in outputFaces[output])
            {
                var known = expectedFaces.TryGetValue(face.Tag, out var input);
                resolved &= known && face.SurfaceAndDomainUnchanged && seen.Add(face.Tag);
                if (known) contributors.Add(input);
            }
            tagDerivedContributors[output] = contributors.OrderBy(input => input).ToArray();
        }
        resolved &= seen.Count == expectedFaces.Count && expectedFaces.Keys.All(seen.Contains);
        // Rhino explicitly permits an absent map. It cannot veto independently complete face
        // provenance. A supplied but contradictory or malformed map must still reject it.
        if (nativeMap is not null)
        {
            resolved &= nativeMap.Count == outputFaces.Count;
            for (var output = 0; output < outputFaces.Count; output++)
                resolved &= nativeMap.Count > output
                    && ContributorsAgree(nativeMap[output], tagDerivedContributors[output], inputCount);
        }
        return resolved;
    }

    internal static bool OrdinarySelectedSeam(bool interior, int trimCount, bool allMated,
        int distinctFaces, bool hasSeedFace, bool hasExpectedParentFace, bool provenanceResolved) =>
        provenanceResolved && interior && trimCount == 2 && allMated && distinctFaces == 2
        && hasSeedFace && hasExpectedParentFace;

    internal static bool ContributorsAgree(IEnumerable<int>? nativeContributors, IEnumerable<int> faceContributors,
        int inputCount)
    {
        if (nativeContributors is null || inputCount < 2) return false;
        var native = nativeContributors.ToArray(); var faces = faceContributors.Distinct().OrderBy(i => i).ToArray();
        return native.Length > 0 && native.All(i => i >= 0 && i < inputCount)
            && native.Distinct().Count() == native.Length
            && native.OrderBy(i => i).SequenceEqual(faces);
    }

    // Multiple hits are unambiguous only at one actual output topological vertex.
    internal static bool OneTopologicalLocation(IReadOnlyList<(int Output, int Vertex)> hits)
    {
        if (hits.Count == 1) return true;
        return hits.Count > 1 && hits[0].Vertex >= 0
            && hits.All(hit => hit.Output == hits[0].Output && hit.Vertex == hits[0].Vertex);
    }

    internal static bool SampledSelectedOpeningJoined(bool outputsValid, bool provenanceResolved,
        int selectedPieces, int completelyCoveredPieces, int seedBoundaryEdges, int completelyCoveredSeedEdges,
        int seedNakedEdges, int seedNonManifoldEdges, int selectedParentNakedEdges, int unresolvedStations) =>
        outputsValid && provenanceResolved && selectedPieces > 0 && selectedPieces == completelyCoveredPieces
        && seedBoundaryEdges > 0 && seedBoundaryEdges == completelyCoveredSeedEdges
        && seedNakedEdges == 0 && seedNonManifoldEdges == 0 && selectedParentNakedEdges == 0 && unresolvedStations == 0;
}
