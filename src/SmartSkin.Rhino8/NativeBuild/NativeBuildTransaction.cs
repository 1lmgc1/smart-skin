using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;

namespace SmartSkin.Rhino8;

// Shared transaction runner used by the Rhino native Build adapter.
// Transaction bookkeeping never establishes geometric acceptance by itself.
internal static class NativeBuildTransaction
{
    internal const string OwnershipAttribute = "SmartSkin.NativeBuild.Transaction";

    internal interface IAcceptancePolicy
    {
        // Return a reason to block. A policy must inspect the sealed geometry evidence;
        // accepting requested continuity, sampled topology alone, or absent proof is not implicit.
        string? Rejection(State confirmed);
    }

    internal sealed class BlockedAcceptance : IAcceptancePolicy
    {
        internal static readonly BlockedAcceptance Instance = new();
        private BlockedAcceptance() { }
        public string Rejection(State confirmed) => "Native Build acceptance has not been authorized.";
    }

    internal interface IDocument
    {
        // All methods run synchronously on the supported Rhino command/UI path.
        // Reads must not pump events or mutate state. Capture actual archives, not cached
        // booleans. Generation is the preview/request revision, not an object-count revision.
        // ActiveUndoSerial must be zero unless recording is BOTH enabled and active.
        // Capture the native model-unit enum and actual metres-per-unit (including custom units).
        State CaptureState();

        // Add exactly one COPY of the confirmed cap. Before native insertion, assign
        // objectId and OwnershipAttribute=transactionMarker to its object attributes.
        // Reuse the already active command Undo record; do not Begin/End a nested record.
        // Never add an assembly, replace a source, or change the candidate receipt.
        Guid AddCap(State confirmed, Guid objectId, Guid transactionMarker);

        // Read live objects in the ORIGINAL document, even if the active document changed.
        // Return all objects with the planned ID OR exact attribute marker, including an
        // insertion followed by a native throw. An unmarked planned ID is a residual, not
        // permission to delete it. Do not omit it merely because its marker was changed.
        IReadOnlyList<CreatedCap> InspectInsertion(ulong documentSerial, Guid plannedId, Guid transactionMarker);

        // Recheck document, ID and attribute marker immediately before deleting this one
        // object. No global Undo or deletion by selection/count; return native success.
        bool DeleteCreatedCap(ulong documentSerial, Guid objectId, Guid transactionMarker);
    }

    internal sealed class State
    {
        private readonly byte[] _candidateArchive;
        private readonly byte[] _geometryEvidence;
        private readonly Dictionary<Guid, byte[]> _sources;
        private readonly Guid[] _objectIds;

        internal ulong DocumentSerial { get; }
        internal long Generation { get; }
        internal uint ActiveUndoSerial { get; }
        internal double AbsoluteTolerance { get; }
        internal double AngleToleranceRadians { get; }
        internal int ModelUnitSystem { get; }
        internal double MetresPerModelUnit { get; }
        internal Guid CandidateReceiptId { get; }
        internal bool Cancelled { get; }
        internal byte[] CandidateArchive => (byte[])_candidateArchive.Clone();
        internal byte[] GeometryEvidence => (byte[])_geometryEvidence.Clone();
        internal IReadOnlyList<Guid> ObjectIds => Array.AsReadOnly(_objectIds);

        internal State(ulong documentSerial, long generation, uint activeUndoSerial,
            double absoluteTolerance, double angleToleranceRadians, int modelUnitSystem, double metresPerModelUnit, Guid candidateReceiptId,
            byte[] candidateArchive, byte[] geometryEvidence,
            IReadOnlyDictionary<Guid, byte[]> sourceArchives, IEnumerable<Guid> objectIds,
            bool cancelled = false)
        {
            DocumentSerial = documentSerial; Generation = generation; ActiveUndoSerial = activeUndoSerial;
            AbsoluteTolerance = absoluteTolerance; AngleToleranceRadians = angleToleranceRadians;
            ModelUnitSystem = modelUnitSystem; MetresPerModelUnit = metresPerModelUnit;
            CandidateReceiptId = candidateReceiptId; Cancelled = cancelled;
            _candidateArchive = (byte[])candidateArchive.Clone();
            _geometryEvidence = (byte[])geometryEvidence.Clone();
            _sources = sourceArchives.ToDictionary(pair => pair.Key, pair => (byte[])pair.Value.Clone());
            _objectIds = objectIds.ToArray();
        }

