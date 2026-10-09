# Trendyol AI Satıcı Asistanı - Başlatma Scripti
# PowerShell versiyonu (daha gelişmiş özellikler)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Trendyol AI Satıcı Asistanı" -ForegroundColor Yellow
Write-Host "  Proje Başlatılıyor..." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Python kontrolü
Write-Host "[1/5] Python kontrol ediliyor..." -ForegroundColor Yellow
try {
    $pythonVersion = py --version 2>&1
    Write-Host "[OK] Python bulundu: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[HATA] Python bulunamadı!" -ForegroundColor Red
    Write-Host "Python'u https://www.python.org/downloads/ adresinden indirip kurun." -ForegroundColor Yellow
    Read-Host "Devam etmek için Enter'a basın"
    exit 1
}

# Node.js kontrolü
Write-Host "[2/5] Node.js kontrol ediliyor..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "[OK] Node.js bulundu: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[HATA] Node.js bulunamadı!" -ForegroundColor Red
    Write-Host "Node.js'i https://nodejs.org/ adresinden indirip kurun." -ForegroundColor Yellow
    Read-Host "Devam etmek için Enter'a basın"
    exit 1
}

# Backend dependencies kontrolü
Write-Host "[3/5] Backend bağımlılıkları kontrol ediliyor..." -ForegroundColor Yellow
$backendPath = Join-Path $PSScriptRoot "backend"
$venvPath = Join-Path $backendPath "venv"

if (-not (Test-Path $venvPath)) {
    Write-Host "[BILGI] Python virtual environment oluşturuluyor..." -ForegroundColor Cyan
    Set-Location $backendPath
    py -m venv venv
    Set-Location $PSScriptRoot
}

$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Host "[HATA] Virtual environment oluşturulamadı!" -ForegroundColor Red
    Read-Host "Devam etmek için Enter'a basın"
    exit 1
}

# Backend dependencies yükleme
$fastapiInstalled = Test-Path (Join-Path $venvPath "Lib\site-packages\fastapi")
if (-not $fastapiInstalled) {
    Write-Host "[BILGI] Backend bağımlılıkları yükleniyor (ilk kez çalıştırma)..." -ForegroundColor Cyan
    Set-Location $backendPath
    & "$venvPath\Scripts\python.exe" -m pip install -r requirements.txt --quiet
    Set-Location $PSScriptRoot
}

# Frontend dependencies kontrolü
Write-Host "[4/5] Frontend bağımlılıkları kontrol ediliyor..." -ForegroundColor Yellow
$frontendPath = Join-Path $PSScriptRoot "frontend"
$nodeModulesPath = Join-Path $frontendPath "node_modules"

if (-not (Test-Path $nodeModulesPath)) {
    Write-Host "[BILGI] Frontend bağımlılıkları yükleniyor (ilk kez çalıştırma)..." -ForegroundColor Cyan
    Set-Location $frontendPath
    npm install
    Set-Location $PSScriptRoot
}

# .env dosyası kontrolü
$envPath = Join-Path $backendPath ".env"
$envExamplePath = Join-Path $backendPath "env.example"

if (-not (Test-Path $envPath)) {
    Write-Host "[UYARI] .env dosyası bulunamadı!" -ForegroundColor Yellow
    if (Test-Path $envExamplePath) {
        Write-Host "[BILGI] env.example dosyasından .env oluşturuluyor..." -ForegroundColor Cyan
        Copy-Item $envExamplePath $envPath
        Write-Host "[UYARI] Lütfen backend\.env dosyasını düzenleyip Trendyol API bilgilerinizi girin!" -ForegroundColor Yellow
        Start-Sleep -Seconds 3
    }
}

# Backend başlatma
Write-Host "[5/5] Serverler başlatılıyor..." -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Backend: http://localhost:8000" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[BILGI] Serverler yeni pencerelerde açılacak..." -ForegroundColor Cyan
Write-Host ""

# Backend'i yeni pencerede başlat
$backendScript = @"
cd `"$backendPath`"
& `"$venvPath\Scripts\python.exe`" -m uvicorn main:app --reload
pause
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendScript -WindowStyle Normal

# Kısa bir bekleme
Start-Sleep -Seconds 2

# Frontend'i yeni pencerede başlat
$frontendScript = @"
cd `"$frontendPath`"
npm run dev
pause
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendScript -WindowStyle Normal

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Proje başlatıldı!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend ve Frontend yeni pencerelerde açıldı." -ForegroundColor Cyan
Write-Host "Tarayıcınızda http://localhost:3000 adresini açın." -ForegroundColor Cyan
Write-Host ""
Write-Host "Durdurmak için Backend ve Frontend pencerelerinde Ctrl+C yapın." -ForegroundColor Yellow
Write-Host ""
Read-Host "Bu pencereyi kapatmak için Enter'a basın"










