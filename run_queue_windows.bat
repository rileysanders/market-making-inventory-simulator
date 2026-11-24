@echo off
cd /d "%~dp0"
echo ==============================================
echo AAPL historical depth-aware queue experiment
echo ==============================================
echo.
echo Step 1: Verify all Python tests.
python -m unittest discover -s tests -v
if errorlevel 1 (
 echo Tests failed. Read the error above before running the experiment.
 pause
 exit /b 1
)
echo.
echo Step 2: Download official free AAPL 2012-06-21 Level-5 data and replay.
python queue_replay.py --download --output results\queue_replay
if errorlevel 1 (
 echo Replay failed. See QUEUE_RESULTS.md for data-source help.
 pause
 exit /b 1
)
echo.
echo Outputs are in results\queue_replay
echo IMPORTANT: all strategy fills and profits are HYPOTHETICAL.
if exist "results\queue_replay\queue_sensitivity.csv" start "" "results\queue_replay\queue_sensitivity.csv"
pause
