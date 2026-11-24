@echo off
cd /d "%~dp0"
echo ==============================================
echo AAPL multi-day chronological holdout experiment
echo ==============================================
echo.
echo You must supply 12+ DISTINCT licensed AAPL Level-5 LOBSTER ZIP dates.
echo Recommended: 30 to 60 dates.
echo Put the ZIP files into data\aapl_days.
echo The free 2012-06-21 sample alone is NOT sufficient.
echo.
if not exist "data\aapl_days\*.zip" (
 echo No data ZIPs found under data\aapl_days.
 echo See MULTI_DAY_DATA_GUIDE.md before spending money.
 pause
 exit /b 1
)
python multi_day_research.py --data-dir data\aapl_days --output results\multi_day
if errorlevel 1 (
 echo Multi-day run did not complete. Please review the error above.
 pause
 exit /b 1
)
echo.
echo Summary available in results\multi_day\holdout_robustness.csv.
if exist "results\multi_day\holdout_robustness.csv" start "" "results\multi_day\holdout_robustness.csv"
pause
