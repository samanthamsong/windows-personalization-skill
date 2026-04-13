# notification-watcher.ps1 — Monitors Windows toast notifications via Event Log
# When a new toast is delivered (Event ID 3153), writes to .pause to trigger a flash

param(
    [string]$Color = "#FF69B4",
    [int]$Duration = 3,
    [int]$CooldownSec = 5,
    [int]$PollMs = 1000
)

$pauseFile = Join-Path $PSScriptRoot "rules\.pause"
$logName = "Microsoft-Windows-PushNotification-Platform/Operational"

# Get the latest event timestamp as our baseline
$latest = Get-WinEvent -LogName $logName -MaxEvents 1 -FilterXPath "*[System[EventID=3153]]" -ErrorAction SilentlyContinue
$lastSeen = if ($latest) { $latest.TimeCreated } else { Get-Date }
$lastFlash = [datetime]::MinValue

Write-Host "Notification watcher started"
Write-Host "  Color: $Color | Duration: $($Duration)s | Cooldown: $($CooldownSec)s"
Write-Host "  Monitoring Event Log for toast deliveries (Event ID 3153)..."
Write-Host "  Baseline: $lastSeen"
Write-Host ""

while ($true) {
    try {
        $events = Get-WinEvent -LogName $logName -FilterXPath "*[System[EventID=3153]]" -MaxEvents 5 -ErrorAction SilentlyContinue |
            Where-Object { $_.TimeCreated -gt $lastSeen }

        if ($events -and $events.Count -gt 0) {
            $newest = $events | Sort-Object TimeCreated -Descending | Select-Object -First 1
            $lastSeen = $newest.TimeCreated

            # Extract app name from message
            $appMatch = [regex]::Match($newest.Message, 'delivered to\s+(\S+)')
            $app = if ($appMatch.Success) { $appMatch.Groups[1].Value.Split('!')[0].Split('_')[0] } else { "Unknown" }

            $now = Get-Date
            $sinceLast = ($now - $lastFlash).TotalSeconds

            if ($sinceLast -ge $CooldownSec) {
                $ts = $now.ToString('HH:mm:ss')
                Write-Host "[$ts] Toast from: $app - flashing $Color"
                $payload = "$Color" + "|" + "$Duration"
                [System.IO.File]::WriteAllText($pauseFile, $payload)
                $lastFlash = $now
            } else {
                $ts = $now.ToString('HH:mm:ss')
                Write-Host "[$ts] Toast from: $app - cooldown ($([int]$sinceLast)s < $($CooldownSec)s)"
            }
        }
    } catch {
        # Silently continue on transient errors
    }

    Start-Sleep -Milliseconds $PollMs
}
