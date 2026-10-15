@echo off
cd /d D:\mrhbench-local-pilot\factory-v5-driver
set PYTHONPATH=C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark;D:/mrhbench-local-pilot/factory-v5-driver
:wait
if not exist D:\mrhbench-local-pilot\p11-v82-oral-s46low.done (timeout /t 30 /nobreak >nul & goto wait)
set R=D:/mrhbench-local-pilot/factory-v8_2/papers
set O=D:/mrhbench-local-pilot/p11-v82-oral-s46low
set ROLES=D:/mrhbench-local-pilot/factory-v5-driver/config/role_transport_sonnet46low_executor.json
set WHY=controller checks.json was not generated for the new factory-v8_2 units before the pilot; generated afterwards with checks/gen_generic_checks.py (zero calls); executor not re-run
for %%T in (iclr2025-Xo0Q1N7CGk:WRITE_CONTENT iclr2025-GMwRl2e9Y1:WRITE_CONTENT iclr2025-kbjJ9ZOakb:WRITE_CONTENT iclr2025-GMwRl2e9Y1:IDEA) do (
  for /f "tokens=1,2 delims=:" %%A in ("%%T") do (
    echo === finish %%A %%B >> D:\mrhbench-local-pilot\p11-v82-oral-finish.log
    D:\mrhbench-local-pilot\controller-venv\Scripts\python.exe -X utf8 -u finish_pilot_judge.py %R%/%%A/units/%%B@release %O%/%%A__%%B %ROLES% "%WHY%" >> D:\mrhbench-local-pilot\p11-v82-oral-finish.log 2>&1
  )
)
echo FINISH DONE >> D:\mrhbench-local-pilot\p11-v82-oral-finish.log
