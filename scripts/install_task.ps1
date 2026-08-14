# Zaregistruje scraper do Plánovača úloh Windows.
# Spusti v PowerShelli ako správca:
#   powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1
#
# Odinštalovanie:
#   Unregister-ScheduledTask -TaskName "Nehnutelnosti scraper" -Confirm:$false

param(
    [string]$Time = "07:00",                 # čas prvého denného behu
    [int]$RepeatHours = 6,                   # ako často opakovať počas dňa
    [string]$TaskName = "Nehnutelnosti scraper"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\pythonw.exe"
$script = Join-Path $root "run.py"

if (-not (Test-Path $python)) {
    Write-Error "Nenašiel som $python . Najprv vytvor virtuálne prostredie:`n  python -m venv .venv`n  .\.venv\Scripts\pip install -r requirements.txt"
}
if (-not (Test-Path $script)) { Write-Error "Nenašiel som $script" }

$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $Time `
    -RepetitionInterval (New-TimeSpan -Hours $RepeatHours) `
    -RepetitionDuration (New-TimeSpan -Hours 24)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Ponuky priamo od majiteľa z nehnutelnosti.sk do Google Sheets" -Force | Out-Null

Write-Host ""
Write-Host "Hotovo. Úloha '$TaskName' je zaregistrovaná." -ForegroundColor Green
Write-Host "  Prvý beh:  $Time, potom každých $RepeatHours h"
Write-Host "  Priečinok: $root"
Write-Host ""
Write-Host "Spustiť hneď teraz:   Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Zobraziť stav:        Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Host "Odstrániť:            Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
