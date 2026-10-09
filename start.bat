@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title Trendyol AI
color 0A

REM Script'in bulundugu dizini al (start.bat'in calistigi yer)
set "BAT_DIR=%~dp0"
REM Sonundaki \ karakterini kaldir
set "BAT_DIR=%BAT_DIR:~0,-1%"
cd /d "%BAT_DIR%"

REM Debug: BAT_DIR degerini goster (test icin)
REM echo [DEBUG] BAT_DIR: %BAT_DIR%

echo.
echo ========================================
echo   Trendyol AI Satici Asistani
echo   Proje Baslatiliyor...
echo ========================================
echo.

echo [1/6] Python kontrol ediliyor...
py --version >nul 2>&1
if errorlevel 1 (
    python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [HATA] Python bulunamadi!
        echo Python'u https://www.python.org/downloads/ adresinden indirip kurun.
        echo.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
) else (
    set "PYTHON_CMD=py"
)
echo [OK] Python bulundu

echo [2/6] Node.js kontrol ediliyor...
node --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [HATA] Node.js bulunamadi!
    echo Node.js'i https://nodejs.org/ adresinden indirip kurun.
    echo.
    pause
    exit /b 1
)
echo [OK] Node.js bulundu

echo [3/6] Backend bagimliliklari kontrol ediliyor...
if not exist "backend\venv\" (
    echo [BILGI] Python virtual environment olusturuluyor...
    cd backend
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        cd ..
        echo.
        echo [HATA] Virtual environment olusturulamadi!
        echo.
        pause
        exit /b 1
    )
    cd ..
    echo [OK] Virtual environment olusturuldu
) else (
    echo [OK] Virtual environment zaten mevcut
)

REM Virtual environment'in Python executable'ini test et
set "VENV_PYTHON=backend\venv\Scripts\python.exe"
set "VENV_RECREATED=0"
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" --version >nul 2>&1
    if errorlevel 1 (
        echo [UYARI] Virtual environment'in Python executable'i calismiyor!
        echo [BILGI] Virtual environment yeniden olusturuluyor...
        echo [BILGI] Eski venv siliniyor...
        rmdir /s /q backend\venv 2>nul
        cd backend
        echo [BILGI] Yeni venv olusturuluyor...
        %PYTHON_CMD% -m venv venv
        if errorlevel 1 (
            cd ..
            echo.
            echo [HATA] Virtual environment olusturulamadi!
            echo.
            pause
            exit /b 1
        )
        cd ..
        echo [OK] Virtual environment yeniden olusturuldu
        set "VENV_RECREATED=1"
    )
)

if not exist "backend\venv\Scripts\python.exe" (
    echo.
    echo [HATA] Virtual environment duzgun olusturulamadi!
    echo backend\venv klasorunu silip tekrar deneyin.
    echo.
    pause
    exit /b 1
)

if not exist "backend\venv\Lib\site-packages\fastapi" (
    if "%VENV_RECREATED%"=="1" (
        echo [BILGI] Venv yeniden olusturuldugu icin bagimliliklari yeniden yukleniyor...
    ) else (
        echo [BILGI] Backend bagimliliklari yukleniyor...
    )
    echo [BILGI] Bu islem 5-10 dakika surebilir...
    cd backend
    venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel --quiet
    venv\Scripts\python.exe -m pip install --prefer-binary pydantic pandas numpy scikit-learn
    venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        cd ..
        echo.
        echo [HATA] Bagimliliklari yuklenemedi!
        echo Internet baglantinizi kontrol edin.
        echo.
        pause
        exit /b 1
    )
    cd ..
    echo [OK] Backend bagimliliklari yuklendi
) else (
    echo [OK] Backend bagimliliklari zaten yuklu
)

echo [4/6] Frontend bagimliliklari kontrol ediliyor...
if not exist "frontend\node_modules\" (
    echo [BILGI] Frontend bagimliliklari yukleniyor...
    echo [BILGI] Bu islem 5-10 dakika surebilir...
    cd frontend
    call npm install
    if errorlevel 1 (
        cd ..
        echo.
        echo [HATA] Frontend bagimliliklari yuklenemedi!
        echo Internet baglantinizi kontrol edin.
        echo.
        pause
        exit /b 1
    )
    cd ..
    echo [OK] Frontend bagimliliklari yuklendi
) else (
    echo [OK] Frontend bagimliliklari zaten yuklu
)

