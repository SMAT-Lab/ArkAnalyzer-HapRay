cd /d %~dp0
cd
REM 设置python解释器路径
set python="python"
%python% -m pip uninstall -y hypium
%python% -m pip uninstall -y xdevice-ohos
%python% -m pip uninstall -y xdevice-devicetest
%python% -m pip uninstall -y xdevice

%python% -m pip install xdevice-5.0.7.200.tar.gz
%python% -m pip install xdevice-devicetest-5.0.7.200.tar.gz
%python% -m pip install xdevice-ohos-5.0.7.200.tar.gz
%python% -m pip install hypium-5.0.7.200.tar.gz
pause