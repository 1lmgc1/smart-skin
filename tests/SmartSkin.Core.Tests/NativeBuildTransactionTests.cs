using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using SmartSkin.Rhino8;
using Xunit;
using Transaction = SmartSkin.Rhino8.NativeBuildTransaction;

namespace SmartSkin.Core.Tests;

public sealed class NativeBuildTransactionTests
{
    [Fact]
    public void AddsOneCopyWithKnownIdentityAndMarkerInExistingUndo()
    {
        var doc = new FakeDocument();
        var result = Run(doc);
        Assert.Equal(Transaction.Outcome.Added, result.Status);
        Assert.True(result.AddAttempted);
        Assert.Equal(Transaction.Rollback.NotNeeded, result.Cleanup);
        Assert.Equal(doc.PlannedId, result.AddedObjectId);
        Assert.NotEqual(Guid.Empty, doc.Marker);
        Assert.Equal(19u, doc.UndoAtInsertion);
        Assert.Equal(1, doc.AddCalls);
        Assert.Equal(3, doc.Objects.Count);
        Assert.Equal(doc.Candidate, doc.Objects[result.AddedObjectId].Archive);
        Assert.Empty(doc.DeleteCalls);
        AssertOriginalsIntact(doc);
    }

    [Fact]
    public void MissingOrBlockedPolicyNeverAdds()
    {
        foreach (var policy in new Transaction.IAcceptancePolicy?[] { null, Transaction.BlockedAcceptance.Instance })
        {
            var doc = new FakeDocument();
            var result = Transaction.Run(doc, new Transaction.Confirmation(doc.CaptureState()), policy);
            Assert.Equal(Transaction.Outcome.Blocked, result.Status);
            Assert.False(result.AddAttempted);
            Assert.Equal(0, doc.AddCalls);
        }
    }

    [Theory]
    [InlineData("empty-proof")]
    [InlineData("no-undo")]
    [InlineData("recording-disabled")]
    [InlineData("empty-candidate")]
    [InlineData("empty-candidate-signature")]
    [InlineData("invalid-tolerance")]
    public void IncompleteReceiptCannotBeAcceptedByEvenAnAllowingPolicy(string change)
    {
        var doc = new FakeDocument();
        switch (change)
        {
            case "empty-proof": doc.Evidence = Array.Empty<byte>(); break;
            case "no-undo": doc.Undo = 0; break;
            case "recording-disabled": doc.RecordingEnabled = false; break;
            case "empty-candidate": doc.Candidate = Array.Empty<byte>(); break;
            case "empty-candidate-signature": doc.CandidateGeometrySignature = Array.Empty<byte>(); break;
            case "invalid-tolerance": doc.AbsoluteTolerance = double.NaN; break;
        }
        var result = Transaction.Run(doc, new Transaction.Confirmation(doc.CaptureState()), new TestAcceptance(_ => null));
        Assert.Equal(Transaction.Outcome.Blocked, result.Status);
        Assert.Equal(0, doc.AddCalls);
    }

    [Theory]
    [InlineData("source-archive")]
    [InlineData("source-identity")]
    [InlineData("candidate-archive")]
    [InlineData("candidate-signature")]
    [InlineData("candidate-receipt")]
    [InlineData("proof")]
    [InlineData("absolute-tolerance")]
    [InlineData("angle-tolerance")]
    [InlineData("model-units")]
    [InlineData("unit-scale")]
    [InlineData("generation")]
    [InlineData("undo")]
    [InlineData("recording-disabled")]
    [InlineData("document")]
    [InlineData("unrelated-same-count")]
    public void ChangedReceiptOrObjectSetBeforeAddConsumesConfirmationWithoutMutation(string change)
    {
        var doc = new FakeDocument();
        var confirmation = new Transaction.Confirmation(doc.CaptureState());
        Change(doc, change);
        var result = Transaction.Run(doc, confirmation, Acceptance());
        Assert.Equal(Transaction.Outcome.StaleConfirmation, result.Status);
        Assert.False(result.AddAttempted);
        Assert.Equal(0, doc.AddCalls);
        Assert.Empty(doc.DeleteCalls);
        Assert.Equal(Transaction.Outcome.StaleConfirmation, Transaction.Run(doc, confirmation, Acceptance()).Status);
    }

