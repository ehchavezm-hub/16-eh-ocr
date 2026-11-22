@echo off
REM ============================================================================
REM  eh-ocr.cmd - Usar eh-ocr desde la terminal (CMD o PowerShell) o con doble clic
REM
REM  Antes de cada uso trae la ultima version desde GitHub (git pull) y, si
REM  cambiaron las librerias, las reinstala.
REM
REM  Uso (desde la carpeta de eh-ocr, p. ej. C:\09\02 eh-ocr):
REM    eh-ocr                       Abre la ventana        (en PowerShell: .\eh-ocr)
REM    eh-ocr instalar C:\09\paquete  Primera vez: modelos, Tesseract y accesos directos
REM    eh-ocr autoprueba            Prueba rapida sin internet
REM    eh-ocr pruebas               Todas las pruebas automaticas (pytest)
REM    eh-ocr actualizar            Solo git pull + librerias
REM    eh-ocr ayuda                 Esta lista
REM
REM  Para saltarse el git pull una vez:   set EH_OCR_SIN_PULL=1
REM ============================================================================
setlocal
REM Abierto con doble clic: en caso de error la ventana espera para que se lea.
set "DOBLECLIC="
echo %CMDCMDLINE% | find /i "%~nx0" >nul && set "DOBLECLIC=1"
set "RAIZ=%~dp0"
if "%RAIZ:~-1%"=="\" set "RAIZ=%RAIZ:~0,-1%"

if /i "%~1"=="ayuda" goto :Ayuda
if /i "%~1"=="/?" goto :Ayuda

REM ---- 1. Python 3.13 ---------------------------------------------------------
set "PY="
py -3.13 --version >nul 2>&1 && set "PY=py -3.13"
if not defined PY python -c "import sys; sys.exit(sys.version_info[:2] != (3, 13))" >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [ERROR] No se encontro Python 3.13.
    echo         Instalalo desde https://www.python.org/downloads/ y vuelve a intentar.
    if defined DOBLECLIC pause
    exit /b 1
)

REM ---- 2. Actualizar desde GitHub ---------------------------------------------
set "REINSTALAR="
if defined EH_OCR_SIN_PULL goto :Librerias
git --version >nul 2>&1 || (
    echo [AVISO] Git no esta instalado: se usa la version local sin actualizar.
    goto :Librerias
)
if not exist "%RAIZ%\.git" (
    echo [AVISO] Esta carpeta no es un clon de GitHub: se usa la version local.
    goto :Librerias
)
set "ANTES="
for /f %%h in ('git -C "%RAIZ%" rev-parse HEAD') do set "ANTES=%%h"
echo [git] Actualizando desde GitHub...
REM El bloque se lee completo antes de ejecutarse: si git pull cambia este mismo
REM archivo, el script se reinicia con la version nueva en vez de leerla a medias.
(
    git -C "%RAIZ%" pull --ff-only
    if errorlevel 1 (
        echo [AVISO] git pull no se pudo completar ^(sin conexion o cambios locales^).
        echo         Se continua con la version local.
        goto :Librerias
    )
    git -C "%RAIZ%" diff --quiet %ANTES% HEAD -- pyproject.toml desarrollo/requirements-tablas.txt || set "EH_OCR_REINSTALAR=1"
    git -C "%RAIZ%" diff --quiet %ANTES% HEAD -- eh-ocr.cmd || (
        echo [git] eh-ocr.cmd se actualizo. Reiniciando con la version nueva...
        set "EH_OCR_SIN_PULL=1"
        cmd /c ""%~f0" %*"
        exit /b
    )
    goto :Librerias
)

