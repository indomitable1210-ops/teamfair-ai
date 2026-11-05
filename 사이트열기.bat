@echo off
chcp 65001 >nul
cd /d %~dp0
echo 팀플 서약 서버를 시작합니다... 브라우저가 자동으로 열립니다.
echo 끄려면 이 창을 닫으세요.
python -m streamlit run app.py --server.port 8501
pause
