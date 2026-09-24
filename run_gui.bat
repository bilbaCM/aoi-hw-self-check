@echo off
setlocal

rem Windows 콘솔 코드페이지를 UTF-8로 전환 (한글 안내문 깨짐 방지)
chcp 65001 >nul

rem 창 제목을 프로그램 이름으로 표시 (GUI가 뜨기 전까지만 보임)
title AOI H/W Self-Check 자동화 프로그램 (GUI)

rem 이 배치 파일이 있는 폴더(저장소 루트)로 이동 — 어디서 더블클릭해도 동작하도록
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [오류] Python을 찾을 수 없습니다.
    echo https://www.python.org/downloads/ 에서 설치 시 "Add python.exe to PATH"를 반드시 체크하세요.
    pause
    exit /b 1
)

rem pythonw가 있으면 콘솔 창 없이 GUI만 띄운다 (없으면 일반 python으로 대체)
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw -m aoi_hw_check.gui
) else (
    python -m aoi_hw_check.gui
)