        internal bool IsWellFormed => DocumentSerial != 0 && Generation >= 0 && ActiveUndoSerial != 0
            && PositiveFinite(AbsoluteTolerance) && PositiveFinite(AngleToleranceRadians) && PositiveFinite(MetresPerModelUnit)
            && CandidateReceiptId != Guid.Empty && _candidateArchive.Length > 0 && _geometryEvidence.Length > 0
            && _sources.Count > 0 && _sources.All(pair => pair.Key != Guid.Empty && pair.Value.Length > 0)
            && _objectIds.All(id => id != Guid.Empty) && _objectIds.Distinct().Count() == _objectIds.Length
            && _sources.Keys.All(id => _objectIds.Contains(id));

        internal bool SameReceipt(State other) => DocumentSerial == other.DocumentSerial
            && Generation == other.Generation && ActiveUndoSerial == other.ActiveUndoSerial
            && AbsoluteTolerance.Equals(other.AbsoluteTolerance) && AngleToleranceRadians.Equals(other.AngleToleranceRadians)
            && ModelUnitSystem == other.ModelUnitSystem && MetresPerModelUnit.Equals(other.MetresPerModelUnit)
            && CandidateReceiptId == other.CandidateReceiptId
            && _candidateArchive.SequenceEqual(other._candidateArchive)
            && _geometryEvidence.SequenceEqual(other._geometryEvidence)
            && _sources.Count == other._sources.Count
            && _sources.All(pair => other._sources.TryGetValue(pair.Key, out var bytes) && pair.Value.SequenceEqual(bytes));

        internal bool HasExactlyObjects(IEnumerable<Guid> ids) => new HashSet<Guid>(_objectIds).SetEquals(ids);
        private static bool PositiveFinite(double value) => value > 0 && !double.IsInfinity(value) && !double.IsNaN(value);
    }

    internal sealed class CreatedCap
    {
        private readonly byte[] _archive;
        internal Guid ObjectId { get; }
        internal Guid TransactionMarker { get; }
        internal CreatedCap(Guid objectId, Guid transactionMarker, byte[] archive)
        { ObjectId = objectId; TransactionMarker = transactionMarker; _archive = (byte[])archive.Clone(); }
        internal bool Matches(State state) => _archive.SequenceEqual(state.CandidateArchive);
    }

    internal sealed class Confirmation
    {
        private int _consumed;
        internal State Confirmed { get; }
        // Create only for a distinct native confirmation event of the displayed generation.
        internal Confirmation(State displayed) { Confirmed = displayed; }
        internal bool TryConsume() => Interlocked.Exchange(ref _consumed, 1) == 0;
    }

    internal enum Outcome { Added, Blocked, Cancelled, StaleConfirmation, Failed }
    internal enum Rollback { NotNeeded, Complete, Incomplete }

    internal sealed class Result
    {
        internal Outcome Status { get; }
        internal string Reason { get; }
        internal Guid AddedObjectId { get; }
        // Complete means only this transaction's tagged additions were removed. It does
        // not claim to reverse reentrant source edits or unrelated document changes.
        internal Rollback Cleanup { get; }
        internal bool AddAttempted { get; }
        internal Result(Outcome status, string reason, Guid addedObjectId = default,
            Rollback cleanup = Rollback.NotNeeded, bool addAttempted = false)
        { Status = status; Reason = reason; AddedObjectId = addedObjectId; Cleanup = cleanup; AddAttempted = addAttempted; }
    }

