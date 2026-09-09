# Claude/Codex Session PIP - installer
# Creates Desktop + Startup shortcuts and launches the widget.
$ErrorActionPreference = "Stop"
$dir = Split-Path $PSScriptRoot          # 저장소 루트 (scripts/ 상위)
$entry = Join-Path $dir "src\pip_widget.py"

if (-not (Test-Path $entry)) {
    Write-Host "[!] src\pip_widget.py not found. Run this from inside the extracted folder." -ForegroundColor Red
    exit 1
}

# Find pythonw.exe (runs without a console window)
$pyw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pyw) {
    $py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if ($py) { $pyw = Join-Path (Split-Path $py) "pythonw.exe" }
}
if (-not $pyw -or -not (Test-Path $pyw)) {
    Write-Host "[!] Python (pythonw.exe) not found." -ForegroundColor Red
    Write-Host "    Install Python 3.x from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "    and check 'Add Python to PATH', then run this again." -ForegroundColor Yellow
    exit 1
}

function New-WidgetShortcut($lnkPath) {
    $ws = New-Object -ComObject WScript.Shell
    $s = $ws.CreateShortcut($lnkPath)
    $s.TargetPath = $pyw
    $s.Arguments = "src\pip_widget.py"
    $s.WorkingDirectory = $dir
    $s.WindowStyle = 7
    $s.IconLocation = "$pyw,0"
    $s.Description = "Claude Session PIP"
    $s.Save()
}

$desktop = [Environment]::GetFolderPath('Desktop')
$startup = [Environment]::GetFolderPath('Startup')
New-WidgetShortcut (Join-Path $desktop "Claude Session PIP.lnk")
New-WidgetShortcut (Join-Path $startup "Claude Session PIP.lnk")
Write-Host "[OK] Desktop icon + auto-start (on login) created." -ForegroundColor Green

# Stop any existing instance, then launch
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*pip_widget.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 500
Start-Process $pyw -ArgumentList "src\pip_widget.py" -WorkingDirectory $dir
Write-Host "[OK] Widget launched. Check the bottom-right of your screen." -ForegroundColor Green
Write-Host ""
Write-Host "Drag to move / Right-click: provider, opacity, fairy toggle, quit." -ForegroundColor Cyan
