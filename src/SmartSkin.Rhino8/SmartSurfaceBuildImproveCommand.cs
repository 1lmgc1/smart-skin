using Rhino;
using Rhino.Commands;

namespace SmartSkin.Rhino8;

public sealed class SmartSurfaceBuildImproveCommand : Command
{
    public override string EnglishName => "SmartSurfaceBuildImprove";
    protected override Result RunCommand(RhinoDoc doc, RunMode mode) => SmartSurfaceBuildCommand.RunNative(doc, mode, true);
}
