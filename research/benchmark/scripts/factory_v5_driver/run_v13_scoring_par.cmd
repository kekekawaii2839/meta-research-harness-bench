@echo off
cd /d D:\mrhbench-local-pilot\factory-v5-driver
set PYTHONPATH=C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark;D:/mrhbench-local-pilot/factory-v5-driver
echo === run (parallel x2) %DATE% %TIME% >> D:\mrhbench-local-pilot\v13-scoring.log
D:\mrhbench-local-pilot\controller-venv\Scripts\python.exe -X utf8 -u run_v13_scoring_par.py >> D:\mrhbench-local-pilot\v13-scoring.log 2>&1
echo done > D:\mrhbench-local-pilot\v13-scoring.done
