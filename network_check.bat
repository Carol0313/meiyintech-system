@echo off
chcp 65001 >nul
echo ==========================================
echo   网络连通性排查工具
echo ==========================================
echo.

echo 【1/3】本机IP信息：
ipconfig | findstr /i "IPv4"
echo.

echo 【2/3】端口8000监听状态：
netstat -ano | findstr :8000
echo.

echo 【3/3】防火墙规则：
netsh advfirewall firewall show rule name="制版系统内测"
echo.

echo ==========================================
echo 如果以上都正常，请让同事做以下测试：
echo.
echo   1. 让同事按 Win+R，输入 cmd
echo   2. 输入：ping 192.168.0.141
echo   3. 看是否显示"已接收=4"或"Reply from..."
echo.
echo   如果ping不通 =^> 不在同一个网络
echo   如果ping得通但网页打不开 =^> 可能是其他防火墙/安全软件拦截
echo ==========================================
pause
