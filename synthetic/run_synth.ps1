# Runs the four readers on the synthetic set, one process each, pinned to one logical CPU.
#
#   powershell -ExecutionPolicy Bypass -File synthetic\run_synth.ps1 -DmrPrefix <unpacked dmr package> [-Reps 1] [-Only dmr,zxingcpp,...]
#
# Before: python synthetic\png_to_pgm.py   (frames\*.png -> gray\*.pgm + frames.lst)
# Writes synthetic\results\raw\<library>.tsv (idx, rep, ok, hex(text), ms, timedOut) and
# <library>.cpuperf (mean;min delivered CPU performance, % of nominal;samples), then the summary.
#
# Requirements (Windows, MSYS2 MINGW64): mingw-w64-x86_64-gcc, -pkgconf, -libdmtx;
# Python 3 with zxing-cpp and numpy; Java 11+ and ZXing core-3.5.4.jar in tools\zxing-java.
# dmr: the Windows x64 package from https://libscanner.com or GitHub Releases
# (libscanner/datamatrix-reader), unpacked; -DmrPrefix points at its root (bin, include, lib).
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DmrPrefix,
    [int]$Reps = 1,
    [int]$Warmup = 20,
    [int]$DmtxTimeoutMs = 3000,
    [string[]]$Only = @('dmr', 'dmr_single', 'zxingcpp', 'zxingjava', 'libdmtx'),
    [string]$Python = 'python',
    [string]$Msys = 'C:\msys64\mingw64',
    [long]$Affinity = 1
)
$ErrorActionPreference = 'Stop'
$Only = @($Only | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$S    = $PSScriptRoot
$Root = Split-Path -Parent $S
$H    = Join-Path $Root 'harness'
$T    = Join-Path $Root 'tools'
$Raw  = Join-Path $S 'results\raw'
$lst  = Join-Path $S 'frames.lst'
if (-not (Test-Path $lst)) { throw "no $lst - run: python synthetic\png_to_pgm.py" }
New-Item -ItemType Directory -Force $Raw, (Join-Path $T 'bin') | Out-Null
$env:PATH = "$Msys\bin;" + $env:PATH

$env:PKG_CONFIG_PATH = Join-Path $DmrPrefix 'lib\pkgconfig'
$dmrFlags = (& "$Msys\bin\pkg-config.exe" --static --cflags --libs dmr) -split ' '
& "$Msys\bin\g++.exe" -std=c++20 -O2 -o (Join-Path $T 'bin\dmr_bench.exe') (Join-Path $H 'dmr_bench.cpp') @dmrFlags -static
if ($LASTEXITCODE) { throw 'dmr_bench build failed' }
& "$Msys\bin\gcc.exe" -O2 -o (Join-Path $T 'bin\dmtx_bench.exe') (Join-Path $H 'dmtx_bench.c') -ldmtx -static
if ($LASTEXITCODE) { throw 'dmtx_bench build failed' }
$jdir = Join-Path $T 'zxing-java'
$jcore = (Get-ChildItem $jdir -Filter 'core-*.jar' | Select-Object -First 1).FullName
& javac -cp $jcore -d $jdir (Join-Path $H 'ZxingBench.java')
if ($LASTEXITCODE) { throw 'ZxingBench build failed' }

function Run-Pinned([string]$name, [string]$exe, [string[]]$arguments) {
    $log = Join-Path $Raw "$name.log"
    Write-Host ("[{0}] {1}" -f (Get-Date -Format HH:mm:ss), $name)
    $quoted = $arguments | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }
    $p = Start-Process -FilePath $exe -ArgumentList $quoted -NoNewWindow -PassThru -RedirectStandardError $log
    $p.ProcessorAffinity = [IntPtr]$Affinity
    # Delivered CPU performance while the reader runs (% of nominal, >100 = turbo):
    # a throttled run makes times meaningless. Read via CIM (Get-Counter fails in
    # some hosts, e.g. under Git Bash or in a hidden window).
    $perf = New-Object System.Collections.Generic.List[double]
    while (-not $p.HasExited) {
        Start-Sleep -Seconds 5
        try {
            $perf.Add([double](Get-CimInstance Win32_PerfFormattedData_Counters_ProcessorInformation `
                        -Filter "Name='_Total'" -ErrorAction Stop).PercentProcessorPerformance)
        } catch { }
    }
    $p.WaitForExit()
    if ($perf.Count) {
        $s = $perf | Measure-Object -Average -Minimum
        ('{0:F1};{1:F1};{2}' -f $s.Average, $s.Minimum, $perf.Count) | Set-Content -Encoding ascii (Join-Path $Raw "$name.cpuperf")
    }
    if ($p.ExitCode) { throw "$name exited with $($p.ExitCode), see $log" }
}

$runs = [ordered]@{
    dmr        = @((Join-Path $T 'bin\dmr_bench.exe'), @($lst, (Join-Path $Raw 'dmr.tsv'), $Warmup, $Reps, 'independent'))
    dmr_single = @((Join-Path $T 'bin\dmr_bench.exe'), @($lst, (Join-Path $Raw 'dmr_single.tsv'), $Warmup, $Reps, 'single'))
    zxingcpp   = @($Python, @((Join-Path $H 'zxingcpp_bench.py'), $lst, (Join-Path $Raw 'zxingcpp.tsv'), $Warmup, $Reps))
    zxingjava  = @('java', @('-cp', "$jcore;$jdir", 'ZxingBench', $lst, (Join-Path $Raw 'zxingjava.tsv'), $Warmup, $Reps))
    libdmtx    = @((Join-Path $T 'bin\dmtx_bench.exe'), @($lst, (Join-Path $Raw 'libdmtx.tsv'), $Warmup, $Reps, $DmtxTimeoutMs))
}
foreach ($k in $runs.Keys) {
    if ($Only -notcontains $k) { continue }
    Run-Pinned $k $runs[$k][0] ([string[]]$runs[$k][1])
}
& $Python (Join-Path $S 'aggregate_synth.py')