:Librerias
REM ---- 3. Librerias (solo si faltan, cambiaron o vienen de otra carpeta) ------
if defined EH_OCR_REINSTALAR set "REINSTALAR=1"
%PY% -c "import eh_ocr, PySide6, cv2, pikepdf, rapidocr, rapid_table, rapid_layout" >nul 2>&1 || set "REINSTALAR=1"
REM Si Python carga eh_ocr desde otra carpeta (p. ej. D:\PST\eh-ocr), se reinstala desde esta.
%PY% -c "import os,sys,eh_ocr as e; a=os.path.normcase(os.path.abspath(e.__file__)); b=os.path.normcase(os.path.abspath(sys.argv[1])); sys.exit(0 if a.startswith(b) else 1)" "%RAIZ%" >nul 2>&1 || set "REINSTALAR=1"
if not defined REINSTALAR goto :Ejecutar
echo [pip] Instalando librerias ^(la primera vez tarda unos minutos^)...
%PY% -m pip install -q --disable-pip-version-check --no-warn-script-location -e "%RAIZ%"
if errorlevel 1 goto :ErrorPip
REM Las de tablas SIEMPRE sin dependencias (con ellas traen OpenCV completo y ONNX Runtime de CPU).
%PY% -m pip install -q --disable-pip-version-check --no-warn-script-location --no-deps -r "%RAIZ%\desarrollo\requirements-tablas.txt"
if errorlevel 1 goto :ErrorPip
goto :Ejecutar

:ErrorPip
echo [ERROR] No se pudieron instalar las librerias. Revisa el mensaje de pip arriba.
if defined DOBLECLIC pause
exit /b 1

:Ejecutar
REM ---- 4. Ejecutar -----------------------------------------------------------
set "PYTHONPATH=%RAIZ%\src;%PYTHONPATH%"
if "%~1"=="" goto :Ventana
if /i "%~1"=="actualizar" (
    echo [OK] eh-ocr actualizado.
    exit /b 0
)
if /i "%~1"=="instalar" goto :Instalar
if /i "%~1"=="autoprueba" goto :Autoprueba
if /i "%~1"=="pruebas" goto :Pruebas
echo [ERROR] No conozco la orden "%~1".
goto :Ayuda

:Autoprueba
echo [eh-ocr] Probando sin internet...
%PY% -m eh_ocr --autoprueba "%TEMP%\eh-ocr-autoprueba.txt"
set "CODIGO=%errorlevel%"
if exist "%TEMP%\eh-ocr-autoprueba.txt" type "%TEMP%\eh-ocr-autoprueba.txt"
if defined DOBLECLIC pause
exit /b %CODIGO%

:Pruebas
%PY% -c "import pytest" >nul 2>&1 || %PY% -m pip install -q --disable-pip-version-check pytest pyflakes
if exist "%RAIZ%\recursos\tesseract" set "EH_OCR_TESSERACT_INCLUIDO=1"
pushd "%RAIZ%"
%PY% -m pytest -v
set "CODIGO=%errorlevel%"
popd
if defined DOBLECLIC pause
exit /b %CODIGO%

:Instalar
if "%~2"=="" (
    %PY% "%RAIZ%\instalar.py"
) else (
    %PY% "%RAIZ%\instalar.py" "%~2"
)
exit /b

:Ventana
if not exist "%RAIZ%\recursos\modelos" (
    echo [AVISO] Faltan los modelos precisos y Tesseract: eh-ocr funciona, pero con menos precision.
    echo         Instalalos una vez con:  eh-ocr instalar C:\09\paquete
)
echo [eh-ocr] Abriendo la ventana... ^(cierra la ventana para volver a la terminal^)
%PY% -m eh_ocr
if errorlevel 1 (
    echo [ERROR] eh-ocr se cerro con un error. El detalle esta arriba y en datos\error_inicio.txt.
    if defined DOBLECLIC pause
    exit /b 1
)
exit /b 0

:Ayuda
echo.
echo  eh-ocr                         Abre la ventana        (en PowerShell: .\eh-ocr)
echo  eh-ocr instalar C:\09\paquete  Primera vez: modelos, Tesseract y accesos directos
echo  eh-ocr autoprueba              Prueba rapida sin internet
echo  eh-ocr pruebas                 Todas las pruebas automaticas
echo  eh-ocr actualizar              Solo trae la ultima version de GitHub
echo.
exit /b 0