    // Acceptance is a mandatory input. Null and BlockedAcceptance both block; there is
    // no default policy that promotes missing G1/G2 evidence into acceptance.
    internal static Result Run(IDocument document, Confirmation confirmation, IAcceptancePolicy? acceptance,
        CancellationToken cancellation = default)
    {
        if (!confirmation.TryConsume()) return new Result(Outcome.StaleConfirmation, "Confirmation was already consumed.");
        var expected = confirmation.Confirmed;
        if (cancellation.IsCancellationRequested || expected.Cancelled)
            return new Result(Outcome.Cancelled, "Build cancelled before Add.");
        if (!expected.IsWellFormed) return new Result(Outcome.Blocked, "Incomplete receipt or no active command Undo record.");
        if (acceptance is null) return new Result(Outcome.Blocked, "An explicit acceptance policy is required.");

        Guid plannedId;
        do { plannedId = Guid.NewGuid(); } while (expected.ObjectIds.Contains(plannedId));
        var marker = Guid.NewGuid();
        var addAttempted = false;
        try
        {
            var rejection = acceptance.Rejection(expected);
            if (rejection is not null) return new Result(Outcome.Blocked, rejection);

            // This capture follows policy evaluation, so a callback cannot leave stale
            // evidence between validation and the native Add boundary.
            var before = document.CaptureState();
            if (cancellation.IsCancellationRequested || before.Cancelled)
                return new Result(Outcome.Cancelled, "Build cancelled before Add.");
            if (!before.IsWellFormed || !expected.SameReceipt(before) || !before.HasExactlyObjects(expected.ObjectIds))
                return new Result(Outcome.StaleConfirmation, "Document, sources, candidate, units, tolerances, generation or Undo changed before Add.");

            addAttempted = true;
            var added = document.AddCap(expected, plannedId, marker);
            if (added == Guid.Empty || added != plannedId)
                throw new InvalidOperationException("Native Add returned an empty or unexpected object ID.");

            var owned = document.InspectInsertion(expected.DocumentSerial, plannedId, marker);
            var after = document.CaptureState();
            if (cancellation.IsCancellationRequested || after.Cancelled)
                throw new OperationCanceledException("Build cancelled during Add.");
            if (!after.IsWellFormed || !expected.SameReceipt(after))
                throw new InvalidOperationException("Document, sources, candidate, units, tolerances, generation or Undo changed during Add.");
            if (!after.HasExactlyObjects(expected.ObjectIds.Concat(new[] { plannedId })))
                throw new InvalidOperationException("Add did not produce exactly one new object with all originals retained.");
            if (owned.Count != 1 || owned[0].ObjectId != plannedId || owned[0].TransactionMarker != marker || !owned[0].Matches(expected))
                throw new InvalidOperationException("The inserted cap's identity, transaction marker or geometry differs from the confirmed candidate.");
            return new Result(Outcome.Added, "Added exactly one confirmed cap in the existing command Undo record.", plannedId, addAttempted: true);
        }
        catch (Exception error)
        {
            var cleanup = addAttempted ? RollBack(document, expected, plannedId, marker) : Rollback.NotNeeded;
            var status = error is OperationCanceledException ? Outcome.Cancelled : Outcome.Failed;
            var reason = error.Message;
            if (cleanup == Rollback.Incomplete) reason += " Transaction rollback is incomplete; inspect the document before retrying.";
            return new Result(status, reason, cleanup: cleanup, addAttempted: addAttempted);
        }
    }

    private static Rollback RollBack(IDocument document, State expected, Guid plannedId, Guid marker)
    {
        // Take a bounded snapshot. Never chase objects created by reentrant deletion events.
        // A final read detects any remaining marked additions and reports incomplete rollback.
        try
        {
            var originalIds = new HashSet<Guid>(expected.ObjectIds);
            var owned = document.InspectInsertion(expected.DocumentSerial, plannedId, marker);
            var attemptedIds = new HashSet<Guid>();
            var uncertain = false;
            foreach (var cap in owned)
            {
                if (cap.ObjectId == Guid.Empty || originalIds.Contains(cap.ObjectId) || cap.TransactionMarker != marker)
                { uncertain = true; continue; }
                if (!attemptedIds.Add(cap.ObjectId)) continue;
                try { document.DeleteCreatedCap(expected.DocumentSerial, cap.ObjectId, marker); }
                catch (Exception) { /* Final live-object inspection determines cleanup, even after a throw. */ }
            }
            return !uncertain && document.InspectInsertion(expected.DocumentSerial, plannedId, marker).Count == 0
                ? Rollback.Complete : Rollback.Incomplete;
        }
        catch (Exception) { return Rollback.Incomplete; }
    }
}
