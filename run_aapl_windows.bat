@echo off
setlocal
cd /d "%~dp0"
echo.
echo ===============================================
echo  Experiment 4: Historical AAPL Order-Book Replay
echo ===============================================
echo.
echo This downloads the 2012 LOBSTER AAPL sample locally (if available),
echo then generates actual historical trade markouts and HYPOTHETICAL quotes.
echo.
python aapl_replay.py --download --output results\aapl
if errorlevel 1 (
  echo.
  echo Replay could not finish. Read AAPL_HISTORICAL_STUDY.md for data download help.
  echo.
  pause
  exit /b 1
)
echo.
echo Results saved to results\aapl
if exist "results\aapl\hypothetical_pnl.png" (
  start "" "results\aapl\hypothetical_pnl.png"
)
echo.
echo IMPORTANT: Hypothetical quote fills are NOT actual historical executions.
pause