if not exist "backend\.env" (
    echo [UYARI] .env dosyasi bulunamadi!
    if exist "backend\env.example" (
        echo [BILGI] env.example dosyasindan .env olusturuluyor...
        copy "backend\env.example" "backend\.env" >nul
        echo [UYARI] backend\.env dosyasini duzenleyip Trendyol API bilgilerinizi girin!
        timeout /t 3 >nul
    ) else (
        echo [UYARI] env.example dosyasi da bulunamadi!
        echo backend\.env dosyasini manuel olarak olusturun.
        timeout /t 3 >nul
    )
)

echo [5/6] Database baslatiliyor...
cd backend
venv\Scripts\python.exe -c "from database.db import init_db; init_db()" >nul 2>&1
if errorlevel 1 (
    echo [UYARI] Database baslatilamadi, backend baslatilirken otomatik baslatilacak
) else (
    echo [OK] Database baslatildi
)
cd ..

echo.
echo [6/6] Serverler baslatiliyor...
echo.
echo ========================================
echo   Backend: http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
echo ========================================
echo.

REM Bilgisayarin IP adresini bul
set "LOCAL_IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set "TEMP_IP=%%a"
    set "TEMP_IP=!TEMP_IP:~1!"
    echo !TEMP_IP! | findstr /r "^192\.168\." >nul && (
        if not defined LOCAL_IP set "LOCAL_IP=!TEMP_IP!"
    )
    echo !TEMP_IP! | findstr /r "^10\." >nul && (
        if not defined LOCAL_IP set "LOCAL_IP=!TEMP_IP!"
    )
    echo !TEMP_IP! | findstr /r "^172\." >nul && (
        if not defined LOCAL_IP set "LOCAL_IP=!TEMP_IP!"
    )
)
if not defined LOCAL_IP (
    for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
        set "LOCAL_IP=%%a"
        set "LOCAL_IP=!LOCAL_IP:~1!"
        goto :ip_found
    )
)
:ip_found
if not defined LOCAL_IP set "LOCAL_IP=localhost"

REM Backend'i baslat (manuel calisan komut)
echo [BILGI] Backend baslatiliyor...
if exist "%BAT_DIR%\backend\venv\Scripts\python.exe" (
    REM Backend klasorunu calisma dizini yaparak uvicorn'u baslat
    start "" /B /D "%BAT_DIR%\backend" "%BAT_DIR%\backend\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
) else (
    echo [HATA] Backend Python bulunamadi!
    echo %BAT_DIR%\backend\venv\Scripts\python.exe
    pause
    exit /b 1
)

REM Kisa bekleme
timeout /t 3 >nul

REM Frontend'i baslat (manuel calisan komut)
echo [BILGI] Frontend baslatiliyor...
REM Frontend klasorunu calisma dizini yaparak npm'i baslat
start "" /B /D "%BAT_DIR%\frontend" cmd /c npm run dev

echo.
echo [BILGI] Frontend'in baslamasi bekleniyor...
timeout /t 5 >nul

echo [BILGI] Tarayici aciliyor...
start http://localhost:3000

echo.
echo ========================================
echo   Proje baslatildi!
echo ========================================
echo.
echo Backend ve Frontend arka planda calisiyor.
echo Tarayici otomatik olarak acildi.
echo.
echo ========================================
echo   ERISIM ADRESLERI:
echo ========================================
echo   Bilgisayardan:
echo   - Frontend: http://localhost:3000
echo   - Backend:  http://localhost:8000
echo.
echo   Telefondan (Ayni WiFi aginda):
if not "%LOCAL_IP%"=="localhost" (
    echo   - Frontend: http://%LOCAL_IP%:3000
    echo   - Backend:  http://%LOCAL_IP%:8000
) else (
    echo   - IP adresi bulunamadi!
    echo   - Manuel olarak IP adresinizi bulun:
    echo     ipconfig komutunu calistirin
)
echo.
echo   NOT: Telefon ve bilgisayar ayni WiFi
echo   aginda olmalidir!
echo   Windows Firewall portlari acik olmalidir!
echo.
echo ========================================
echo   Durdurmak icin bir tusa basin...
echo ========================================
echo.

pause >nul

echo.
echo [BILGI] Serverler durduruluyor...

REM Backend process'lerini kapat
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

REM Frontend process'lerini kapat
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1

echo [OK] Serverler durduruldu.
echo.
timeout /t 2 >nul
