param(
    [string]$TaskName = "stock_option_agent",
    [string]$PythonBin = "",
    [string]$AgentConfigPath = "",
    [switch]$EnableAfterHours
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
$runnerPath = Join-Path $scriptDir "run_agent.ps1"

if (-not $PythonBin) {
    $venvPython = Join-Path $rootDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonBin = $venvPython
    } else {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCmd) {
            $PythonBin = $pythonCmd.Source
        } else {
            throw "Python executable not found. Set -PythonBin or create .venv."
        }
    }
}

if (-not $AgentConfigPath) {
    $AgentConfigPath = Join-Path $rootDir "config\agent_config.json"
}

$runnerArgs = @(
    "-NoProfile"
    "-WindowStyle", "Hidden"
    "-ExecutionPolicy", "Bypass"
    "-File", ('"{0}"' -f $runnerPath)
    "-PythonBin", ('"{0}"' -f $PythonBin)
    "-AgentConfigPath", ('"{0}"' -f $AgentConfigPath)
)

if ($EnableAfterHours) {
    $runnerArgs += "-EnableAfterHours"
}

$taskArgs = [System.Security.SecurityElement]::Escape(($runnerArgs -join " "))
$taskRoot = [System.Security.SecurityElement]::Escape($rootDir)
$taskUser = [System.Security.SecurityElement]::Escape(
    [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
)
$taskDate = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")

function New-WeekdayTriggerXml {
    param(
        [int]$Hour,
        [int]$Minute,
        [string]$Duration
    )

    $startBoundary = (Get-Date -Hour $Hour -Minute $Minute -Second 0).ToString("yyyy-MM-ddTHH:mm:ss")
    return @"
    <CalendarTrigger>
      <Repetition>
        <Interval>PT5M</Interval>
        <Duration>$Duration</Duration>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>$startBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <DaysOfWeek>
          <Monday />
          <Tuesday />
          <Wednesday />
          <Thursday />
          <Friday />
        </DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>
"@
}

function New-WeekdayOneShotTriggerXml {
    param(
        [int]$Hour,
        [int]$Minute
    )

    $startBoundary = (Get-Date -Hour $Hour -Minute $Minute -Second 0).ToString("yyyy-MM-ddTHH:mm:ss")
    return @"
    <CalendarTrigger>
      <StartBoundary>$startBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <DaysOfWeek>
          <Monday />
          <Tuesday />
          <Wednesday />
          <Thursday />
          <Friday />
        </DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>
"@
}

$triggerBlocks = @(
    (New-WeekdayTriggerXml -Hour 6 -Minute 30 -Duration "PT30M")
)
foreach ($hour in 7..12) {
    $triggerBlocks += New-WeekdayTriggerXml -Hour $hour -Minute 0 -Duration "PT1H"
}
$triggerBlocks += New-WeekdayOneShotTriggerXml -Hour 13 -Minute 5
$taskTriggers = $triggerBlocks -join "`n"

$taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>$taskDate</Date>
    <Author>$taskUser</Author>
    <Description>Runs the stock/options scanner every 5 minutes during regular market hours.</Description>
  </RegistrationInfo>
  <Triggers>
$taskTriggers
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$taskUser</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT20M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>$taskArgs</Arguments>
      <WorkingDirectory>$taskRoot</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

function Register-TaskWithSchtasksCli {
    $taskCommand = 'powershell.exe {0}' -f ($runnerArgs -join " ")
    $createArgs = @(
        "/Create"
        "/TN", $TaskName
        "/TR", $taskCommand
        "/SC", "WEEKLY"
        "/D", "MON,TUE,WED,THU,FRI"
        "/ST", "06:30"
        "/RI", "5"
        "/DU", "06:30"
        "/F"
    )
    $createOutput = & schtasks.exe @createArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "schtasks.exe failed to create task. Output: $createOutput"
    }

    $xmlText = & schtasks.exe /Query /TN $TaskName /XML 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "schtasks.exe failed to export task XML. Output: $xmlText"
    }

    [xml]$taskDoc = $xmlText
    $ns = New-Object System.Xml.XmlNamespaceManager($taskDoc.NameTable)
    $ns.AddNamespace("t", "http://schemas.microsoft.com/windows/2004/02/mit/task")
    $settingsNode = $taskDoc.SelectSingleNode("/t:Task/t:Settings", $ns)
    $idleNode = $taskDoc.SelectSingleNode("/t:Task/t:Settings/t:IdleSettings", $ns)
    $execNode = $taskDoc.SelectSingleNode("/t:Task/t:Actions/t:Exec", $ns)

    $settingsNode.DisallowStartIfOnBatteries = "false"
    $settingsNode.StopIfGoingOnBatteries = "false"
    if ($idleNode) {
        $idleNode.StopOnIdleEnd = "false"
    }

    foreach ($name in @("StartWhenAvailable", "Enabled", "ExecutionTimeLimit")) {
        $existing = $settingsNode.SelectSingleNode("t:$name", $ns)
        if ($existing) {
            $settingsNode.RemoveChild($existing) | Out-Null
        }
    }
    $startAvailable = $taskDoc.CreateElement("StartWhenAvailable", $settingsNode.NamespaceURI)
    $startAvailable.InnerText = "true"
    $settingsNode.AppendChild($startAvailable) | Out-Null
    $enabledNode = $taskDoc.CreateElement("Enabled", $settingsNode.NamespaceURI)
    $enabledNode.InnerText = "true"
    $settingsNode.AppendChild($enabledNode) | Out-Null
    $executionLimit = $taskDoc.CreateElement("ExecutionTimeLimit", $settingsNode.NamespaceURI)
    $executionLimit.InnerText = "PT20M"
    $settingsNode.AppendChild($executionLimit) | Out-Null

    if ($execNode -and -not $execNode.SelectSingleNode("t:WorkingDirectory", $ns)) {
        $workingDirectory = $taskDoc.CreateElement("WorkingDirectory", $settingsNode.NamespaceURI)
        $workingDirectory.InnerText = $rootDir
        $execNode.AppendChild($workingDirectory) | Out-Null
    }

    $tempXml = Join-Path $env:TEMP "$TaskName.xml"
    try {
        $taskDoc.Save($tempXml)
        $importOutput = & schtasks.exe /Create /TN $TaskName /XML $tempXml /F 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "schtasks.exe failed to import repaired task XML. Output: $importOutput"
        }
    } finally {
        if (Test-Path $tempXml) {
            Remove-Item -LiteralPath $tempXml -Force
        }
    }
}