    [Theory]
    [InlineData("source-archive")]
    [InlineData("source-identity")]
    [InlineData("candidate-archive")]
    [InlineData("candidate-signature")]
    [InlineData("candidate-receipt")]
    [InlineData("proof")]
    [InlineData("absolute-tolerance")]
    [InlineData("angle-tolerance")]
    [InlineData("model-units")]
    [InlineData("unit-scale")]
    [InlineData("generation")]
    [InlineData("undo")]
    [InlineData("recording-disabled")]
    [InlineData("document")]
    public void ReentrantInvalidationDuringAddRemovesOnlyItsCap(string change)
    {
        var doc = new FakeDocument();
        doc.AfterInsert = () => Change(doc, change);
        var result = Run(doc);
        Assert.Equal(Transaction.Outcome.Failed, result.Status);
        Assert.Equal(Transaction.Rollback.Complete, result.Cleanup);
        Assert.Equal(doc.PlannedId, Assert.Single(doc.DeleteCalls));
        Assert.False(doc.Objects.ContainsKey(doc.PlannedId));
        Assert.True(doc.Objects.ContainsKey(doc.UnrelatedId));
        Assert.DoesNotContain(doc.SourceId, doc.DeleteCalls);
        Assert.All(doc.InspectedDocumentSerials, serial => Assert.Equal(7ul, serial));
    }

    [Fact]
    public void PolicyCallbackCannotInvalidateSourcesBeforeTheFinalPreAddCheck()
    {
        var doc = new FakeDocument();
        var confirmation = new Transaction.Confirmation(doc.CaptureState());
        var policy = new TestAcceptance(state =>
        {
            Assert.Equal(new byte[] { 9, 8, 7 }, state.GeometryEvidence);
            doc.Objects[doc.SourceId].Archive[0]++;
            return null;
        });
        var result = Transaction.Run(doc, confirmation, policy);
        Assert.Equal(Transaction.Outcome.StaleConfirmation, result.Status);
        Assert.Equal(0, doc.AddCalls);
    }

    [Fact]
    public void ReentrantDuplicateConfirmationCannotAddTwice()
    {
        var doc = new FakeDocument();
        var confirmation = new Transaction.Confirmation(doc.CaptureState());
        Transaction.Result? duplicate = null;
        doc.AfterInsert = () => duplicate = Transaction.Run(doc, confirmation, Acceptance());
        Assert.Equal(Transaction.Outcome.Added, Transaction.Run(doc, confirmation, Acceptance()).Status);
        Assert.Equal(Transaction.Outcome.StaleConfirmation, duplicate!.Status);
        Assert.Equal(Transaction.Outcome.StaleConfirmation, Transaction.Run(doc, confirmation, Acceptance()).Status);
        Assert.Equal(1, doc.AddCalls);
        Assert.Empty(doc.DeleteCalls);
    }

