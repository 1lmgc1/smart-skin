using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class NativeBuildDocumentAdapter : NativeBuildTransaction.IDocument, IDisposable
{
    private readonly RhinoDoc _document;
    private readonly NativeCompareInput _input;
    private readonly Brep _cap;
    private readonly NativeBuildCapQualification _qualification;
    private readonly NativeBuildController _controller;
    private readonly Guid _receipt = Guid.NewGuid();
    private Guid _plannedId, _marker;
    private bool _insideAdd;
    private readonly double _absoluteTolerance, _angleTolerance, _metresPerUnit;
    private readonly UnitSystem _units;

    internal NativeBuildDocumentAdapter(RhinoDoc document, NativeCompareInput input, Brep cap,
        NativeBuildCapQualification qualification, NativeBuildController controller)
    {
        _document = document; _input = input; _cap = cap; _qualification = qualification; _controller = controller;
        _absoluteTolerance = document.ModelAbsoluteTolerance; _angleTolerance = document.ModelAngleToleranceRadians;
        _units = document.ModelUnitSystem; _metresPerUnit = MetresPerUnit();
        if (!qualification.Matches(input, cap) || !input.SourcesUnchanged(document) || !input.CopiesUnchanged())
            throw new InvalidOperationException("BUILD_QUALIFICATION_SEAL_MISMATCH");
        RhinoDoc.AddRhinoObject += Added;
        RhinoDoc.DeleteRhinoObject += ObjectChanged;
        RhinoDoc.UndeleteRhinoObject += ObjectChanged;
        RhinoDoc.ReplaceRhinoObject += Replaced;
        RhinoDoc.ModifyObjectAttributes += AttributesChanged;
        RhinoDoc.DocumentPropertiesChanged += DocumentChanged;
        RhinoDoc.CloseDocument += DocumentClosed;
        RhinoDoc.ActiveDocumentChanged += ActiveDocumentChanged;
    }
    public NativeBuildTransaction.State CaptureState()
    {
        if (!_input.CopiesUnchanged()) throw new InvalidOperationException("BUILD_CAPTURED_COPIES_CHANGED");
        var active = RhinoDoc.ActiveDoc;
        var serial = active?.RuntimeSerialNumber ?? 0;
        var sources = new Dictionary<Guid, byte[]>();
        foreach (var owner in _input.Owners)
        {
            var source = _document.Objects.FindId(owner.Id);
            if (source is null || source.IsDeleted) throw new InvalidOperationException("BUILD_SOURCE_MISSING");
            sources.Add(owner.Id, Encoding.UTF8.GetBytes(source.RuntimeSerialNumber + "|" + _input.Fingerprint(source)));
        }
        var units = _document.ModelUnitSystem;
        var scale = MetresPerUnit();
        var undo = _document.UndoRecordingEnabled && _document.UndoRecordingIsActive ? _document.CurrentUndoRecordSerialNumber : 0;
        return new NativeBuildTransaction.State(serial, _controller.Generation, undo, _document.ModelAbsoluteTolerance,
            _document.ModelAngleToleranceRadians, (int)units, scale, _receipt,
            Convert.FromBase64String(_input.GeometryFingerprint(_cap)), NativeBuildGeometrySignature.Capture(_cap), _qualification.Evidence, sources,
            LiveObjects().Select(obj => obj.Id), _controller.Cancelled || _document.IsClosing || serial != _document.RuntimeSerialNumber);
    }
    internal bool PreviewMetadataCurrent(NativeBuildTransaction.State displayed)
    {
        if (_document.IsClosing || _controller.Cancelled || _controller.Generation != displayed.Generation
            || RhinoDoc.ActiveDoc?.RuntimeSerialNumber != _document.RuntimeSerialNumber
            || _document.ModelAbsoluteTolerance != displayed.AbsoluteTolerance
            || _document.ModelAngleToleranceRadians != displayed.AngleToleranceRadians
            || (int)_document.ModelUnitSystem != displayed.ModelUnitSystem || MetresPerUnit() != displayed.MetresPerModelUnit) return false;
        foreach (var owner in _input.Owners)
        {
            var source = _document.Objects.FindId(owner.Id);
            if (source is null || source.IsDeleted || source.RuntimeSerialNumber != owner.Serial) return false;
        }
        return true;
    }

    public Guid AddCap(NativeBuildTransaction.State confirmed, Guid objectId, Guid transactionMarker)
    {
        if (!_input.SourcesUnchanged(_document) || !_input.CopiesUnchanged() || !_qualification.Matches(_input, _cap) || _controller.Cancelled)
            throw new InvalidOperationException("BUILD_SOURCE_OR_CANDIDATE_NOT_CURRENT");
        using var copy = _cap.DuplicateBrep();
        using var attributes = _document.CreateDefaultAttributes();
        attributes.ObjectId = objectId; attributes.Name = "Smart Skin — " + NativeBuildCapQualification.UserStatus;
        attributes.SetUserString(NativeBuildTransaction.OwnershipAttribute, transactionMarker.ToString("N"));
        attributes.SetUserString("SmartSkin.NativeBuild.Status", NativeBuildCapQualification.UserStatus);
        if (!Convert.FromBase64String(_input.GeometryFingerprint(copy)).SequenceEqual(confirmed.CandidateArchive))
            throw new InvalidOperationException("BUILD_ADD_COPY_ARCHIVE_MISMATCH");
        _plannedId = objectId; _marker = transactionMarker; _insideAdd = true;
        // Preserve the exact qualified cap. Rhino's shorter overload delegates kink splitting
        // to native defaults, which can change topology and invalidate the sealed readback.
        try { return _document.Objects.AddBrep(copy, attributes, null, false, false); }
        finally { _insideAdd = false; }
    }
    public IReadOnlyList<NativeBuildTransaction.CreatedCap> InspectInsertion(ulong documentSerial, Guid plannedId, Guid transactionMarker)
    {
        if (documentSerial != _document.RuntimeSerialNumber) throw new InvalidOperationException("BUILD_ROLLBACK_DOCUMENT_MISMATCH");
        var result = new List<NativeBuildTransaction.CreatedCap>();
        foreach (var obj in LiveObjects().Where(obj => obj.Id == plannedId || Marker(obj) == transactionMarker))
        {
            // Failed content extraction must not lose the identity needed for safe rollback.
            var signature = Array.Empty<byte>();
            try { if (obj.Geometry is Brep brep) signature = NativeBuildGeometrySignature.Capture(brep); }
            catch (Exception) { /* The core reports unavailable geometry, then removes only owned IDs. */ }
            result.Add(new NativeBuildTransaction.CreatedCap(obj.Id, Marker(obj), signature));
        }
        return result;
    }
    public bool DeleteCreatedCap(ulong documentSerial, Guid objectId, Guid transactionMarker)
    {
        if (documentSerial != _document.RuntimeSerialNumber || _input.Owners.Any(owner => owner.Id == objectId)) return false;
        var obj = _document.Objects.FindId(objectId);
        if (obj is null || obj.IsDeleted || obj.Id != objectId || Marker(obj) != transactionMarker) return false;
        return _document.Objects.Delete(obj, true);
    }
    internal NativeBuildTransaction.IAcceptancePolicy Acceptance(NativeBuildTransaction.State displayed) => new AcceptancePolicy(_qualification, displayed);
    private sealed class AcceptancePolicy : NativeBuildTransaction.IAcceptancePolicy
    {
        private readonly NativeBuildCapQualification _qualification;
        private readonly NativeBuildTransaction.State _displayed;
        internal AcceptancePolicy(NativeBuildCapQualification qualification, NativeBuildTransaction.State displayed)
        { _qualification = qualification; _displayed = displayed; }
        public string? Rejection(NativeBuildTransaction.State confirmed) => _qualification.Ready
            && confirmed.CandidateReceiptId == _displayed.CandidateReceiptId
            && confirmed.GeometryEvidence.SequenceEqual(_qualification.Evidence)
            && confirmed.CandidateArchive.SequenceEqual(_displayed.CandidateArchive)
            ? null : "BUILD_TYPED_CAP_EVIDENCE_NOT_CURRENT";
    }
    private RhinoObject[] LiveObjects()
    {
        var settings = new ObjectEnumeratorSettings { ActiveObjects = true, DeletedObjects = false, NormalObjects = true,
            LockedObjects = true, HiddenObjects = true, ReferenceObjects = false, IdefObjects = false,
            IncludeGrips = false, IncludeLights = false, IncludePhantoms = false };
        var objects = _document.Objects.GetObjectList(settings).Take(100001).ToArray();
        if (objects.Length > 100000) throw new InvalidOperationException("BUILD_DOCUMENT_OBJECT_LIMIT");
        return objects;
    }
    private static Guid Marker(RhinoObject obj) => Guid.TryParse(obj.Attributes.GetUserString(NativeBuildTransaction.OwnershipAttribute), out var marker) ? marker : Guid.Empty;
    private void Added(object? sender, RhinoObjectEventArgs args)
    {
        if (args.TheObject.Document?.RuntimeSerialNumber != _document.RuntimeSerialNumber) return;
        if (_insideAdd && args.ObjectId == _plannedId && Marker(args.TheObject) == _marker) return;
        _controller.Invalidate();
    }
    private void ObjectChanged(object? sender, RhinoObjectEventArgs args)
    { if (args.TheObject.Document?.RuntimeSerialNumber == _document.RuntimeSerialNumber) _controller.Invalidate(); }
    private void Replaced(object? sender, RhinoReplaceObjectEventArgs args)
    { if (args.Document.RuntimeSerialNumber == _document.RuntimeSerialNumber) _controller.Invalidate(); }
    private void AttributesChanged(object? sender, RhinoModifyObjectAttributesEventArgs args)
    { if (args.Document.RuntimeSerialNumber == _document.RuntimeSerialNumber) _controller.Invalidate(); }
    private double MetresPerUnit() => _document.ModelUnitSystem == UnitSystem.CustomUnits
        ? (_document.GetCustomUnitSystem(true, out _, out var metres) ? metres : double.NaN)
        : RhinoMath.UnitScale(_document.ModelUnitSystem, UnitSystem.Meters);
    private void DocumentChanged(object? sender, DocumentEventArgs args)
    {
        if (args.DocumentSerialNumber == _document.RuntimeSerialNumber && (_document.ModelAbsoluteTolerance != _absoluteTolerance
            || _document.ModelAngleToleranceRadians != _angleTolerance || _document.ModelUnitSystem != _units || MetresPerUnit() != _metresPerUnit))
            _controller.Invalidate();
    }
    private void DocumentClosed(object? sender, DocumentEventArgs args)
    { if (args.DocumentSerialNumber == _document.RuntimeSerialNumber) _controller.Invalidate(); }
    private void ActiveDocumentChanged(object? sender, DocumentEventArgs args) => _controller.DocumentContextChanged(
        args.DocumentSerialNumber == _document.RuntimeSerialNumber && RhinoDoc.ActiveDoc?.RuntimeSerialNumber == _document.RuntimeSerialNumber,
        _document.IsClosing);
    public void Dispose()
    {
        RhinoDoc.AddRhinoObject -= Added;
        RhinoDoc.DeleteRhinoObject -= ObjectChanged;
        RhinoDoc.UndeleteRhinoObject -= ObjectChanged;
        RhinoDoc.ReplaceRhinoObject -= Replaced;
        RhinoDoc.ModifyObjectAttributes -= AttributesChanged;
        RhinoDoc.DocumentPropertiesChanged -= DocumentChanged;
        RhinoDoc.CloseDocument -= DocumentClosed;
        RhinoDoc.ActiveDocumentChanged -= ActiveDocumentChanged;
    }
}
