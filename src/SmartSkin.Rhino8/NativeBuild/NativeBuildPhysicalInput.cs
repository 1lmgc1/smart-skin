using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace SmartSkin.Rhino8;

// The delivered net48 user-test plug-in targets Windows. Use only the documented
// current-state high bit, never GetAsyncKeyState's unreliable "pressed since" bit.
internal static class NativeBuildPhysicalInput
{
    [DllImport("user32.dll")] private static extern short GetAsyncKeyState(int key);
    [DllImport("user32.dll")] [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetKeyboardState([Out] byte[] state);
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
    [DllImport("user32.dll")] private static extern int GetSystemMetrics(int metric);
    private static readonly uint ProcessId = (uint)Process.GetCurrentProcess().Id;
    internal static bool Supported => RuntimeInformation.IsOSPlatform(OSPlatform.Windows);
    private static bool Foreground
    {
        get
        {
            if (!Supported) return false;
            var window = GetForegroundWindow();
            return window != IntPtr.Zero && GetWindowThreadProcessId(window, out var process) != 0 && process == ProcessId;
        }
    }
    internal static bool ContextAvailable => Foreground;
    private static bool Down(int key) => GetAsyncKeyState(key) < 0;
    private static bool Released(params int[] keys)
    {
        if (!Foreground) return false;
        var state = new byte[256];
        if (!GetKeyboardState(state)) return false;
        foreach (var key in keys) if ((state[key] & 0x80) != 0 || Down(key)) return false;
        return true;
    }
    internal static bool Unmodified => Released(16, 17, 18, 91, 92);
    internal static bool ConfirmationInputsReleased => Released(13, 32, 1, 2, 4, 16, 17, 18, 91, 92);
    // Rhino's hook ordering relative to Windows async-state updates is undocumented.
    // The post-release key event is paired with GetResult.Nothing (or a focused Eto KeyDown).
    internal static bool ConfirmationEventAllowed(int key) => (key == 13 || key == 32) && Unmodified;
    internal static int DragWidth => Math.Max(1, Math.Abs(GetSystemMetrics(68)));
    internal static int DragHeight => Math.Max(1, Math.Abs(GetSystemMetrics(69)));
}
