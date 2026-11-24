@echo off
setlocal
cd /d "%~dp0"
echo =============================================================
echo Real multi-day AAPL Nasdaq historical order-book research
echo =============================================================
echo This study streams SEVEN separate official historical Nasdaq
echo ITCH files. Combined downloads can exceed 30 GIGABYTES.
echo They are not stored in the GitHub repository.
echo Requires a stable internet connection and Python 3.10 or newer.
echo Hypothetical fills are NOT real trades.
echo.
set /p CONFIRM=Type YES to download and run all seven real days:
if /I not "%CONFIRM%"=="YES" (
  echo Cancelled.
  pause
  exit /b 1
)
echo.
python -m unittest discover -s tests -v
if errorlevel 1 goto fail
for %%D in (01302019 03272019 07302019 08302019 10302019 12302019 01302020) do (
  echo.
  echo Processing Nasdaq AAPL historical day %%D
  python -u nasdaq_day_replay.py --date %%D --output results\nasdaq_public\%%D
  if errorlevel 1 goto fail
)
python nasdaq_multiday_report.py --results-dir results\nasdaq_public --output results\nasdaq_multi_day
if errorlevel 1 goto fail
echo.
echo Multi-day descriptive results:
echo results\nasdaq_multi_day\multi_day_table.csv
if exist "results\nasdaq_multi_day\multi_day_table.csv" start "" "results\nasdaq_multi_day\multi_day_table.csv"
pause
exit /b 0
:fail
echo.
echo The research run failed; previous successful daily outputs stay on disk.
echo Check the error text above. Do not claim a completed seven-day study.
pause
exit /b 1
