# Сборка BLCL Programmer и выкладка в рабочую папку (Яндекс.Диск).
# Запуск:  powershell -ExecutionPolicy Bypass -File build.ps1
#          powershell -ExecutionPolicy Bypass -File build.ps1 -Force
#
# -Force закрывает работающую программу. По умолчанию скрипт этого НЕ
# делает: программа шьёт платы, и обрыв посреди прошивки может оставить
# плату без рабочего образа.
param([switch]$Force)

$ErrorActionPreference = 'Stop'
$deploy = 'E:\Yandex.Disk\Soft\Programmer'

Set-Location $PSScriptRoot

$running = Get-Process BLCL_Programmer -ErrorAction SilentlyContinue
if ($running) {
    if ($Force) {
        $running | Stop-Process -Force -Confirm:$false
        Start-Sleep -Seconds 2
    } else {
        throw ("Программа запущена (PID: " + ($running.Id -join ', ') +
               "). Закройте её или запустите скрипт с ключом -Force")
    }
}

python -m PyInstaller --noconfirm BLCL_Programmer.spec
if (-not (Test-Path 'dist\BLCL_Programmer.exe')) { throw 'Сборка не удалась' }

# exe и рабочие данные рядом с ним: прошивки, образы FPGA, настройки.
# Внутрь exe зашиты только resources (иконка, документация, projects.json)
# — туда писать нельзя, распаковка временная.
New-Item -ItemType Directory -Force $deploy | Out-Null
Copy-Item 'dist\BLCL_Programmer.exe' $deploy -Force
Copy-Item 'firmware' $deploy -Recurse -Force
Copy-Item 'mcs' $deploy -Recurse -Force

# настройки и список проектов не перетираем: там запомненные пути
# к ST-Link/Vivado/J-Link и добавленные платы
New-Item -ItemType Directory -Force (Join-Path $deploy 'resources') | Out-Null
foreach ($f in 'settings.json', 'settings3.json', 'mcu.json', 'projects.json') {
    $dst = Join-Path $deploy "resources\$f"
    if (-not (Test-Path $dst)) { Copy-Item "resources\$f" $dst -Force }
}

Remove-Item 'build', 'dist' -Recurse -Force -Confirm:$false
Write-Host "Готово: $deploy\BLCL_Programmer.exe обновлён" -ForegroundColor Green
