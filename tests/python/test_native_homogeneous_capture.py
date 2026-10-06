"""Preserve native binary64 homogeneous coefficients without Location round trips."""
import pathlib
import sys
import unittest
from types import SimpleNamespace
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'src'/'SmartSkin.Rhino8'/'Python'))
import native_input

class Point:
    X,Y,Z,Weight=0.7,1.1,-3.1,0.3
    @property
    def Location(self):
        raise AssertionError('Euclidean round trip would alter the native coefficient')

class List:
    def __init__(self,values):self.values=values;self.Count=len(values)
    def __getitem__(self,index):return self.values[index]

class HomogeneousCapture(unittest.TestCase):
    def test_curve_copy_uses_exact_native_homogeneous_values(self):
        disposed=[]
        curve=SimpleNamespace(IsValid=True,Degree=1,Points=List([Point(),Point()]),
                              Knots=List([0,1]),Domain=SimpleNamespace(T0=0,T1=1),
                              Dispose=lambda:disposed.append(True))
        result=native_input._curve_record(SimpleNamespace(ToNurbsCurve=lambda:curve))
        self.assertEqual(result['homogeneous_cp'],[[0.7,1.1,-3.1,0.3]]*2)
        self.assertEqual(disposed,[True])

    def test_surface_copy_uses_exact_native_homogeneous_values(self):
        disposed=[]
        surface=SimpleNamespace(IsValid=True,Degree=lambda axis:1,
             Points=SimpleNamespace(CountU=2,CountV=2,GetControlPoint=lambda i,j:Point()),
             KnotsU=List([0,1]),KnotsV=List([0,1]),Dispose=lambda:disposed.append(True))
        result=native_input._surface_record(SimpleNamespace(ToNurbsSurface=lambda:surface))
        self.assertEqual(result['homogeneous_cp'],[[[0.7,1.1,-3.1,0.3]]*2]*2)
        self.assertEqual(disposed,[True])

if __name__=='__main__':unittest.main()
