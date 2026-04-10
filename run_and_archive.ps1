# run_and_archive.ps1 — Apéry validation + long Family B discovery run + shard archival
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "=== Step 1: Apéry PCF validation ===" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -c @"
from importlib import reload
import ramanujan_breakthrough_generator as rbg
from mpmath import mp
mp.dps = 120
reload(rbg)
engine = rbg.PCFEngine(precision=100)
alpha = [0,0,0,0,0,0,-1]
beta  = [5,27,51,34]
val, err, conv = engine.evaluate_pcf(alpha, beta, depth=500)
diff = abs(val - 6/mp.zeta(3))
digits = -int(mp.log10(diff)) if diff > 0 else 120
print(f'Apery match: {digits} digits')
if digits < 50:
    print('WARNING: Apery match below 50 digits — generator may be broken')
    exit(1)
else:
    print('OK — generator verified')
"@
if ($LASTEXITCODE -ne 0) {
    Write-Host "Apéry validation FAILED — aborting" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Step 2: Run regression tests ===" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m pytest tests/test_regressions.py -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "Regression tests FAILED — aborting" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Step 3: Long Family B discovery run ===" -ForegroundColor Cyan
.\.venv\Scripts\python.exe ramanujan_parallel_launcher.py `
    --families B `
    --workers 1 `
    --budget-scale 15 `
    --coeff 45 `
    --max-depth 220 `
    --timeout 86400 `
    2>&1 | Tee-Object -FilePath run_B_long.log

Write-Host "`n=== Step 4: Archive shards ===" -ForegroundColor Cyan
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$archiveDir = "shards\$ts"
New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
Copy-Item registry_*.json $archiveDir\ -ErrorAction SilentlyContinue
Copy-Item ramanujan_registry.json $archiveDir\ -ErrorAction SilentlyContinue
Copy-Item run_B_long.log $archiveDir\ -ErrorAction SilentlyContinue
Write-Host "Archived to $archiveDir" -ForegroundColor Green

Write-Host "`n=== Done ===" -ForegroundColor Cyan
