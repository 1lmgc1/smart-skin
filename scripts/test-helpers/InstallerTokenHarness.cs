// Test-only Windows token/process helper. Never distributed in the runtime ZIP.
// Uses a restricted copy of the current user's token; no accounts, passwords,
// machine policy, registry ACLs, or persistent security settings are changed.
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;

namespace SmartSkin.InstallerTests
{
    public sealed class TokenFacts
    {
        public string UserSid;
        public bool IsAdministrator;
        public bool IsElevated;
        public bool HasRestrictingSids;
        public bool AdministratorsSidDenyOnly;
        public int IntegrityRid;
    }

    public static class TokenProcess
    {
        const uint TOKEN_ALL_ACCESS = 0xF01FF;
        const uint DISABLE_MAX_PRIVILEGE = 1;
        const uint CREATE_SUSPENDED = 4;
        const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;
        const uint WAIT_TIMEOUT = 258;
        const int TokenElevation = 20, TokenIntegrityLevel = 25;

        [StructLayout(LayoutKind.Sequential)] struct SID_AND_ATTRIBUTES { public IntPtr Sid; public uint Attributes; }
        [StructLayout(LayoutKind.Sequential)] struct TOKEN_GROUPS_HEADER { public uint Count; public SID_AND_ATTRIBUTES First; }
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] struct STARTUPINFO
        {
            public int cb; public string lpReserved, lpDesktop, lpTitle;
            public uint dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
            public short wShowWindow, cbReserved2; public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
        }
        [StructLayout(LayoutKind.Sequential)] struct PROCESS_INFORMATION
        { public IntPtr hProcess, hThread; public uint dwProcessId, dwThreadId; }
        [StructLayout(LayoutKind.Sequential)] struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            public long PerProcessUserTimeLimit, PerJobUserTimeLimit; public uint LimitFlags;
            public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize; public uint ActiveProcessLimit;
            public UIntPtr Affinity; public uint PriorityClass, SchedulingClass;
        }
        [StructLayout(LayoutKind.Sequential)] struct IO_COUNTERS
        { public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount, ReadTransferCount, WriteTransferCount, OtherTransferCount; }
        [StructLayout(LayoutKind.Sequential)] struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation; public IO_COUNTERS IoInfo;
            public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
        }

        [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
        [DllImport("kernel32.dll", SetLastError = true)] static extern bool CloseHandle(IntPtr handle);
        [DllImport("kernel32.dll", SetLastError = true)] static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
        [DllImport("kernel32.dll", SetLastError = true)] static extern bool GetExitCodeProcess(IntPtr process, out uint exitCode);
        [DllImport("kernel32.dll", SetLastError = true)] static extern uint ResumeThread(IntPtr thread);
        [DllImport("kernel32.dll", SetLastError = true)] static extern bool TerminateProcess(IntPtr process, uint exitCode);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr CreateJobObject(IntPtr attributes, string name);
        [DllImport("kernel32.dll", SetLastError = true)] static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref JOBOBJECT_EXTENDED_LIMIT_INFORMATION info, uint length);
        [DllImport("kernel32.dll", SetLastError = true)] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool CreateProcess(string application, StringBuilder command, IntPtr processAttributes, IntPtr threadAttributes, bool inheritHandles, uint flags, IntPtr environment, string directory, ref STARTUPINFO startup, out PROCESS_INFORMATION process);
        [DllImport("advapi32.dll", SetLastError = true)] static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
        [DllImport("advapi32.dll", SetLastError = true)] static extern bool CreateRestrictedToken(IntPtr existingToken, uint flags, uint disabledCount, [In] SID_AND_ATTRIBUTES[] disabled, uint deletedCount, IntPtr deleted, uint restrictedCount, IntPtr restricted, out IntPtr token);
        [DllImport("advapi32.dll", SetLastError = true)] static extern bool GetTokenInformation(IntPtr token, int infoClass, IntPtr info, int size, out int needed);
        [DllImport("advapi32.dll", SetLastError = true)] static extern bool SetTokenInformation(IntPtr token, int infoClass, IntPtr info, int length);
        [DllImport("advapi32.dll", SetLastError = true)] static extern bool IsTokenRestricted(IntPtr token);
        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool ConvertStringSidToSid(string sid, out IntPtr result);
        [DllImport("advapi32.dll")] static extern int GetLengthSid(IntPtr sid);
        [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr value);
        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool CreateProcessAsUser(IntPtr token, string application, StringBuilder command, IntPtr processAttributes, IntPtr threadAttributes, bool inheritHandles, uint flags, IntPtr environment, string directory, ref STARTUPINFO startup, out PROCESS_INFORMATION process);
        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool CreateProcessWithTokenW(IntPtr token, uint logonFlags, string application, StringBuilder command, uint flags, IntPtr environment, string directory, ref STARTUPINFO startup, out PROCESS_INFORMATION process);

        static void Check(bool success, string operation)
        { if (!success) throw new Win32Exception(Marshal.GetLastWin32Error(), operation); }

        public static TokenFacts CurrentFacts()
        {
            using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
            {
                TokenFacts facts = new TokenFacts();
                facts.UserSid = identity.User.Value;
                facts.IsAdministrator = new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
                facts.HasRestrictingSids = IsTokenRestricted(identity.Token);
                int needed;
                GetTokenInformation(identity.Token, 2, IntPtr.Zero, 0, out needed);
                IntPtr groups = Marshal.AllocHGlobal(needed);
                try
                {
                    Check(GetTokenInformation(identity.Token, 2, groups, needed, out needed), "Read token groups");
                    int count = Marshal.ReadInt32(groups);
                    int offset = Marshal.OffsetOf(typeof(TOKEN_GROUPS_HEADER), "First").ToInt32();
                    int stride = Marshal.SizeOf(typeof(SID_AND_ATTRIBUTES));
                    for (int index = 0; index < count; index++)
                    {
                        SID_AND_ATTRIBUTES group = (SID_AND_ATTRIBUTES)Marshal.PtrToStructure(IntPtr.Add(groups, offset + index * stride), typeof(SID_AND_ATTRIBUTES));
                        if (new SecurityIdentifier(group.Sid).Value == "S-1-5-32-544") facts.AdministratorsSidDenyOnly = (group.Attributes & 0x10) != 0;
                    }
                }
                finally { Marshal.FreeHGlobal(groups); }
                IntPtr value = Marshal.AllocHGlobal(4);
                try { Check(GetTokenInformation(identity.Token, TokenElevation, value, 4, out needed), "Read token elevation"); facts.IsElevated = Marshal.ReadInt32(value) != 0; }
                finally { Marshal.FreeHGlobal(value); }
                GetTokenInformation(identity.Token, TokenIntegrityLevel, IntPtr.Zero, 0, out needed);
                value = Marshal.AllocHGlobal(needed);
                try
                {
                    Check(GetTokenInformation(identity.Token, TokenIntegrityLevel, value, needed, out needed), "Read token integrity");
                    SID_AND_ATTRIBUTES label = (SID_AND_ATTRIBUTES)Marshal.PtrToStructure(value, typeof(SID_AND_ATTRIBUTES));
                    string sid = new SecurityIdentifier(label.Sid).Value;
                    facts.IntegrityRid = int.Parse(sid.Substring(sid.LastIndexOf('-') + 1));
                }
                finally { Marshal.FreeHGlobal(value); }
                return facts;
            }
        }

        // All children run in a disposable kill-on-close job, so a failed or timed-out
        // assertion cannot leave an installer (or anything it launched) running in CI.
        public static int Run(string executable, string arguments, string directory, bool restrictToken, int timeoutSeconds)
        {
            IntPtr current = IntPtr.Zero, restricted = IntPtr.Zero, adminSid = IntPtr.Zero, mediumSid = IntPtr.Zero, job = IntPtr.Zero;
            PROCESS_INFORMATION process = new PROCESS_INFORMATION();
            try
            {
                if (restrictToken)
                {
                    Check(OpenProcessToken(GetCurrentProcess(), TOKEN_ALL_ACCESS, out current), "Open current user token");
                    Check(ConvertStringSidToSid("S-1-5-32-544", out adminSid), "Create Administrators SID");
                    SID_AND_ATTRIBUTES[] denyOnly = new SID_AND_ATTRIBUTES[] { new SID_AND_ATTRIBUTES { Sid = adminSid } };
                    Check(CreateRestrictedToken(current, DISABLE_MAX_PRIVILEGE, 1, denyOnly, 0, IntPtr.Zero, 0, IntPtr.Zero, out restricted), "Create same-user non-admin token");
                    Check(ConvertStringSidToSid("S-1-16-8192", out mediumSid), "Create medium integrity SID");
                    SID_AND_ATTRIBUTES label = new SID_AND_ATTRIBUTES { Sid = mediumSid, Attributes = 0x20 };
                    IntPtr buffer = Marshal.AllocHGlobal(Marshal.SizeOf(label));
                    try
                    {
                        Marshal.StructureToPtr(label, buffer, false);
                        Check(SetTokenInformation(restricted, TokenIntegrityLevel, buffer, Marshal.SizeOf(label) + GetLengthSid(mediumSid)), "Set restricted token medium integrity");
                    }
                    finally { Marshal.FreeHGlobal(buffer); }
                }
                job = CreateJobObject(IntPtr.Zero, null);
                Check(job != IntPtr.Zero, "Create disposable test job");
                JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
                limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                Check(SetInformationJobObject(job, 9, ref limits, (uint)Marshal.SizeOf(limits)), "Set test job lifetime");
                STARTUPINFO startup = new STARTUPINFO(); startup.cb = Marshal.SizeOf(startup);
                string command = "\"" + executable + "\" " + arguments;
                bool created;
                if (restrictToken)
                {
                    created = CreateProcessAsUser(restricted, executable, new StringBuilder(command), IntPtr.Zero, IntPtr.Zero, false, CREATE_SUSPENDED, IntPtr.Zero, directory, ref startup, out process);
                    if (!created && Marshal.GetLastWin32Error() == 1314)
                    {
                        // Supported same-token fallback for CI service accounts holding
                        // SeImpersonatePrivilege rather than SeIncreaseQuotaPrivilege.
                        created = CreateProcessWithTokenW(restricted, 0, executable, new StringBuilder(command), CREATE_SUSPENDED, IntPtr.Zero, directory, ref startup, out process);
                    }
                }
                else { created = CreateProcess(executable, new StringBuilder(command), IntPtr.Zero, IntPtr.Zero, false, CREATE_SUSPENDED, IntPtr.Zero, directory, ref startup, out process); }
                Check(created, restrictToken ? "Launch genuine non-admin Windows process" : "Launch full-token Windows process");
                Check(AssignProcessToJobObject(job, process.hProcess), "Assign installer to disposable test job");
                Check(ResumeThread(process.hThread) != UInt32.MaxValue, "Resume installer test process");
                uint wait = WaitForSingleObject(process.hProcess, checked((uint)timeoutSeconds * 1000));
                if (wait == WAIT_TIMEOUT) throw new TimeoutException("Installer entry exceeded " + timeoutSeconds + " seconds.");
                Check(wait == 0, "Wait for installer test process");
                uint exit; Check(GetExitCodeProcess(process.hProcess, out exit), "Read installer test result");
                return unchecked((int)exit);
            }
            finally
            {
                if (process.hProcess != IntPtr.Zero) { TerminateProcess(process.hProcess, 124); CloseHandle(process.hProcess); }
                if (process.hThread != IntPtr.Zero) CloseHandle(process.hThread);
                if (job != IntPtr.Zero) CloseHandle(job);
                if (restricted != IntPtr.Zero) CloseHandle(restricted);
                if (current != IntPtr.Zero) CloseHandle(current);
                if (adminSid != IntPtr.Zero) LocalFree(adminSid);
                if (mediumSid != IntPtr.Zero) LocalFree(mediumSid);
            }
        }
    }
}
