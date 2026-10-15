@echo off
cd /d D:\mrhbench-local-pilot\factory-v5-driver
set PYTHONPATH=C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark;D:/mrhbench-local-pilot/factory-v5-driver
echo === start %DATE% %TIME% >> D:\mrhbench-local-pilot\factory-v8_3\kbjj-v83.log
D:\mrhbench-local-pilot\controller-venv\Scripts\python.exe -X utf8 -u factory_v8_3.py run --root D:/mrhbench-local-pilot/factory-v8_3 --papers iclr2025-kbjJ9ZOakb --units LIT,IDEA --stages fetch,source_audit,adjudication,background,repo_files,external_data,area_brief,bg_screen,units,frame,construct,probe,leak_judge,review_adjudication,reframe,repair,probe2,leak_judge2,repair_adjudication,repair2,repair2_adjudication,runtime,compile --max-calls 40 --retry-platform >> D:\mrhbench-local-pilot\factory-v8_3\kbjj-v83.log 2>&1
echo done > D:\mrhbench-local-pilot\factory-v8_3\kbjj-v83.done