    [Fact]
    public void CancellationBeforeAddAndDuringNativeInsertionHasDifferentCleanup()
    {
        var before = new FakeDocument();
        using var cancelled = new CancellationTokenSource();
        cancelled.Cancel();
        var noAdd = Transaction.Run(before, new Transaction.Confirmation(before.CaptureState()), Acceptance(), cancelled.Token);
        Assert.Equal(Transaction.Outcome.Cancelled, noAdd.Status);
        Assert.Equal(Transaction.Rollback.NotNeeded, noAdd.Cleanup);
        Assert.Equal(0, before.AddCalls);

        var during = new FakeDocument();
        using var cancellation = new CancellationTokenSource();
        during.AfterInsert = cancellation.Cancel;
        var rolledBack = Transaction.Run(during, new Transaction.Confirmation(during.CaptureState()), Acceptance(), cancellation.Token);
        Assert.Equal(Transaction.Outcome.Cancelled, rolledBack.Status);
        Assert.Equal(Transaction.Rollback.Complete, rolledBack.Cleanup);
        AssertOriginalsIntact(during);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void CancelledPreviewBeforeRunOrDuringCaptureNeverAdds(bool duringCapture)
    {
        var doc = new FakeDocument { Cancelled = !duringCapture };
        var confirmation = new Transaction.Confirmation(doc.CaptureState());
        if (duringCapture) doc.BeforeCapture = () => doc.Cancelled = true;
        Assert.Equal(Transaction.Outcome.Cancelled, Transaction.Run(doc, confirmation, Acceptance()).Status);
        Assert.Equal(0, doc.AddCalls);
    }

    [Theory]
    [InlineData("empty-before")]
    [InlineData("throw-before")]
    [InlineData("empty-after")]
    [InlineData("throw-after")]
    [InlineData("wrong-id")]
    public void FailedAddCleansInsertionEvenWithoutSuccessfulReturn(string mode)
    {
        var doc = new FakeDocument { AddMode = mode };
        var result = Run(doc);
        Assert.Equal(Transaction.Outcome.Failed, result.Status);
        Assert.True(result.AddAttempted);
        Assert.Equal(Transaction.Rollback.Complete, result.Cleanup);
        Assert.Equal(2, doc.Objects.Count);
        AssertOriginalsIntact(doc);
        Assert.DoesNotContain(doc.SourceId, doc.DeleteCalls);
        if (mode.EndsWith("before", StringComparison.Ordinal)) Assert.Empty(doc.DeleteCalls);
        else Assert.Equal(doc.PlannedId, Assert.Single(doc.DeleteCalls));
    }

    [Fact]
    public void UnrelatedNewObjectInvalidatesExactDeltaButIsPreservedDuringRollback()
    {
        var doc = new FakeDocument();
        var other = Guid.NewGuid();
        doc.AfterInsert = () => doc.Objects.Add(other, new FakeObject(Guid.Empty, new byte[] { 33 }));
        var result = Run(doc);
        Assert.Equal(Transaction.Outcome.Failed, result.Status);
        Assert.Equal(Transaction.Rollback.Complete, result.Cleanup);
        Assert.True(doc.Objects.ContainsKey(other));
        Assert.False(doc.Objects.ContainsKey(doc.PlannedId));
        Assert.Equal(doc.PlannedId, Assert.Single(doc.DeleteCalls));
        AssertOriginalsIntact(doc);
    }

    [Fact]
    public void ReentrantDeletionOfUnrelatedOriginalCannotMasqueradeAsOneNewObject()
    {
        var doc = new FakeDocument();
        var other = Guid.NewGuid();
        doc.AfterInsert = () =>
        {
            doc.Objects.Remove(doc.UnrelatedId);
            doc.Objects.Add(other, new FakeObject(Guid.Empty, new byte[] { 33 }));
        };
        var result = Run(doc);
        Assert.Equal(Transaction.Outcome.Failed, result.Status);
        Assert.Equal(Transaction.Rollback.Complete, result.Cleanup);
        Assert.Equal(doc.PlannedId, Assert.Single(doc.DeleteCalls));
        Assert.True(doc.Objects.ContainsKey(other));
    }

    [Fact]
    public void ChangedInsertedGeometryFailsAndRollsBack()
    {
        var doc = new FakeDocument();
        doc.AfterInsert = () =>
        {
            doc.Objects[doc.PlannedId].Archive[0]++;
            doc.Objects[doc.PlannedId].GeometrySignature[0]++;
        };
        var result = Run(doc);
        Assert.Equal(Transaction.Outcome.Failed, result.Status);
        Assert.StartsWith("BUILD_INSERTED_CAP_GEOMETRY_MISMATCH:", result.Reason);
        Assert.Equal(Transaction.Rollback.Complete, result.Cleanup);
        Assert.Equal(new byte[] { 10, 20, 30 }, doc.Candidate);
        Assert.Equal(doc.PlannedId, Assert.Single(doc.DeleteCalls));
        AssertOriginalsIntact(doc);
    }

    [Fact]
    public void InsertedSerializationMetadataMayDifferWhileCandidateArchiveAndGeometryStaySealed()
    {
        var doc = new FakeDocument();
        // Only the inserted object's serialized metadata changes. Its exact geometric
        // content and the original, still-disposable candidate remain unchanged.
        doc.AfterInsert = () => doc.Objects[doc.PlannedId].Archive = new byte[] { 10, 20, 30, 99 };
        var result = Run(doc);
        Assert.Equal(Transaction.Outcome.Added, result.Status);
        Assert.Equal(new byte[] { 10, 20, 30 }, doc.Candidate);
        Assert.False(doc.Candidate.SequenceEqual(doc.Objects[doc.PlannedId].Archive));
        Assert.Equal(doc.CandidateGeometrySignature, doc.Objects[doc.PlannedId].GeometrySignature);
        Assert.Empty(doc.DeleteCalls);
        AssertOriginalsIntact(doc);
    }

    [Theory]
    [InlineData("missing", "BUILD_INSERTED_CAP_COUNT_MISMATCH:")]
    [InlineData("duplicate", "BUILD_INSERTED_CAP_COUNT_MISMATCH:")]
    [InlineData("wrong-id", "BUILD_INSERTED_CAP_ID_MISMATCH:")]
    [InlineData("wrong-marker", "BUILD_INSERTED_CAP_MARKER_MISMATCH:")]
    [InlineData("empty-signature", "BUILD_INSERTED_CAP_GEOMETRY_UNAVAILABLE:")]
    [InlineData("changed-signature", "BUILD_INSERTED_CAP_GEOMETRY_MISMATCH:")]
    public void FinalInspectionReportsTheSpecificFailedFieldAndRollsBackOwnedCap(string change, string reasonPrefix)
    {
        var doc = new FakeDocument();
        // Fault only the first inspection; rollback still receives the live native ID
        // and marker and must remove the real insertion, never the reported wrong ID.
        doc.FirstInspection = live => change switch
        {
            "missing" => Array.Empty<Transaction.CreatedCap>(),
            "duplicate" => new[] { live[0], live[0] },
            "wrong-id" => new[] { new Transaction.CreatedCap(doc.UnrelatedId, doc.Marker, doc.CandidateGeometrySignature) },
            "wrong-marker" => new[] { new Transaction.CreatedCap(doc.PlannedId, Guid.NewGuid(), doc.CandidateGeometrySignature) },
            "empty-signature" => new[] { new Transaction.CreatedCap(doc.PlannedId, doc.Marker, Array.Empty<byte>()) },
            "changed-signature" => new[] { new Transaction.CreatedCap(doc.PlannedId, doc.Marker, new byte[] { 99 }) },
            _ => throw new ArgumentOutOfRangeException(nameof(change))
        };
        var result = Run(doc);
        Assert.Equal(Transaction.Outcome.Failed, result.Status);
        Assert.StartsWith(reasonPrefix, result.Reason);
        Assert.Equal(Transaction.Rollback.Complete, result.Cleanup);
        Assert.Equal(doc.PlannedId, Assert.Single(doc.DeleteCalls));
        Assert.False(doc.Objects.ContainsKey(doc.PlannedId));
        AssertOriginalsIntact(doc);
    }

    [Fact]
    public void UnavailableGeometryOnEveryInspectionStillRollsBackByOwnedIdentityAndMarker()
    {
        var doc = new FakeDocument();
        // Persist unavailable extraction through every read, including rollback reads.
        doc.AfterInsert = () => doc.Objects[doc.PlannedId].GeometrySignature = Array.Empty<byte>();
        var result = Run(doc);
        Assert.Equal(Transaction.Outcome.Failed, result.Status);
        Assert.StartsWith("BUILD_INSERTED_CAP_GEOMETRY_UNAVAILABLE:", result.Reason);
        Assert.Equal(Transaction.Rollback.Complete, result.Cleanup);
        Assert.Equal(doc.PlannedId, Assert.Single(doc.DeleteCalls));
        Assert.False(doc.Objects.ContainsKey(doc.PlannedId));
        AssertOriginalsIntact(doc);
    }

    [Theory]
    [InlineData("false")]
    [InlineData("throw-before")]
    [InlineData("marker-changed")]
    [InlineData("inspection-throws")]
    public void UnsafeOrFailedRollbackIsReportedWithoutDeletingOriginals(string mode)
    {
        var doc = new FakeDocument { AddMode = "throw-after", DeleteMode = mode };
        if (mode == "marker-changed") doc.AfterInsert = () => doc.Objects[doc.PlannedId].Marker = Guid.NewGuid();
        if (mode == "inspection-throws") doc.ThrowOnInspect = true;
        var result = Run(doc);
        Assert.Equal(Transaction.Outcome.Failed, result.Status);
        Assert.Equal(Transaction.Rollback.Incomplete, result.Cleanup);
        Assert.Contains("rollback is incomplete", result.Reason);
        Assert.True(doc.Objects.ContainsKey(doc.PlannedId));
        AssertOriginalsIntact(doc);
        Assert.DoesNotContain(doc.SourceId, doc.DeleteCalls);
        Assert.DoesNotContain(doc.UnrelatedId, doc.DeleteCalls);
    }

    [Fact]
    public void DeleteThrowAfterRemovalUsesLiveEvidenceToReportCompletedCleanup()
    {
        var doc = new FakeDocument { AddMode = "throw-after", DeleteMode = "throw-after" };
        var result = Run(doc);
        Assert.Equal(Transaction.Rollback.Complete, result.Cleanup);
        AssertOriginalsIntact(doc);
        Assert.False(doc.Objects.ContainsKey(doc.PlannedId));
    }

    [Fact]
    public void OriginalObjectWithTransactionMarkerIsNeverPassedToDeleteCallback()
    {
        var doc = new FakeDocument { AddMode = "throw-after" };
        doc.AfterInsert = () => doc.Objects[doc.SourceId].Marker = doc.Marker;
        var result = Run(doc);
        Assert.Equal(Transaction.Rollback.Incomplete, result.Cleanup);
        Assert.Equal(doc.PlannedId, Assert.Single(doc.DeleteCalls));
        AssertOriginalsIntact(doc);
    }

    [Fact]
    public void NewTaggedObjectDuringRollbackIsReportedRatherThanChased()
    {
        var doc = new FakeDocument { AddMode = "throw-after" };
        var late = Guid.NewGuid();
        doc.AfterDelete = () => doc.Objects.Add(late, new FakeObject(doc.Marker, new byte[] { 4 }));
        var result = Run(doc);
        Assert.Equal(Transaction.Rollback.Incomplete, result.Cleanup);
        Assert.Equal(doc.PlannedId, Assert.Single(doc.DeleteCalls));
        Assert.True(doc.Objects.ContainsKey(late));
        AssertOriginalsIntact(doc);
    }

    [Fact]
    public void ConfirmationSealsCopiesAndArchiveGettersCannotAlterIt()
    {
        var doc = new FakeDocument();
        var state = doc.CaptureState();
        state.CandidateArchive[0]++;
        state.CandidateGeometrySignature[0]++;
        state.GeometryEvidence[0]++;
        doc.Candidate[0]++;
        var result = Transaction.Run(doc, new Transaction.Confirmation(state), Acceptance());
        Assert.Equal(Transaction.Outcome.StaleConfirmation, result.Status);
        Assert.Equal(0, doc.AddCalls);
    }

    [Fact]
    public void SignatureGetterAndInsertedSignatureConstructorCannotMutateTheirSeals()
    {
        var doc = new FakeDocument();
        var state = doc.CaptureState();
        state.CandidateGeometrySignature[0]++;
        var signature = doc.CandidateGeometrySignature.ToArray();
        var inserted = new Transaction.CreatedCap(Guid.NewGuid(), Guid.NewGuid(), signature);
        signature[0]++;
        Assert.True(inserted.Matches(state));
        Assert.Equal(Transaction.Outcome.Added, Transaction.Run(doc, new Transaction.Confirmation(state), Acceptance()).Status);
    }

    private static Transaction.Result Run(FakeDocument doc) =>
        Transaction.Run(doc, new Transaction.Confirmation(doc.CaptureState()), Acceptance());

    private static Transaction.IAcceptancePolicy Acceptance() => new TestAcceptance(state =>
        state.GeometryEvidence.SequenceEqual(new byte[] { 9, 8, 7 }) ? null : "Fake geometry evidence was not accepted.");

    private static void AssertOriginalsIntact(FakeDocument doc)
    {
        Assert.Equal(new byte[] { 1, 2, 3 }, doc.Objects[doc.SourceId].Archive);
        Assert.Equal(new byte[] { 44, 55 }, doc.Objects[doc.UnrelatedId].Archive);
    }

    private static void Change(FakeDocument doc, string change)
    {
        switch (change)
        {
            case "source-archive": doc.Objects[doc.SourceId].Archive[0]++; break;
            case "source-identity":
                var old = doc.SourceId; doc.SourceId = Guid.NewGuid();
                doc.Objects.Add(doc.SourceId, doc.Objects[old]); doc.Objects.Remove(old); break;
            case "candidate-archive": doc.Candidate[0]++; break;
            case "candidate-signature": doc.CandidateGeometrySignature[0]++; break;
            case "candidate-receipt": doc.ReceiptId = Guid.NewGuid(); break;
            case "proof": doc.Evidence[0]++; break;
            case "absolute-tolerance": doc.AbsoluteTolerance *= 2; break;
            case "angle-tolerance": doc.AngleTolerance *= 2; break;
            case "model-units": doc.ModelUnitSystem++; break;
            case "unit-scale": doc.MetresPerModelUnit *= 2; break;
            case "generation": doc.Generation++; break;
            case "undo": doc.Undo++; break;
            case "recording-disabled": doc.RecordingEnabled = false; break;
            case "document": doc.DocumentSerial++; break;
            case "unrelated-same-count":
                doc.Objects.Remove(doc.UnrelatedId);
                doc.Objects.Add(Guid.NewGuid(), new FakeObject(Guid.Empty, new byte[] { 5 })); break;
            default: throw new ArgumentOutOfRangeException(nameof(change));
        }
    }

    private sealed class TestAcceptance : Transaction.IAcceptancePolicy
    {
        private readonly Func<Transaction.State, string?> _check;
        internal TestAcceptance(Func<Transaction.State, string?> check) { _check = check; }
        public string? Rejection(Transaction.State confirmed) => _check(confirmed);
    }

    private sealed class FakeObject
    {
        internal Guid Marker;
        internal byte[] Archive;
        internal byte[] GeometrySignature;
        internal FakeObject(Guid marker, byte[] archive, byte[]? geometrySignature = null)
        {
            Marker = marker; Archive = (byte[])archive.Clone();
            GeometrySignature = (byte[])(geometrySignature ?? archive).Clone();
        }
    }

    private sealed class FakeDocument : Transaction.IDocument
    {
        internal Guid SourceId = Guid.NewGuid();
        internal readonly Guid UnrelatedId = Guid.NewGuid();
        internal readonly Dictionary<Guid, FakeObject> Objects = new();
        internal ulong DocumentSerial = 7;
        internal long Generation = 4;
        internal uint Undo = 19;
        internal bool RecordingEnabled = true;
        internal double AbsoluteTolerance = .001;
        internal double AngleTolerance = .01;
        internal int ModelUnitSystem = 2;
        internal double MetresPerModelUnit = .001;
        internal Guid ReceiptId = Guid.NewGuid();
        internal byte[] Candidate = { 10, 20, 30 };
        internal byte[] CandidateGeometrySignature = { 11, 22, 33 };
        internal byte[] Evidence = { 9, 8, 7 };
        internal bool Cancelled;
        internal string AddMode = "normal";
        internal string DeleteMode = "normal";
        internal bool ThrowOnInspect;
        internal Func<IReadOnlyList<Transaction.CreatedCap>, IReadOnlyList<Transaction.CreatedCap>>? FirstInspection;
        internal Action? BeforeCapture;
        internal Action? AfterInsert;
        internal Action? AfterDelete;
        internal int AddCalls;
        internal Guid PlannedId;
        internal Guid Marker;
        internal uint UndoAtInsertion;
        internal readonly List<Guid> DeleteCalls = new();
        internal readonly List<ulong> InspectedDocumentSerials = new();

        internal FakeDocument()
        {
            Objects.Add(SourceId, new FakeObject(Guid.Empty, new byte[] { 1, 2, 3 }));
            Objects.Add(UnrelatedId, new FakeObject(Guid.Empty, new byte[] { 44, 55 }));
        }

        public Transaction.State CaptureState()
        {
            BeforeCapture?.Invoke();
            return new Transaction.State(DocumentSerial, Generation, RecordingEnabled ? Undo : 0, AbsoluteTolerance, AngleTolerance, ModelUnitSystem, MetresPerModelUnit, ReceiptId,
                Candidate, CandidateGeometrySignature, Evidence, new Dictionary<Guid, byte[]> { [SourceId] = Objects[SourceId].Archive }, Objects.Keys, Cancelled);
        }

        public Guid AddCap(Transaction.State confirmed, Guid objectId, Guid transactionMarker)
        {
            AddCalls++; PlannedId = objectId; Marker = transactionMarker; UndoAtInsertion = Undo;
            Assert.False(Objects.ContainsKey(objectId));
            Assert.NotEqual(Guid.Empty, transactionMarker);
            if (AddMode == "empty-before") return Guid.Empty;
            if (AddMode == "throw-before") throw new InvalidOperationException("Native failure before insertion.");
            Objects.Add(objectId, new FakeObject(transactionMarker, confirmed.CandidateArchive, confirmed.CandidateGeometrySignature));
            AfterInsert?.Invoke();
            if (AddMode == "empty-after") return Guid.Empty;
            if (AddMode == "throw-after") throw new InvalidOperationException("Native failure after insertion.");
            return AddMode == "wrong-id" ? UnrelatedId : objectId;
        }

        public IReadOnlyList<Transaction.CreatedCap> InspectInsertion(ulong documentSerial, Guid plannedId, Guid transactionMarker)
        {
            InspectedDocumentSerials.Add(documentSerial);
            if (ThrowOnInspect) throw new InvalidOperationException("Cannot inspect live objects.");
            Assert.Equal(7ul, documentSerial); // The fake remains bound to original document 7.
            var live = Objects.Where(pair => pair.Key == plannedId || pair.Value.Marker == transactionMarker)
                .Select(pair => new Transaction.CreatedCap(pair.Key, pair.Value.Marker, pair.Value.GeometrySignature)).ToArray();
            return InspectedDocumentSerials.Count == 1 && FirstInspection is not null ? FirstInspection(live) : live;
        }

        public bool DeleteCreatedCap(ulong documentSerial, Guid objectId, Guid transactionMarker)
        {
            DeleteCalls.Add(objectId);
            Assert.Equal(7ul, documentSerial);
            // An original ID must never reach the destructive callback, even if marked.
            Assert.NotEqual(SourceId, objectId); Assert.NotEqual(UnrelatedId, objectId);
            if (DeleteMode == "false") return false;
            if (DeleteMode == "throw-before") throw new InvalidOperationException("Native delete failed.");
            if (!Objects.TryGetValue(objectId, out var item) || item.Marker != transactionMarker) return false;
            var removed = Objects.Remove(objectId);
            AfterDelete?.Invoke();
            if (DeleteMode == "throw-after") throw new InvalidOperationException("Native delete threw after removing cap.");
            return removed;
        }
    }
}
