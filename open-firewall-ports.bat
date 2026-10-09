@echo off
chcp 65001 >nul 2>&1
title Firewall Port Acma
color 0B

echo.
echo ========================================
echo   Windows Firewall Port Acma
echo ========================================
echo.
echo Bu script, Trendyol AI uygulamasinin
echo telefondan erisilebilmesi icin gerekli
echo portlari Windows Firewall'da acar.
echo.
echo Acilacak portlar:
echo   - Port 3000 (Frontend)
echo   - Port 8000 (Backend)
echo.
echo Devam etmek icin bir tusa basin...
pause >nul

echo.
echo [BILGI] Portlar aciliyor...

REM Port 3000'i ac (Frontend)
netsh advfirewall firewall add rule name="Trendyol Frontend" dir=in action=allow protocol=TCP localport=3000 >nul 2>&1
if errorlevel 1 (
    echo [HATA] Port 3000 acilamadi! Yonetici yetkisi gerekebilir.
) else (
    echo [OK] Port 3000 (Frontend) acildi
)

REM Port 8000'i ac (Backend)
netsh advfirewall firewall add rule name="Trendyol Backend" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
if errorlevel 1 (
    echo [HATA] Port 8000 acilamadi! Yonetici yetkisi gerekebilir.
) else (
    echo [OK] Port 8000 (Backend) acildi
)

echo.
echo ========================================
echo   Islem tamamlandi!
echo ========================================
echo.
echo NOT: Eger hata aldiysaniz, bu scripti
echo Yonetici olarak calistirin (Sag tik - 
echo Yonetici olarak calistir)
echo.
pause


