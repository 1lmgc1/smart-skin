using SmartSkin.Core;
using Rhino;
using Rhino.PlugIns;

namespace SmartSkin.Rhino8;

public sealed class SmartSkinPlugIn : PlugIn
{
    public SmartSkinPlugIn()
    {
        Instance = this;
    }

    public static SmartSkinPlugIn? Instance { get; private set; }

    protected override LoadReturnCode OnLoad(ref string errorMessage)
    {
        var identity = BuildIdentity.FromAssembly(typeof(SmartSkinPlugIn).Assembly);
        RhinoApp.WriteLine($"Smart Skin {identity.Version} ({identity.Patch}, {identity.Commit}) loaded.");
        return LoadReturnCode.Success;
    }
}

