@echo off
cd /d D:\mrhbench-local-pilot\factory-v5-driver
set PYTHONPATH=C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark;D:/mrhbench-local-pilot/factory-v5-driver
D:\mrhbench-local-pilot\controller-venv\Scripts\python.exe -X utf8 -u newpapers_v82.py >> D:\mrhbench-local-pilot\factory-v8_2\newpapers-v82.log 2>&1
echo done > D:\mrhbench-local-pilot\factory-v8_2\newpapers-v82.done
