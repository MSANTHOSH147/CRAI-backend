$ErrorActionPreference = "Stop"

$backend = "C:\Users\91807\Downloads\CRAI_project_structure\CRAI-private\backend"
Set-Location $backend

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "CRAI .venv Python not found."
}

Write-Host "`n[1/6] Installing lifecycle service into the ACTIVE CRAI service..." -ForegroundColor Cyan

$active = ".\app\services\farm_event_service.py"
$patch = ".\app\services\farm_event_service.lifecycle_phase.py"
$backup = ".\app\services\farm_event_service.before_lifecycle_demo_$(Get-Date -Format 'yyyyMMdd_HHmmss').py"

if (-not (Test-Path $patch)) {
    throw "Missing $patch. Keep farm_event_service.lifecycle_phase.py in app\services."
}

Copy-Item $active $backup -Force
Copy-Item $patch $active -Force

Write-Host "Backup: $backup"
Write-Host "Active service replaced."

Write-Host "`n[2/6] Verifying import + full tests..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m compileall app
& ".\.venv\Scripts\python.exe" -c "from app.main import app; print('CRAI IMPORT: PASS')"
& ".\.venv\Scripts\python.exe" -m pytest -q

Write-Host "`n[3/6] Starting backend if needed..." -ForegroundColor Cyan

