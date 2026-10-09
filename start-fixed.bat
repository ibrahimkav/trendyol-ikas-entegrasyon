@echo off
chcp 65001 >nul
title Trendyol AI Satıcı Asistanı
color 0A

REM Script'in çalıştığı dizini al
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo.
echo ========================================
echo   Trendyol AI Satıcı Asistanı
echo   Proje Başlatılıyor...
echo ========================================
echo.

REM Python kontrolü
echo [1/5] Python kontrol ediliyor...
py --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadı!
    echo Python'u https://www.python.org/downloads/ adresinden indirip kurun.
    echo Kurulum sırasında "Add Python to PATH" seçeneğini işaretleyin.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('py --version') do set PYTHON_VERSION=%%i
echo [OK] Python bulundu: %PYTHON_VERSION%

REM Node.js kontrolü
echo [2/5] Node.js kontrol ediliyor...
node --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Node.js bulunamadı!
    echo Node.js'i https://nodejs.org/ adresinden indirip kurun.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo [OK] Node.js bulundu: %NODE_VERSION%

REM Backend dependencies kontrolü
echo [3/5] Backend bağımlılıkları kontrol ediliyor...
if not exist "backend\venv\" (
    echo [BILGI] Python virtual environment oluşturuluyor...
    echo [BILGI] Bu işlem birkaç dakika sürebilir...
    cd backend
    py -m venv venv
    if errorlevel 1 (
        echo [HATA] Virtual environment oluşturulamadı!
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo [OK] Virtual environment oluşturuldu
)

if not exist "backend\venv\Scripts\python.exe" (
    echo [HATA] Virtual environment düzgün oluşturulamadı!
    echo [BILGI] backend\venv klasörünü silip tekrar deneyin.
    pause
    exit /b 1
)

REM Backend dependencies yükleme
if not exist "backend\venv\Lib\site-packages\fastapi" (
    echo [BILGI] Backend bağımlılıkları yükleniyor (ilk kez çalıştırma)...
    echo [BILGI] Bu işlem 5-10 dakika sürebilir, lütfen bekleyin...
    cd backend
    if not exist "venv\Scripts\python.exe" (
        echo [HATA] Virtual environment Python bulunamadı!
        cd ..
        pause
        exit /b 1
    )
    venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [HATA] Bağımlılıklar yüklenemedi!
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo [OK] Backend bağımlılıkları yüklendi
) else (
    echo [OK] Backend bağımlılıkları zaten yüklü
)

REM Frontend dependencies kontrolü
echo [4/5] Frontend bağımlılıkları kontrol ediliyor...
if not exist "frontend\node_modules\" (
    echo [BILGI] Frontend bağımlılıkları yükleniyor (ilk kez çalıştırma)...
    echo [BILGI] Bu işlem 5-10 dakika sürebilir, lütfen bekleyin...
    cd frontend
    call npm install
    if errorlevel 1 (
        echo [HATA] Frontend bağımlılıkları yüklenemedi!
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo [OK] Frontend bağımlılıkları yüklendi
) else (
    echo [OK] Frontend bağımlılıkları zaten yüklü
)

REM .env dosyası kontrolü
if not exist "backend\.env" (
    echo [UYARI] .env dosyası bulunamadı!
    if exist "backend\env.example" (
        echo [BILGI] env.example dosyasından .env oluşturuluyor...
        copy "backend\env.example" "backend\.env" >nul
        echo [UYARI] Lütfen backend\.env dosyasını düzenleyip Trendyol API bilgilerinizi girin!
        timeout /t 3 >nul
    ) else (
        echo [UYARI] env.example dosyası da bulunamadı!
        echo [BILGI] backend\.env dosyasını manuel olarak oluşturun.
        timeout /t 3 >nul
    )
)

REM Backend başlatma
echo [5/5] Serverler başlatılıyor...
echo.
echo ========================================
echo   Backend: http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
echo ========================================
echo.
echo [BILGI] Serverler yeni pencerelerde açılacak...
echo [BILGI] Bu pencereyi kapatmayın!
echo.

REM Backend'i yeni pencerede başlat
cd backend
if exist "venv\Scripts\python.exe" (
    start "Trendyol Backend" cmd /k "cd /d %SCRIPT_DIR%backend && venv\Scripts\python.exe -m uvicorn main:app --reload"
) else (
    start "Trendyol Backend" cmd /k "cd /d %SCRIPT_DIR%backend && py -m uvicorn main:app --reload"
)
cd ..

REM Kısa bir bekleme
timeout /t 3 >nul

REM Frontend'i yeni pencerede başlat
cd frontend
start "Trendyol Frontend" cmd /k "cd /d %SCRIPT_DIR%frontend && npm run dev"
cd ..

echo.
echo ========================================
echo   Proje başlatıldı!
echo ========================================
echo.
echo Backend ve Frontend yeni pencerelerde açıldı.
echo Tarayıcınızda http://localhost:3000 adresini açın.
echo.
echo Durdurmak için Backend ve Frontend pencerelerinde Ctrl+C yapın.
echo.
pause







