# Claude Session PIP - uninstaller
# Stops the widget and removes Desktop/Startup shortcuts (keeps the source folder).
$desktop = [Environment]::GetFolderPath('Desktop')
$startup = [Environment]::GetFolderPath('Startup')

foreach ($p in @((Join-Path $desktop "Claude Session PIP.lnk"),
                 (Join-Path $startup "Claude Session PIP.lnk"))) {
    if (Test-Path $p) { Remove-Item $p -Force; Write-Host "removed: $p" -ForegroundColor Yellow }
}

# Only stop pythonw started from pip_widget.py (leaves other Python processes alone)
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*pip_widget.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "[OK] Uninstalled. (Source folder was not deleted.)" -ForegroundColor Green
