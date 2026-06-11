# 一键运行（需已安装 playwright chromium）
Set-Location $PSScriptRoot
python -m pip install -q playwright pandas
python -m playwright install chromium
python crawl_xhs.py @args
