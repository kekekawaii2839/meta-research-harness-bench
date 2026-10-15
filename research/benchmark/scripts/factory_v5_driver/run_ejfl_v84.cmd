@echo off
cd /d D:\mrhbench-local-pilot\factory-v5-driver
set PYTHONPATH=C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark;D:/mrhbench-local-pilot/factory-v5-driver
echo === start %DATE% %TIME% >> D:\mrhbench-local-pilot\factory-v8_4\ejfl-v84.log
D:\mrhbench-local-pilot\controller-venv\Scripts\python.exe -X utf8 -u factory_v8_4.py run --root D:/mrhbench-local-pilot/factory-v8_4 --papers iclr2025-EJfLvrzh2Q --units IDEA --stages units,frame,construct,probe,leak_judge,review_adjudication,reframe,repair,probe2,leak_judge2,repair_adjudication,runtime,compile --max-calls 15 --retry-platform >> D:\mrhbench-local-pilot\factory-v8_4\ejfl-v84.log 2>&1
echo done > D:\mrhbench-local-pilot\factory-v8_4\ejfl-v84.done
