using System;
using System.Linq;
using Rhino;
using Rhino.Geometry;
using Rhino.FileIO;
using Rhino.DocObjects;
using IronPython.Hosting;
class Program {
 static void Main(string[] args) {
   var engine=Python.CreateEngine();
   foreach(var f in args) {engine.CreateScriptSourceFromFile(f).Compile();Console.WriteLine("IRONPYTHON_SYNTAX_OK "+f);}
 }
 // This method is compiled, never executed without Rhino. It checks exact API signatures.
 static void ApiContract(RhinoDoc doc, Brep edgeOwner, BrepFace face, BrepTrim trim, Curve a, Curve b, File3dm file) {
   var id=file.Objects.First().Attributes.ObjectId;
   var g=file.Objects.First().Geometry.Duplicate();
   bool eq=GeometryBase.GeometryEquals(g,doc.Objects.FindId(id).Geometry);
   double parameter; bool ok=trim.GetTrimParameter(.5,out parameter);
   var uv=trim.PointAt(parameter);var image=trim.Face.PointAt(uv.X,uv.Y);
   var iso=face.IsoCurve(1,face.Domain(0).T1);
   double max,ta,tb,min,ma,mb;
   ok=Curve.GetDistancesBetweenCurves(a,b,.001,out max,out ta,out tb,out min,out ma,out mb);
   var joins=Brep.JoinBreps(new[]{edgeOwner},.01,.01);
   var part=a.Trim(.1,.2); var chains=Curve.JoinCurves(new[]{a,b},.01);
   var normal=face.NormalAt(.5,.5);normal.Unitize();normal=normal*-1.0;double dot=normal*normal;
   var shape=face.CurvatureAt(.5,.5);var direction=shape.Direction(0);double k=shape.Kappa(0);
   var layer=doc.Layers[0];bool deleted=layer.IsDeleted;layer.IsVisible=true;doc.Layers.Modify(layer,layer.Index,true);
   doc.Objects.UnselectAll();doc.Views.ActiveView.ActiveViewport.ZoomBoundingBox(g.GetBoundingBox(true));
   var serial=doc.RuntimeSerialNumber;var path=doc.Path;RhinoApp.Wait();file.Dispose();g.Dispose();
 }
}
