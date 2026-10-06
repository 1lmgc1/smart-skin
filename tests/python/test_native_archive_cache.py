"""Public openNURBS cache reproduction; NOT licensed RhinoCommon execution.

Run with the pinned rhino3dm8.17 dependency. Generic headless jobs without that
optional package skip these tests explicitly; policy/adapter mocks are separate.
"""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/SmartSkin.Rhino8/Python'))
import native_owner_separation as n
try:
    import rhino3dm as r
except ImportError:
    r=None


class OpenNurbsBrep:
    """Bridge only API spelling; all archive/cache operations use openNURBS."""
    def __init__(self,geometry):self.geometry=geometry
    def GetBoundingBox(self,accurate):
        assert accurate is False
        return self.geometry.GetBoundingBox()
    @property
    def IsSolid(self):return self.geometry.IsSolid
    def ToJSON(self,options):return json.dumps(self.geometry.Encode(),sort_keys=True)


def fresh_brep():
    surface=r.PlaneSurface(r.Plane.WorldXY(),r.Interval(0.,1.),r.Interval(0.,1.)).ToNurbsSurface()
    return r.Brep.CreateFromSurface(surface)


def archive_hash(brep):
    return hashlib.sha256(json.dumps(brep.Encode(),sort_keys=True).encode()).hexdigest()


def definition(brep):
    return dict(surfaces=[s.Encode() for s in brep.Surfaces],
                vertices=[(v.Location.X,v.Location.Y,v.Location.Z) for v in brep.Vertices],
                face_orientations=[f.OrientationIsReversed for f in brep.Faces],
                counts=(len(brep.Faces),len(brep.Edges),len(brep.Vertices)))


@unittest.skipIf(r is None,'Pinned rhino3dm is unavailable; licensed Rhino behavior remains unverified.')
class OpenNurbsArchiveCacheTests(unittest.TestCase):
    def adapter(self):
        return n.RhinoAdapter(SimpleNamespace(Geometry=SimpleNamespace(Brep=OpenNurbsBrep),
                   FileIO=SimpleNamespace(SerializationOptions=lambda:SimpleNamespace())))
    def test_read_only_bbox_and_solid_queries_change_raw_archive_not_definition(self):
        brep=fresh_brep();shape=definition(brep)
        cold=archive_hash(brep);brep.GetBoundingBox();boxed=archive_hash(brep)
        self.assertNotEqual(cold,boxed)
        unused=brep.IsSolid;classified=archive_hash(brep)
        self.assertNotEqual(boxed,classified)
        self.assertEqual(shape,definition(brep))
        for unused in range(3):
            brep.GetBoundingBox();solid=brep.IsSolid;valid=brep.IsValid
            self.assertEqual(classified,archive_hash(brep))
    def test_production_fingerprint_primes_known_caches_before_first_binding(self):
        adapter=self.adapter();brep=fresh_brep();wrapped=OpenNurbsBrep(brep)
        before=definition(brep)
        first=adapter.fingerprint(wrapped,n._Budget(n.ScreenLimits()))
        brep.GetBoundingBox();unused=brep.IsSolid;unused=brep.IsValid
        self.assertEqual(first,adapter.fingerprint(wrapped,n._Budget(n.ScreenLimits())))
        self.assertEqual(before,definition(brep))
    def test_full_archive_fingerprint_still_detects_geometry_and_userdata(self):
        adapter=self.adapter();brep=fresh_brep();wrapped=OpenNurbsBrep(brep)
        before=adapter.fingerprint(wrapped,n._Budget(n.ScreenLimits()))
        brep.SetUserString('public-test','changed')
        userdata=adapter.fingerprint(wrapped,n._Budget(n.ScreenLimits()))
        self.assertNotEqual(before,userdata)
        self.assertTrue(brep.Transform(r.Transform.Translation(0.,0.,.125)))
        moved=adapter.fingerprint(wrapped,n._Budget(n.ScreenLimits()))
        self.assertNotEqual(userdata,moved)


if __name__=='__main__':unittest.main()