try {
    Register-ScheduledTask -TaskName $TaskName -Xml $taskXml -Force | Out-Null
} catch {
    $registerError = $_
    $tempXml = Join-Path $env:TEMP "$TaskName.xml"
    try {
        Set-Content -Path $tempXml -Value $taskXml -Encoding Unicode
        $oldErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue) {
            $oldNativeCommandErrorPreference = $global:PSNativeCommandUseErrorActionPreference
            $global:PSNativeCommandUseErrorActionPreference = $false
        }
        $createOutput = & schtasks.exe /Create /TN $TaskName /XML $tempXml /F 2>&1
        $createExitCode = $LASTEXITCODE
        $ErrorActionPreference = $oldErrorActionPreference
        if (Get-Variable -Name oldNativeCommandErrorPreference -ErrorAction SilentlyContinue) {
            $global:PSNativeCommandUseErrorActionPreference = $oldNativeCommandErrorPreference
        }
        if ($createExitCode -ne 0) {
            try {
                Register-TaskWithSchtasksCli
            } catch {
                throw "Register-ScheduledTask failed: $registerError`nschtasks.exe XML import failed: $createOutput`nschtasks.exe CLI fallback failed: $_"
            }
        }
    } finally {
        if ($oldErrorActionPreference) {
            $ErrorActionPreference = $oldErrorActionPreference
        }
        if (Get-Variable -Name oldNativeCommandErrorPreference -ErrorAction SilentlyContinue) {
            $global:PSNativeCommandUseErrorActionPreference = $oldNativeCommandErrorPreference
        }
        if (Test-Path $tempXml) {
            Remove-Item -LiteralPath $tempXml -Force
        }
    }
}

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Runs every 5 minutes from 6:30 AM to 1:00 PM local time, then runs one daily evaluation at 1:05 PM."
Write-Host "Overlapping triggers are ignored while a previous run is active, so the task should not remain queued."
