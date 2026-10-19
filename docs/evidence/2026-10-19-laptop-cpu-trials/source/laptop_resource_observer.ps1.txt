param(
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [Parameter(Mandatory=$true)][string]$PhasePath,
    [Parameter(Mandatory=$true)][string]$StopPath,
    [int]$MaxSeconds = 3600
)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class LaptopCounters {
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool GetProcessTimes(IntPtr handle, out long created, out long exited, out long kernel, out long user);
    [StructLayout(LayoutKind.Sequential)] public struct Memory {
        public uint size, pageFaults;
        public UIntPtr peakWorkingSet, workingSet, peakPaged, paged, peakNonpaged, nonpaged, pagefile, peakPagefile;
    }
    [DllImport("psapi.dll", SetLastError=true)] static extern bool GetProcessMemoryInfo(IntPtr handle, out Memory memory, uint size);
    public static List<Dictionary<string,object>> Processes() {
        var result = new List<Dictionary<string,object>>();
        foreach (var process in System.Diagnostics.Process.GetProcesses()) {
            using (process) {
                var errors = new List<string>();
                var item = new Dictionary<string,object> {{"pid",process.Id}, {"errors",errors}};
                try { item["name"] = process.ProcessName; } catch { errors.Add("name_unavailable"); }
                IntPtr handle = OpenProcess(0x1000, false, process.Id);
                if (handle == IntPtr.Zero) {
                    errors.Add("process_access_unavailable:" + Marshal.GetLastWin32Error());
                } else {
                    try {
                        long created, exited, kernel, user;
                        if (GetProcessTimes(handle, out created, out exited, out kernel, out user)) {
                            item["cpu_seconds"] = (kernel + user) / 10000000.0;
                            item["start_utc"] = DateTime.FromFileTimeUtc(created).ToString("o");
                        } else { errors.Add("cpu_unavailable:" + Marshal.GetLastWin32Error()); }
                        Memory memory;
                        if (GetProcessMemoryInfo(handle, out memory, (uint)Marshal.SizeOf(typeof(Memory)))) {
                            item["working_set_bytes"] = memory.workingSet.ToUInt64();
                        } else { errors.Add("working_set_unavailable:" + Marshal.GetLastWin32Error()); }
                    } finally { CloseHandle(handle); }
                }
                result.Add(item);
            }
        }
        return result;
    }
    [DllImport("kernel32.dll")] public static extern bool GetSystemTimes(out ulong idle, out ulong kernel, out ulong user);
    [StructLayout(LayoutKind.Sequential)] public struct Power {
        public byte ac, flags, percent, reserved;
        public uint life, full;
    }
    [DllImport("kernel32.dll")] public static extern bool GetSystemPowerStatus(out Power power);
    [StructLayout(LayoutKind.Sequential)] public struct Formatted {
        public uint status;
        public double value;
    }
    [StructLayout(LayoutKind.Sequential)] public struct Raw {
        public uint status;
        public System.Runtime.InteropServices.ComTypes.FILETIME timestamp;
        public long first, second;
        public uint multiple;
    }
    [DllImport("pdh.dll", CharSet=CharSet.Unicode)] static extern uint PdhOpenQuery(string source, IntPtr data, out IntPtr query);
    [DllImport("pdh.dll", CharSet=CharSet.Unicode)] static extern uint PdhAddEnglishCounter(IntPtr query, string path, IntPtr data, out IntPtr counter);
    [DllImport("pdh.dll")] static extern uint PdhCollectQueryData(IntPtr query);
    [DllImport("pdh.dll")] static extern uint PdhGetFormattedCounterValue(IntPtr counter, uint format, out uint type, out Formatted value);
    [DllImport("pdh.dll")] static extern uint PdhGetRawCounterValue(IntPtr counter, out uint type, out Raw value);
    static IntPtr query;
    static Dictionary<string,IntPtr> counters = new Dictionary<string,IntPtr>();
    static Dictionary<string,uint> setup = new Dictionary<string,uint>();
    public static void Init() {
        uint opened = PdhOpenQuery(null, IntPtr.Zero, out query);
        setup["open_query"] = opened;
        if (opened != 0) return;
        string[] paths = {
            @"\Memory\Available Bytes", @"\Memory\Committed Bytes", @"\Memory\Commit Limit",
            @"\Memory\Pages Input/sec", @"\Memory\Page Reads/sec",
            @"\PhysicalDisk(_Total)\Disk Bytes/sec", @"\PhysicalDisk(_Total)\Disk Reads/sec",
            @"\Processor Information(_Total)\Processor Frequency",
            @"\Processor Information(_Total)\% Processor Performance"
        };
        foreach (string path in paths) {
            IntPtr counter;
            uint status = PdhAddEnglishCounter(query, path, IntPtr.Zero, out counter);
            setup[path] = status;
            if (status == 0) counters[path] = counter;
        }
        PdhCollectQueryData(query);
    }
    public static Dictionary<string,object> Performance() {
        var result = new Dictionary<string,object>();
        result["setup_status"] = setup;
        result["collect_status"] = PdhCollectQueryData(query);
        foreach (var counter in counters) {
            uint type; Formatted formatted; Raw raw;
            uint fs = PdhGetFormattedCounterValue(counter.Value, 0x200, out type, out formatted);
            uint rs = PdhGetRawCounterValue(counter.Value, out type, out raw);
            result[counter.Key] = new Dictionary<string,object> {
                {"format_status",fs}, {"value_status",formatted.status},
                {"value", fs == 0 && formatted.status <= 1 ? (object)formatted.value : null},
                {"raw_status",rs}, {"raw_value_status",raw.status},
                {"raw_first",raw.first}, {"raw_second",raw.second}, {"raw_multiple",raw.multiple},
                {"raw_timestamp_low",raw.timestamp.dwLowDateTime},
                {"raw_timestamp_high",raw.timestamp.dwHighDateTime}, {"counter_type",type}
            };
        }
        return result;
    }
}
'@
[LaptopCounters]::Init()
$observerClock = [Diagnostics.Stopwatch]::StartNew()
$lastStart = $null
while ($observerClock.Elapsed.TotalSeconds -lt $MaxSeconds -and -not (Test-Path -LiteralPath $StopPath)) {
    $sampleStart = $observerClock.Elapsed.TotalSeconds
    $sample = @{
        utc = [DateTime]::UtcNow.ToString('o')
        observer_elapsed_seconds = $sampleStart
        target_interval_seconds = 2
        sample_gap_seconds = $(if ($null -eq $lastStart) { $null } else { $sampleStart - $lastStart })
        performance_counter_frequency = [Diagnostics.Stopwatch]::Frequency
        phase = 'unknown'
        errors = @()
        processes = @()
    }
    $lastStart = $sampleStart
    try { $sample.phase = [IO.File]::ReadAllText($PhasePath).Trim() } catch { $sample.errors += 'phase_unavailable' }
    [UInt64]$idle = 0; [UInt64]$kernel = 0; [UInt64]$user = 0
    if ([LaptopCounters]::GetSystemTimes([ref]$idle, [ref]$kernel, [ref]$user)) {
        $sample.system_cpu = @{idle_100ns=$idle; kernel_100ns=$kernel; user_100ns=$user}
    } else { $sample.errors += 'system_cpu_unavailable' }
    $power = New-Object LaptopCounters+Power
    if ([LaptopCounters]::GetSystemPowerStatus([ref]$power)) {
        $sample.power = @{ac_line_status=$power.ac; battery_percent=$power.percent; battery_flags=$power.flags}
    } else { $sample.errors += 'power_unavailable' }
    $sample.processes = [LaptopCounters]::Processes()
    $sample.process_collection_seconds = $observerClock.Elapsed.TotalSeconds - $sampleStart
    $performanceStart = $observerClock.Elapsed.TotalSeconds
    try { $sample.performance = [LaptopCounters]::Performance() }
    catch { $sample.errors += ('performance_unavailable:' + $_.Exception.GetType().Name) }
    $sample.performance_collection_seconds = $observerClock.Elapsed.TotalSeconds - $performanceStart
    $sample.observer_pid = $PID
    $sample.observer_cpu_seconds = [Diagnostics.Process]::GetCurrentProcess().TotalProcessorTime.TotalSeconds
    $sample.duration_seconds = $observerClock.Elapsed.TotalSeconds - $sampleStart
    [IO.File]::AppendAllText($OutputPath, (($sample | ConvertTo-Json -Depth 7 -Compress) + [Environment]::NewLine))
    $remainingMs = [Math]::Max(0, 2000 - ($observerClock.Elapsed.TotalSeconds - $sampleStart) * 1000)
    if ($remainingMs -gt 0) { Start-Sleep -Milliseconds ([int]$remainingMs) }
}
