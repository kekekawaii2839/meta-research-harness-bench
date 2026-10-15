@echo off
cd /d D:\mrhbench-local-pilot\factory-v5-driver
set PYTHONPATH=C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark;D:/mrhbench-local-pilot/factory-v5-driver
set MRH_FACTORY_ROOT=D:/mrhbench-local-pilot/factory-v8_4
echo === maint 4OaO WRITE_EVIDENCE %DATE% %TIME% >> D:\mrhbench-local-pilot\factory-v8_4\searchset-v13.log
D:\mrhbench-local-pilot\controller-venv\Scripts\python.exe -X utf8 -u maintenance_repair_v6.py run iclr2025-4OaO3GjP7k:WRITE_EVIDENCE >> D:\mrhbench-local-pilot\factory-v8_4\searchset-v13.log 2>&1
echo === maint 4OaO WRITE_CONTENT >> D:\mrhbench-local-pilot\factory-v8_4\searchset-v13.log
D:\mrhbench-local-pilot\controller-venv\Scripts\python.exe -X utf8 -u maintenance_repair_v6.py run iclr2025-4OaO3GjP7k:WRITE_CONTENT >> D:\mrhbench-local-pilot\factory-v8_4\searchset-v13.log 2>&1
echo === rebuild 4OaO IDEA >> D:\mrhbench-local-pilot\factory-v8_4\searchset-v13.log
D:\mrhbench-local-pilot\controller-venv\Scripts\python.exe -X utf8 -u factory_v8_4.py run --root D:/mrhbench-local-pilot/factory-v8_4 --papers iclr2025-4OaO3GjP7k --units IDEA --stages units,frame,construct,probe,leak_judge,review_adjudication,reframe,repair,probe2,leak_judge2,repair_adjudication,runtime,compile --max-calls 16 --retry-platform >> D:\mrhbench-local-pilot\factory-v8_4\searchset-v13.log 2>&1
echo === MAINT-4OAO DONE >> D:\mrhbench-local-pilot\factory-v8_4\searchset-v13.log
echo done > D:\mrhbench-local-pilot\factory-v8_4\searchset-v13.done
