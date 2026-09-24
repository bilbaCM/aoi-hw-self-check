@echo off
setlocal

rem Windows 콘솔 코드페이지를 UTF-8로 전환 (한글 안내문 깨짐 방지)
chcp 65001 >nul

rem 창 제목을 프로그램 이름으로 표시
title AOI H/W Self-Check 자동화 프로그램

rem 이 배치 파일이 있는 폴더(저장소 루트)로 이동 — 어디서 더블클릭해도 동작하도록
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [오류] Python을 찾을 수 없습니다.
    echo https://www.python.org/downloads/ 에서 설치 시 "Add python.exe to PATH"를 반드시 체크하세요.
    pause
    exit /b 1
)

set /p EQUIPMENT_ID="설비 ID를 입력하세요 (엔터만 누르면 EQ01): "
if "%EQUIPMENT_ID%"=="" set EQUIPMENT_ID=EQ01

python -m aoi_hw_check.cli run-all --equipment-id %EQUIPMENT_ID% --seed-example-criteria --supervised

echo.
echo ================================================
echo 실행이 끝났습니다. 위 결과를 확인하세요.
echo   - [FAIL]/[NA] 항목은 "조치 대상 목록"에도 정리되어 있습니다.
echo   - 위험 출력(I/O Check)은 작업자 승인 전까지 NA로 남는 게 정상입니다.
echo   - 이번 실행 결과는 reports 폴더에 로그 파일로도 저장되었습니다.
echo ================================================
pause
