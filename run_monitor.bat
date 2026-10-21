@echo off
chcp 65001 >nul
title WebCafe AI与工具 付费站商机监控
echo ========================================================
echo   WebCafe AI 与 工具付费站商机监控服务 (免积分新词挖掘)
echo   [已全面过滤游戏与泛资讯 · 只专注卖积分与月度订阅]
echo ========================================================
echo.

:menu
echo --------------------------------------------------------
echo [核心商机查看]
echo 1. 查看【AI与工具】精选商机 (区分新词卖积分 vs 二次爆火做订阅)
echo 2. 打开【AI与工具】付费商机 Excel 表格
echo 3. 打开【纯净版】网页看板 (在浏览器中交互查看)
echo.
echo [后台常驻守护与自动化]
echo 4. 立即同步一次最新批次 (python cli.py sync)
echo 5. 启动常驻后台守护服务 (每30分钟检测，自动推送到飞书)
echo 6. 测试飞书机器人推送 (test-feishu)
echo 7. 退出
echo --------------------------------------------------------
echo.
set /p choice=请输入操作编号 (1-7): 

if "%choice%"=="1" (
    python cli.py ai-tools
    pause
    goto menu
)
if "%choice%"=="2" (
    start data\AI与工具_精选付费商机.csv
    goto menu
)
if "%choice%"=="3" (
    start data\dashboard.html
    goto menu
)
if "%choice%"=="4" (
    python cli.py sync
    pause
    goto menu
)
if "%choice%"=="5" (
    echo.
    echo 正在启动守护监控...
    echo 提示: 如需推送到飞书，请确保在 config.py 中配置了 FEISHU_WEBHOOK_URL
    echo 按 Ctrl+C 可停止运行。
    echo.
    python cli.py daemon --interval 1800
    goto menu
)
if "%choice%"=="6" (
    set /p hook=请输入飞书群机器人 Webhook 地址: 
    python cli.py test-feishu --webhook "%hook%"
    pause
    goto menu
)
if "%choice%"=="7" (
    exit
)

echo 无效输入，请重试。
pause
goto menu
