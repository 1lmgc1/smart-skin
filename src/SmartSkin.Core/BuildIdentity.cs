using System;
using System.Linq;
using System.Reflection;

namespace SmartSkin.Core;

public sealed class BuildIdentity
{
    private BuildIdentity(string version, string commit, string patch)
    {
        Version = version;
        Commit = commit;
        Patch = patch;
    }

    public string Version { get; }

    public string Commit { get; }

    public string Patch { get; }

    public static BuildIdentity FromAssembly(Assembly assembly)
    {
        if (assembly is null)
        {
            throw new ArgumentNullException(nameof(assembly));
        }

        var informationalVersion = assembly
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()
            ?.InformationalVersion;

        var fallbackVersion = assembly.GetName().Version?.ToString() ?? "unknown";
        var version = string.IsNullOrWhiteSpace(informationalVersion)
            ? fallbackVersion
            : informationalVersion.Split('+')[0];

        var metadata = assembly.GetCustomAttributes<AssemblyMetadataAttribute>().ToArray();
        var commit = MetadataValue(metadata, "GitCommit") ?? CommitFromInformationalVersion(informationalVersion) ?? "unknown";
        var patch = MetadataValue(metadata, "Patch") ?? "unknown";

        return new BuildIdentity(version, commit, patch);
    }

    public string ToMachineLine(int objectCount)
    {
        return $"SMARTSKIN_{Patch} PASS | version={Version} | commit={Commit} | objects={objectCount}";
    }

    private static string? MetadataValue(AssemblyMetadataAttribute[] metadata, string key)
    {
        return metadata.FirstOrDefault(item => string.Equals(item.Key, key, StringComparison.OrdinalIgnoreCase))?.Value;
    }

    private static string? CommitFromInformationalVersion(string? informationalVersion)
    {
        if (string.IsNullOrWhiteSpace(informationalVersion))
        {
            return null;
        }

        var separator = informationalVersion.IndexOf('+');
        return separator >= 0 && separator < informationalVersion.Length - 1
            ? informationalVersion.Substring(separator + 1)
            : null;
    }
}

