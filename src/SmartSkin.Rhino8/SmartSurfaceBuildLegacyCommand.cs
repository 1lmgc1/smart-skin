using Rhino;
using Rhino.Commands;

namespace SmartSkin.Rhino8;

// Command-line compatibility route only. No toolbar node or existing GUID
// changes: the single visible Smart Skin button enters native FULLCYCLE.
[CommandStyle(Style.Hidden)]
public sealed class SmartSurfaceBuildLegacyCommand : Command
{
    public override string EnglishName => "SmartSurfaceBuildLegacy";

    protected override Result RunCommand(RhinoDoc doc, RunMode mode) =>
        SmartSurfaceBuildCommand.RunLegacyCommand(doc, mode);
}
