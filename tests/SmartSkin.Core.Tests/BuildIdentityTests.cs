using System.Reflection;
using SmartSkin.Core;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class BuildIdentityTests
{
    [Fact]
    public void FromAssembly_ReturnsVersionCommitAndPatch()
    {
        var identity = BuildIdentity.FromAssembly(Assembly.GetExecutingAssembly());

        Assert.Equal("0.0.20-p08e1f6", identity.Version);
        Assert.False(string.IsNullOrWhiteSpace(identity.Commit));
        Assert.Equal("P08E1F6", identity.Patch);
    }

    [Fact]
    public void MachineLine_IsStableAndParseable()
    {
        var identity = BuildIdentity.FromAssembly(Assembly.GetExecutingAssembly());

        var line = identity.ToMachineLine(17);

        Assert.StartsWith("SMARTSKIN_P08E1F6 PASS", line);
        Assert.Contains("version=", line);
        Assert.Contains("commit=", line);
        Assert.EndsWith("objects=17", line);
    }
}
