@echo off
chcp 65001 >nul
title Test - Trendyol AI Satıcı Asistanı
color 0E

echo.
echo ========================================
echo   TEST MODU
echo   Hata mesajlarını görmek için
echo ========================================
echo.

REM Script'in çalıştığı dizini al
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo Mevcut dizin: %CD%
echo.

REM Python kontrolü
echo [TEST] Python kontrol ediliyor...
py --version
if errorlevel 1 (
    echo [HATA] Python bulunamadı!
    pause
    exit /b 1
) else (
    echo [OK] Python bulundu
)

echo.
REM Node.js kontrolü
echo [TEST] Node.js kontrol ediliyor...
node --version
if errorlevel 1 (
    echo [HATA] Node.js bulunamadı!
    pause
    exit /b 1
) else (
    echo [OK] Node.js bulundu
)

echo.
REM Backend klasörü kontrolü
echo [TEST] Backend klasörü kontrol ediliyor...
if exist "backend\" (
    echo [OK] Backend klasörü bulundu
) else (
    echo [HATA] Backend klasörü bulunamadı!
    pause
    exit /b 1
)

echo.
REM Frontend klasörü kontrolü
echo [TEST] Frontend klasörü kontrol ediliyor...
if exist "frontend\" (
    echo [OK] Frontend klasörü bulundu
) else (
    echo [HATA] Frontend klasörü bulunamadı!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Tüm kontroller tamamlandı!
echo ========================================
echo.
echo start.bat dosyasını çalıştırabilirsiniz.
echo.
pause