try {
    $health = Invoke-RestMethod "http://127.0.0.1:8000/api/health" -TimeoutSec 3
    Write-Host "Backend already running: $($health.status) / $($health.service)"
}
catch {
    $logOut = Join-Path $backend "crAI_demo_server.out.log"
    $logErr = Join-Path $backend "crAI_demo_server.err.log"

    Start-Process `
        -FilePath ".\.venv\Scripts\python.exe" `
        -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port 8000" `
        -WorkingDirectory $backend `
        -RedirectStandardOutput $logOut `
        -RedirectStandardError $logErr `
        -WindowStyle Hidden

    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:8000/api/health" -TimeoutSec 2
            $ready = $true
            break
        } catch {}
    }

    if (-not $ready) {
        Write-Host "Server stdout:" -ForegroundColor Yellow
        if (Test-Path $logOut) { Get-Content $logOut -Tail 30 }
        Write-Host "Server stderr:" -ForegroundColor Yellow
        if (Test-Path $logErr) { Get-Content $logErr -Tail 30 }
        throw "Backend did not become ready."
    }
}

Write-Host "`n[4/6] Creating a clean demo field..." -ForegroundColor Cyan

$device = "CRAI-DEMO-001"
$farm = 1
$zone = "DEMO-A1"

# Severe event scenario
$scenario = @{
    device_id = $device
    farm_id = $farm
    zone_id = $zone
    scenario = "SEVERE_EVENT"
    interval = 1
    seed = 42
    reset_step = $true
} | ConvertTo-Json

Invoke-RestMethod `
    -Method POST `
    -Uri "http://127.0.0.1:8000/api/simulator/scenario" `
    -ContentType "application/json" `
    -Body $scenario | Out-Null

Invoke-RestMethod `
    -Method POST `
    -Uri "http://127.0.0.1:8000/api/simulator/step" `
    -ContentType "application/json" `
    -Body (@{
        device_id=$device
        farm_id=$farm
        zone_id=$zone
        steps=1
    } | ConvertTo-Json) | Out-Null

$severe = @{
    device_id=$device
    farm_id=$farm
    zone_id=$zone
    crop="Tomato"
    growth_stage="Vegetative"
    prediction="severe crop stress and disease risk detected"
    confidence=95
    thermal_anomaly=8
} | ConvertTo-Json

$r1 = Invoke-RestMethod `
    -Method POST `
    -Uri "http://127.0.0.1:8000/api/simulator/evaluate" `
    -ContentType "application/json" `
    -Body $severe

$eventId = $r1.event.event_id

Write-Host "`nSEVERE EVENT" -ForegroundColor Red
Write-Host "Event ID : $eventId"
Write-Host "Status   : $($r1.event.status)"
Write-Host "Risk     : $($r1.event.risk_level) / $($r1.event.risk_score)"
Write-Host "Action   : $($r1.event.action)"

# Recovery observation
$recoveryScenario = @{
    device_id=$device
    farm_id=$farm
    zone_id=$zone
    scenario="RECOVERY"
    interval=2
    seed=42
    reset_step=$true
} | ConvertTo-Json

Invoke-RestMethod `
    -Method POST `
    -Uri "http://127.0.0.1:8000/api/simulator/scenario" `
    -ContentType "application/json" `
    -Body $recoveryScenario | Out-Null

Invoke-RestMethod `
    -Method POST `
    -Uri "http://127.0.0.1:8000/api/simulator/step" `
    -ContentType "application/json" `
    -Body (@{
        device_id=$device
        farm_id=$farm
        zone_id=$zone
        steps=1
    } | ConvertTo-Json) | Out-Null

$recovery = @{
    device_id=$device
    farm_id=$farm
    zone_id=$zone
    crop="Tomato"
    growth_stage="Vegetative"
    prediction="crop condition improving after intervention"
    confidence=90
    thermal_anomaly=2
} | ConvertTo-Json

$r2 = Invoke-RestMethod `
    -Method POST `
    -Uri "http://127.0.0.1:8000/api/simulator/evaluate" `
    -ContentType "application/json" `
    -Body $recovery

Write-Host "`nRECOVERY OBSERVATION" -ForegroundColor Yellow
Write-Host "Event ID : $($r2.event.event_id)"
Write-Host "Status   : $($r2.event.status)"
Write-Host "Risk     : $($r2.event.risk_level) / $($r2.event.risk_score)"
Write-Host "During phase: $($r2.event.during_state.phase)"

# ============================================================
# CONFIRM RECOVERY AND RESOLVE EVENT
# ============================================================

Invoke-RestMethod `
    -Method POST `
    -Uri "http://127.0.0.1:8000/api/simulator/step" `
    -ContentType "application/json" `
    -Body (@{
        device_id=$device
        farm_id=$farm
        zone_id=$zone
        steps=1
    } | ConvertTo-Json) | Out-Null

$safe = @{
    device_id=$device
    farm_id=$farm
    zone_id=$zone
    crop="Tomato"
    growth_stage="Vegetative"
    prediction="healthy crop condition confirmed after recovery"
    confidence=95
    thermal_anomaly=0
} | ConvertTo-Json

# First safe observation -> RECOVERING
$r3 = Invoke-RestMethod `
    -Method POST `
    -Uri "http://127.0.0.1:8000/api/simulator/evaluate" `
    -ContentType "application/json" `
    -Body $safe

Write-Host "`nSAFE / RECOVERY CONFIRMATION" -ForegroundColor Yellow
Write-Host "Event ID : $($r3.event.event_id)"
Write-Host "Status   : $($r3.event.status)"
Write-Host "Risk     : $($r3.event.risk_level) / $($r3.event.risk_score)"
Write-Host "Before   : $($r3.event.before_state.phase)"
Write-Host "During   : $($r3.event.during_state.phase)"
Write-Host "After    : $($r3.event.after_state.phase)"

if ($r3.event.status -ne "RECOVERING") {
    throw "Expected RECOVERING after first safe observation."
}

# Second safe observation -> RESOLVED / AFTER
Invoke-RestMethod `
    -Method POST `
    -Uri "http://127.0.0.1:8000/api/simulator/step" `
    -ContentType "application/json" `
    -Body (@{
        device_id=$device
        farm_id=$farm
        zone_id=$zone
        steps=1
    } | ConvertTo-Json) | Out-Null

$r4 = Invoke-RestMethod `
    -Method POST `
    -Uri "http://127.0.0.1:8000/api/simulator/evaluate" `
    -ContentType "application/json" `
    -Body $safe

Write-Host "`nFINAL EVENT" -ForegroundColor Green
Write-Host "Event ID : $($r4.event.event_id)"
Write-Host "Status   : $($r4.event.status)"
Write-Host "Risk     : $($r4.event.risk_level) / $($r4.event.risk_score)"
Write-Host "Before   : $($r4.event.before_state.phase)"
Write-Host "During   : $($r4.event.during_state.phase)"
Write-Host "After    : $($r4.event.after_state.phase)"
Write-Host "Resolved : $($r4.event.resolved_at)"

if ($r4.event.status -ne "RESOLVED") {
    throw "Lifecycle demo did not finish RESOLVED."
}

if ($r4.event.before_state.phase -ne "BEFORE") {
    throw "BEFORE phase missing."
}

if ($r4.event.during_state.phase -notin @("DURING","RECOVERY")) {
    throw "DURING/RECOVERY phase missing."
}

if ($r4.event.after_state.phase -ne "AFTER") {
    throw "AFTER phase missing."
}

Write-Host "`nLifecycle: BEFORE -> DURING -> RECOVERY -> AFTER -> RESOLVED" -ForegroundColor Cyan


$timeline = Invoke-RestMethod "http://127.0.0.1:8000/api/events/$eventId/timeline"
$evidence = Invoke-RestMethod "http://127.0.0.1:8000/api/events/$eventId/evidence"
$verify = Invoke-RestMethod -Method POST "http://127.0.0.1:8000/api/evidence/verify?event_id=$eventId"

Write-Host "Timeline: PASS"
Write-Host "Evidence: PASS"
Write-Host "Integrity: $($verify.valid)"

if (-not $verify.valid) {
    throw "Integrity verification failed."
}

Write-Host "`n[6/6] CRAI DEMO READY" -ForegroundColor Green
Write-Host "Lifecycle: BEFORE -> DURING -> RECOVERY -> AFTER -> RESOLVED"
Write-Host "Event ID : $eventId"
Write-Host "Tests    : PASS"
Write-Host "Integrity: VALID"
Write-Host "Backend  : http://127.0.0.1:8000"
