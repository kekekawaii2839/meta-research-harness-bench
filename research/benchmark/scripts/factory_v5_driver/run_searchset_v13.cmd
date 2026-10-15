@echo off
cd /d D:\mrhbench-local-pilot\factory-v5-driver
set PYTHONPATH=C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark;D:/mrhbench-local-pilot/factory-v5-driver
echo === run %DATE% %TIME% >> D:\mrhbench-local-pilot\factory-v8_4\searchset-v13.log
D:\mrhbench-local-pilot\controller-venv\Scripts\python.exe -X utf8 -u searchset_v13_v84.py >> D:\mrhbench-local-pilot\factory-v8_4\searchset-v13.log 2>&1
echo done > D:\mrhbench-local-pilot\factory-v8_4\searchset-v13.done
