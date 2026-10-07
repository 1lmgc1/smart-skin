using Rhino;
using Rhino.Commands;

namespace SmartSkin.Rhino8;

// Explicit historical Python workflow. Never an automatic native Build fallback.
[CommandStyle(Style.ScriptRunner | Style.Hidden)]
public sealed class SmartSurfaceBuildPythonCommand : Command
{
    public override string EnglishName => "SmartSurfaceBuildPython";
    protected override Result RunCommand(RhinoDoc doc, RunMode mode) => SmartSurfaceBuildCommand.RunPythonCommand(doc, mode);
}
