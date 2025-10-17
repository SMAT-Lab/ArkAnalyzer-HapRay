@echo off
setlocal

set "result_dir=opt_results"
set "base=binary_analysis_report"
set "ext=.xlsx"

cd %~dp0
cd %result_dir%
echo %~dp0

set "count=0"
:loop
:: Generate candidate filename
call set "candidate=%base%%%count%%%ext%"
echo %candidate%
:: Check if file exists
if not exist "%candidate%" (goto outer)
:: Increment counter and loop
set /a count+=1
goto loop
:outer
echo %candidate%
set "welcome_msg=Simple GUI interface for optimization tool. For more fine-grained control, please use the command line (instructions in README.md)"
start cmd /c "echo %welcome_msg% & cd %~dp0 & .\.venv\Scripts\python.exe -Wignore -m scripts.main opt -i %1 -o %result_dir%\%candidate% -j4 3> warning.log & pause"
:: (for /L %%a in (1,1,10) do echo %%a)