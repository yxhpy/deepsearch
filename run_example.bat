@echo off
chcp 65001 >nul
echo ====================================
echo 网站发现系统 - 示例运行脚本
echo ====================================
echo.

echo 1. 检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo ❌ 未找到Python，请先安装Python 3.10+
    pause
    exit /b 1
)

echo.
echo 2. 安装依赖包...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ❌ 依赖安装失败
    pause
    exit /b 1
)

echo.
echo 3. 检查环境配置...
if not exist .env (
    echo ⚠️  未找到.env文件，复制示例文件...
    copy .env.example .env
    echo 💡 请编辑 .env 文件，填写API密钥后重新运行
    pause
    exit /b 1
)

echo.
echo 4. 运行系统测试...
python test_system.py
echo.

echo 5. 选择运行示例：
echo    [1] Python机器学习教程
echo    [2] React开发指南  
echo    [3] 自定义查询
echo    [4] 退出

set /p choice="请选择 (1-4): "

if "%choice%"=="1" (
    echo.
    echo 🔍 搜索：Python机器学习教程
    python main.py --input "Python机器学习入门教程和最佳实践" --max-queries 30 --verbose
) else if "%choice%"=="2" (
    echo.
    echo 🔍 搜索：React开发指南
    python main.py --input "React开发完整指南和最佳实践" --seeds "https://reactjs.org,https://create-react-app.dev" --max-queries 25
) else if "%choice%"=="3" (
    set /p query="请输入查询内容: "
    set /p seeds="请输入种子网站（可选，用逗号分隔）: "
    echo.
    echo 🔍 执行自定义查询...
    if "%seeds%"=="" (
        python main.py --input "%query%" --verbose
    ) else (
        python main.py --input "%query%" --seeds "%seeds%" --verbose
    )
) else (
    echo 👋 再见！
    exit /b 0
)

echo.
echo ✅ 任务完成！
echo 📄 请查看生成的Excel和CSV报告文件
pause