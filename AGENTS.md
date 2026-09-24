# Meta Research Harness Benchmark：唯一研究方案与工作记忆

更新：2026-09-23。本文是唯一研究协议、待办与工作记忆；代码、结构化材料、原始快照、trace和测试报告是证据，不另立PLAN/STATUS/TODO文档。

## 0. 当前决定、授权与协作规则

### 0.1 现在的研究与工程边界

- **研究对象：** builder构建并演化一个统一AI/ML research harness；主benchmark用固定独立起点测LIT、IDEA、EXP、WRITE（写作两类），不是自然科学题库，也不是一题一套harness。
- **首版CPU-only：** benchmark科研任务不依赖本地GPU；来源论文可以含GPU研究，但只派生CPU环境中科学上成立的任务。WRITE可使用作者已报告结果。不能把GPU研究随意缩水后声称检验原假设。GPU扩展不属于首版完成门槛。
- **包级环境与预算：** 每个材料包在构造时独立配置并验证Docker环境、依赖、CPU/内存/存储/进程数、执行时限、数据/工具/网络权限。统一schema和约束机制，**不统一资源数值**。同一任务对所有模型/harness版本配置相同，不同包允许不同。
- **运行隔离：** 每任务每次运行全新容器和独立可写状态；可复用安全依赖镜像层，但不能复用带科研记忆的运行容器。镜像不含目标答案/同包其他阶段私有材料；按当前TaskView只读发布输入，单独收集产物。Docker本身不是绝对安全保证，挂载、网络、资源和越界必须实测。
- **角色边界：** 材料构造agent可以读原始论文；被测builder、executor不继承维护者上下文。H0不看科研任务，演化仅search；judge可读私有参考，**同次评审生成内部评分和公开feedback，不另设feedback agent**。字段分离不等于语义不泄漏，须专门审核。
- **LIT唯一方案：** R2全局共享背景文献库、自由库内检索，无开放互联网；搜索/摘要/读取统一时间、版本、目标排除。废止R1；固定IDEA背景报告仍合法，不改为实际LIT输出。
- **工程优先级：** 可信调用/包级Docker执行与原生judge优先；小批材料/评分验收后扩展。TTS等归因分析及连续use case不阻塞主benchmark建设。

### 0.2 授权与当前真实状态

| 项目 | 当前状态 |
|---|---|
| Builder/evolver | **2026-09-24用户改定：Claude Code原生agent**（claude-opus-5-5，effort medium，订阅登录）；旧gpt-5.6-sol+Codex记录保留为历史配置，不与新配置混算 |
| Executor | **2026-09-24用户改定：Claude订阅经无原生harness的API式transport**（claude-opus-5-5，medium；`claude -p`关闭全部内置工具/MCP/技能，只返回JSON），替代旧`codex exec`反代；控制循环仍属于被测harness，不用Claude Code原生agent当executor |
| Judge | **2026-09-24改为Claude Code原生agent**（claude-opus-5-5/medium，仅受控MCP取证工具）；以下为旧gpt-5.6-sol+原生Codex历史：同次评分/feedback已实现；v2.8新EXP/WRITE_CONTENT配对留出已实际审阅，目标错误可区分，EXP暴露fixture公开配置identity/反馈归属及非目标维度差异；完整T03仍未通过，旧分数/循环均保留 |
| 材料构造模型 | **2026-09-24用户改定：Claude native runner（constructor角色，opus-5-5/medium）**；以下为旧Luna历史：低消耗模型优先；GPT-6 Luna按2026-09-23所查官方credits速率最便宜，但订阅配额不保证同比例，Luna/medium多轮自主构造仍未通过；维护者另存科学修订并经sol/medium独立审阅，不能把维护者修复算Luna质量通过或冻结批量配置；不改其余已定模型 |
| 调用授权 | 2026-09-24再新增100次Claude调用，总上限**368**（见§0.2.13）；此前：历史基线68次；用户另授权**本轮新增最多200次**（失败计入、不自动购买额度/兑换reset）。账本和development配置已更新为总上限268，不另加旧剩余32次；当前次数以账本为准。研究协议的限轮次与开发调用上限不同 |
| Goal/协作 | 用户已明确恢复goal与并行推进；工具现已核实**active**。本机小批试产，暂不迁移全量、不启动未经确认的正式评测；不声称全TODO完成 |
| 已有交付 | 两篇覆盖五类开发任务的新TaskView/包级容器；18篇R2共享背景库；真实builder H0及五类开发试跑；无正式split/正式任务/科学演化 |
| 既有测试 | 最新290项benchmark离线测试通过；8项来源测试再次通过；177/177 source_cache文件此前对历史登记hash一致；包级CPU压力/边界、模型broker、镜像同机save/load、25MiB产物整链已实测。测试不替代材料语义或judge验收 |
| 未通过关键项 | native正式角色隔离与executor服务边界、judge留出验收、材料自主量产质量/覆盖、真实模型混合演化验收、正式配置与评测；具体演化适配器已实现并测试，不等于真实自演化成功 |

新增200次是独立开发transport调用上限，不含本对话/研究协作subagent的完整系统用量；不得声称覆盖全部订阅消耗。缺失usage不记零，订阅不虚构逐次美元成本。材料批量运行和正式规模参数需依据pilot明确，不能把额度授权当必须用尽或已定正式样本量。

### 0.2.1 本机小批试产与磁盘审计 [决定与重启前历史；当前状态见后文]

- 先在本机构造少量材料包，记录真实磁盘占用后再决定全量在本机还是服务器；暂不迁移全量、不租服务器。实现先复用SSA与IV两篇已保存来源，生成新版本候选，不覆盖旧材料。
- 分别记录原始来源、构造/审核工作目录与材料包、模型轨迹/运行产物、Docker镜像共享层与新增层、构建缓存/卷及宿主剩余空间。报告首个环境基础开销与后续增量，不把各镜像名义大小简单求和；目录逻辑字节、Docker层用量和宿主实际占用不得混称。
- 新增只读测量入口`research/benchmark/measure_local_storage.py`及3项测试；真实初始快照`audit/local_pilot_storage_before.json`记录工作区66,875,651字节、原始来源33,479,571字节（子目录包含于总量，不能相加）。Docker未就绪的用量记null/unavailable，不记零；工作期间数据增长需再次采样，不把初始值当最终包大小。
- 当前检测：Docker CLI已安装，但desktop-linux引擎不可连接，Docker/WSL服务均停止且禁用；C盘约24GiB、D盘约199GiB可用。用户已允许启用所需服务；实际Set-Service被Windows拒绝访问，已请求用户用管理员PowerShell启用。已启动Docker Desktop进程，不代表引擎可用。配置指向`D:/wsl/docker-desktop-data`，既有两份VHDX逻辑长度合计34,158,411,776字节，**不计入本次新增**，真实分配块另测；未迁移、清理数据。具体证据`audit/local_pilot_docker_host_preflight.json`。可并行准备材料、Dockerfile和离线测试，但不能称容器已构建或验收。
- Docker可固定用户态依赖，但不保证任意宿主完全相同：冻结基础镜像digest、平台架构、依赖和包级资源；迁移后复跑环境/数值烟雾测试。实际时间受硬件、内核和虚拟化影响，须记录宿主，不把相同CPU配额当相同性能。
- 原生Codex权限探针69已完成模型调用但本地读写未通过：PowerShell工具被policy拒绝，无目标产物；计为运行平台问题，不当材料构造或H0成功。runtime子任务最多先用4次调用定位，实际状态以独立轨迹与账本为据。
- 后续真实进度：探针70在`--no-daemon`下仍因workspace权限失败；71/72以显式Full access通过开发读写、执行及独立重复检查。**这只解锁维护者材料构造，不证明正式角色/任务隔离**。实际二进制已变为`80f78947ad880e6e/codex.exe`（0.155.0-alpha.16.3），旧路径消失；每次保留hash。JSONL没有完整图像工具事件，不能据一次回答颜色正确通过视觉轨迹验收；新runner已准备按精确session ID保存脱敏rollout，后续仍需逐条审阅。
- 两篇原生构造已在本机D盘独立目录`D:/mrhbench-local-pilot/batch-20260923-001`启动（Luna/medium；调用73、74），不在含全部私有材料的主仓库cwd内运行。完整调用预算仍268。初构两份均被结构门禁拒绝；已区分并修复模板路径歧义与private-only事实空stage列表的schema/validator不一致，并在新目录完成一次显式返修。保留原件，不以材料构造失败计为科研agent能力失败；结果见下一小节。
- 用户启用服务后已复查均Running/Manual；WSL报告当前配置不支持WSL2，Docker仍不可用。用户管理员只读结果确认`VirtualMachinePlatform: Disabled`；未看到hypervisorlaunchtype输出，不擅断Off。已给出启用该组件且`-NoRestart`的命令，当前未获实际执行结果、未重启。容器实测须组件启用并完成所需重启后再做。VHDX现已用Windows分配字节API测量，见`audit/local_pilot_docker_virtualization_check.json`；仍为既有宿主成本。

### 0.2.2 首批试产结果 [历史账本截至78；后续见§0.2.4]

- 两篇论文形成3个候选：IV的CPU EXP、SSA的WRITE_CONTENT/WRITE_EVIDENCE。初构在`D:/mrhbench-local-pilot/batch-20260923-001`；一次显式返修及独立审核在`batch-20260923-002`。每包有独立Dockerfile/依赖/资源候选/外置smoke，未建镜像。新schema尚需接到正式TaskView与execution_budget，不称开箱即用benchmark包。
- 本轮10次调用（69–78）均已结束：4权限探针、4Luna构造/返修、2sol材料审核；账本78/268，本轮剩190。没有正式executor/judge评测或H0构建。当前没有这两批遗留模型运行，可在用户启用组件后安排重启；不自动重启。
- 两份返修结构检查通过，独立评审均`revise`。SSA仍缺规范化层更新/Oracle比较条件，且公开完整renderer提前完成被测可视化任务。IV需补来源条件定位与机器可读结果接口；**不采纳评审要求统一重复次数/网格/迭代数的意见**，这些属于solver应自主设计的实验。未来prompt已纠正此评审越界和WRITE过度辅助，现有候选/评审保持原样。Docker非root/挂载、镜像digest、资源实测及可发布性仍是独立待办。
- 根审计`audit/local_pilot_review_adjudication.json`记录逐项采纳/驳回；已读两份完整review及相关输入/代码/原文，但没有把全部rollout逐字审核冒称完成。75–78真实新调用已捕获精确session的脱敏rollout；完整judge行为验收仍未通过，不能由材料review代替benchmark judge验收。
- 磁盘快照与汇总：`audit/local_pilot_storage_before.json`、`local_pilot_storage_after.json`、`local_pilot_batch_summary.json`。两批D盘工作目录（包含原文副本、初稿、返修、审核副本）合计5,334,645字节≈5.09MiB；主工作区区间增长7,885,935字节≈7.52MiB（主要审计轨迹及工程）；额外Codex原始会话文件5,405,711字节≈5.16MiB，合计观测约17.8MiB。最终两份候选output共43,007字节，已包含在D盘总量中，不能再相加。共享系统日志/数据库/临时文件增量未完整计量。
- **Docker新增镜像/缓存/容器占用尚未测得，不是0**；既有D盘Docker VHDX约31.8GiB不归本次。不能用两份小型文本/数值任务直接推全量磁盘规模。重启后先采daemon基线，再逐包构建测共享基础层与新增量；全量宿主选择仍留待这些实测后讨论。
- 最新离线88项benchmark测试、8项来源测试通过；116原始缓存hash全部未变，constructor与reviewer的候选output副本hash一致。证据为`audit/local_pilot_offline_tests.json`、`local_pilot_original_integrity.json`和汇总；软件测试不替代材料语义或容器验收。

### 0.2.3 重启后的CPU容器实测 [2026-09-23，开发环境通过基础检查]

- 用户确认已重启后实查：`HypervisorPresent=true`，Docker Engine28.5.1 / Desktop4.49.0、WSL2 Linux amd64可连接，cgroup v1。WSL后端当前正常工作，未因com.docker.service显示Stopped就再次要求启用/改服务。
- 已构建两个独立依赖镜像：IV `mrhbench-pilot/iv:860c335d9324`、SSA `mrhbench-pilot/ssa:779fd62fc90a`。公共Python基础镜像固定digest `sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9`，平台linux/amd64；实际image IDs、全部已安装Python依赖和配置已记录。原始model生成包未修改，controller只在新目录锁定FROM。
- 控制器入口`research/benchmark/run_docker_pilot.py`、实现`mrhbench/docker_pilot.py`仅用于**开发环境烟雾测试，不是正式solver runner**。按包启动：IV 2CPU/2GiB RAM/128PIDs/1200s；SSA 1CPU/1GiB RAM/64PIDs/600s。disk_mb暂明确映射为每run可写tmpfs总额（work80%+tmp20%），分别1GiB/512MiB；只读依赖镜像/输入和有界controller日志另计。该语义需后续统一进入正式ResourceSpec，不把镜像大小混进可写配额。
- 首次启动因Docker local日志驱动`max-file=1`与默认压缩不兼容失败，两个旧失败记录保留；修改为2后复用原镜像重新启动。IV的数据生成/OLS/2SLS基础代码、SSA的CSV读取和绘图依赖在CPU容器内实际通过。每次新容器，UID10001、无外部网络接口、只读输入与根目录、全部capability关闭、NoNewPrivs=1均检查；Docker inspect资源配置与各包一致。只发布白名单基线/数据和controller smoke，不挂目标原文、私有包JSON、模型凭据、Docker socket或整个工作区。
- 重复启动未读到上次临时状态；额外2秒合成sleep故障注入确认watchdog超时后杀掉daemon侧容器并清理。该2秒仅测控制器，不改变科研题面的1200/600秒。所有本次临时容器已移除；用户旧镜像、容器和卷未删改。
- 磁盘按共享层去重：公共基础镜像约119.4MB；IV新增独有层约77.5MB、SSA约168.4MB；两包合计镜像层约**365.3MB**（不能相加完整197MB与288MB）。未共享额外build cache报告282B，共享缓存层不再重复计。基础镜像拉取后至两包构建/烟雾测试结束，D盘VHDX分配字节观测增长**320MiB**；这是该区间的宿主观察，不是全部镜像大小，也不含未隔离计量的重启/基础拉取增长。既有约31.8GiB VHDX仍不算项目新增。
- 证据：`audit/local_pilot_docker_before_build.json`与`audit/local_pilot_docker_acceptance_v1.json`；明细在`D:/mrhbench-local-pilot/docker-20260923-001`、`docker-20260923-smoke-002`、`docker-20260923-boundary-003`。后者每包`observed_environment_lock.json`记录image ID/Python3.12.14/实际依赖；当前Dockerfile仅顶层pip依赖固定，跨宿主精确重建仍需完整wheel锁定或传输已构建镜像，再做迁移验收，不能声称任意宿主行为完全相同。
- **未完成：** OOM/PID/存储耗尽压力、cgroupv1直接读回或压力核验、完整宿主越界与broker隔离、产物收集/整题生命周期、image导出导入复验。现有烟雾测试不是正式安全/科研/judge验收。两材料包的科学修订、自动构造缺陷和原生judge工作仍按§0.2.2待办，不因Docker跑通自动准入。
- 本轮未调用新模型；账本仍78/268。92项benchmark离线测试通过，116原缓存hash再次全部未变。GPU未配置或运行。

### 0.2.4 首轮恢复联调与H0 [历史证据摘要]

- **运行底座：** ContainerSession/ExecutorBroker/ContainerExecutor将harness控制循环放入新容器，凭据留controller；执行角色、绝对deadline和包级预算已接。10项真实诊断含cgroup v1/OOM/PID/ENOSPC、只读、网络、非root、超时清理；小故障配置不替代科研预算。入口源码快照不冻结所有import；broker调用数不等于本地操作数。
- **调用层：** 86/101图像字节与rollout匹配，修复`--`前stdin被吞成额外图片；108动态strict-schema失败保留，110以固定payload_json+controller jsonschema通过，拒外部/递归schema引用。宿主技能干扰后在§0.2.7修复为可选profile；仍非裸API等价。
- **冻结H0：** 93首候选独立ABI失败且需人工抢救；107仅凭公开ABI修订，通过17自测+6独立检查，controller负责watchdog/收集。`D:/mrhbench-local-pilot/h0-bounded-20260923-002/artifacts/harness.py`与`audit/h0_independent_build_review_v1.json`是权威入口。未给科研任务，维护者未改其科研代码；不是正式隔离验收。
- **材料/R2：** Luna多轮仍有KL/归一化语义回归；维护者另存v5、独立sol审核，SSA图表provenance另修v6并核DOM/CSV。见`audit/material_pipeline_v3_handoff.json`、`material_v6_root_adjudication.json`，不得计为Luna自主成功。18篇固定v1共享库、时间/目标alias/allowed_versions过滤；364/365页可读，SHOT p5抽取失败保留。IDEA固定背景报告仍合法。
- **五类首次运行：** `h0-integration-20260923-001`用同一H0。WRITE_CONTENT有产物；IDEA提案产生但artifacts=null被降partial；EXP/图表未产出。H0只列工具名不列参数schema，出现inline shell/额外参数误用；公开动作与不可信本地错误已接证据。IDEA/内容写作历史4分不直接代表可靠；WE缺产物曾误作材料失败，144库存证据重评四维0，未虚构图片。审计`h0_write_iv_independent_review_v1.json`、`h0_judge_v2_4_reassessment_review.json`。
- **平台与LIT：** 默认Python缺jsonschema/pypdf的失败属于平台；controller venv启动前预检后，`h0-integration-20260923-002/lit-controller-fixed`完成12模型/11工具/261.39秒，6次参数错误。132/146 capacity失败单列。LIT原文补充与最新诊断见§0.2.5/8。
- **环境交付：** 两镜像同机save/load的tar为374,120,448B，14层引用/9唯一层，image ID/RootFS保持；数值/CSV/numpy/matplotlib复测，错误假设pandas的失败保留，未改镜像。`audit/image_portability_v1.json`不等于干净或跨宿主验证；tar与去重image层不可相加当新增镜像。

### 0.2.5 12/16开发预算、科研产物与历史judge [历史证据摘要]

| 项目 | 实测与结论边界 | 权威证据（audit下） |
|---|---|---|
| 预算可行性 | 用户批准图表12模型、EXP16；同H0/科学输入、CPU/内存/存储/PID/总时限不变。图表实际12模型/13工具/519.764秒（600秒内）；EXP14/13/737.485秒（16/120/1200限制内）。只验证开发预算，不算演化或正式配置。失败variant不覆盖。 | `approved_budget_pilot_costs_v1.json`；材料`materials/pilot_v3/budget_candidates_v2`；运行`D:/mrhbench-local-pilot/h0-budget-pilot-20260923-001` |
| 图表产物 | 140/140数据格、5科学文件，新SSA容器重跑字节一致且实际回看图。标题遮Source行、最大差值漏Snow、硬编码CSV三缺陷。173=3.5抓后两项但漏遮挡，4204×2241原图确实送达，非transport故障。 | `write_evidence_native_judge_independent_review_v1.json` |
| EXP产物 | 48轨迹/108781迭代/432聚合；另8前缀共2400数值独立复算吻合，不等于全复算。13数值失败在raw保留，report把H2分母筛为0/0，提交承认缺陷。 | `iv_budget_independent_review_v1.json`及严格JSON补审 |
| LIT取证 | 157=3.5漏Tent p3反例；v2.5/178读后2.75，43回包匹配、未泄漏私有反例。这是同例修复而非新留出。 | `lit_judge_fulltext_v2_5_independent_review.json` |
| EXP judge | 179=3.5/资源4、36receipt匹配，识别H2但强求无必要的独立alpha/eta效应，feedback泄私有复算范围。182/v2.7两目标行为修复，但又暴露fixture哈希域混淆；历史分保留，不追调同例。v2.8新留出见§0.2.7。 | `iv_native_judge_independent_review_v1.json` |
| 视觉留出 | 180/181在v2.6分别4/2.75，正常图未捏造错误、裁切被发现；仅简单裁切范围，不代表密集科学图普遍可靠。 | `visual_judge_holdout_acceptance_v2_6.json` |

- **隐藏收集配额修复：** 原20MiB读内容hash接口漏掉已捕获24,993,124B raw文件，且32MiB/1000收集上限未公开，属于平台而非没做实验。新容器fd/no-follow流式hash、12项真实文件安全/配额诊断、25MiB生命周期6项均通过；不是原子快照，收集后核hash。`stream_artifact_hash_acceptance_v1.json`、`D:/mrhbench-local-pilot/collection-lifecycle-abd5e6f341/results.json`。
- **当前任务入口：** `materials/development_catalog_v2.json`指向`materials/pilot_v3/collection_candidates_v2/{lit,idea,iv-exp,ssa-write-content,ssa-write-evidence}`。收集MiB为16/8/128/16/64，条目含目录500/200/2000/500/1000；tmpfs work/tmp=80/20且计入内存，均按包公开、不增加原总资源。v2仅复制manifest-owned资产，旧run不追认已见新规则。`taskview_collection_independent_review_v4.json`。
- **超时与证据：** 硬deadline后未采集tmpfs可能丢失；保留已有receipt/入口/模型动作/图像，采集不全记unknown，不假造空输出或科研零分。40秒合成注入10项通过，`failure_artifact_policy_acceptance_v1.json`。所有捕获产物有库存；完整JSONL可分页，未知编码/二进制明确不可读，见`collection_evolution_independent_review_v2.json`。
- **guard历史：** 176 hook未获信任而失效，假canary被读写；177显式单次信任后2 ping成功、2越界MCP及apply_patch拒绝，5hook记录匹配。`native_tool_guard_probe_v1.json`不是OS隔离；后续继承/审计修复见§0.2.9。
- **成本/空间口径：** WE/EXP judge另耗约208/279秒；缓存token为输入子集，不重算。`budget_pilot_storage_after_v1.json`当时workspace129,029,234B、D盘605,831,675B，包含374,120,448B tar、25MiB测试文件及多份证据副本；父子不相加、未计全Codex共享状态、不据两篇线性外推。177源文件hash核对见`taskview_source_independent_review_v1.json`。当时账本182/268与187测试只是历史快照，最新见§0.2。

### 0.2.6 演化适配器与恢复 [开发实现；无真实科研演化]

- `run_evolution_development.py`接真实`StageEvaluationAdapter`、`ReadOnlyReviewResolver`、`NativeDevelopmentBuilder`。initialize零调用冻结配置；advance才执行。二进制/代码/材料/H0/请求hash绑定；按剩余阶段保守transport上界预检开发授权，不冒充正式外层cost上限。
- 已付费评测先缓存，外部审核后单独恢复，不自动重评或重试未知操作。模板默认pending；通过需绑定原同次judge分数+feedback、完整轨迹、公开证据语义及适用图像送达。不给维护者改分通道；hash不是数字签名/OS证明。
- 只投影public且来源允许的完整证据及公开receipt；private机械检查也不能发布。公开标记仍要语义审核。IV179/WE173/LIT178历史映射均pending，公开条目46/44/35、排除private2/1/20，新增约27MB是副本而非新材料。`evolution_evaluator_development_acceptance_v1.json`、`evolution_driver_review_resume_v2.json`。
- 原生evolver输入只含冻结代码/search/已审公开反馈，独立cwd+新容器；selector服务端仅read/list，controller负责watchdog、收集清理。开发limits公开但非正式预算。6个真实Docker+fake-native场景通过；9项CLI测试以合成worker走20评测+修改+选择，不当科学演化。`native_evolution_bridge_independent_review_v1.json`、`evolution_cli_independent_review_v1.json`。原selector真实dict契约/空目录问题后在§0.2.7修复。
- 现两篇无法组成双方五类都覆盖的论文隔离search/test，禁止复制同题伪造hidden。新论文试产/构造模型及正式规模配置待用户；judge与正式隔离尚未完整验收，不能据整轮软件fixture成功关闭goal。

### 0.2.7 宿主上下文干扰与新judge留出 [前阶段快照；后续见§0.2.8]

- **本轮性质：** 上一轮有真实代码/独立回归交付，本轮继续T01/T03/T06，不是重复等待扩充材料答复；没有启动新的论文构造或正式评测。root负责可选上下文策略/真实探针和接口修复，独立runtime复核调用完整轨迹，material协作者复核返回类型/失败入账，judge协作者负责新冻结诊断对照。
- **定位宿主技能注入：** 本机`debug prompt-input`零模型渲染实证，旧`skip_host_skill_discovery=true`仍显示21项技能。按目录路径禁用仍21项；精确`SKILL.md`文件路径禁用后0项。官方[配置表](https://learn.chatgpt.com/docs/config-file/config-reference)写目录，而[禁用示例](https://learn.chatgpt.com/docs/build-skills)使用完整文件路径；以当前二进制实测为准，不改全局config/skills，不复制凭据。`audit/context_policy_offline_acceptance_v1.json`记录文档差异与本机证据。
- **已实现可选冻结策略：** `mrhbench/context_policy.py`只解析初始developer目录，绑定binary hash、原prompt hash、21个精确路径；拒空/截断/非SKILL/越界或更换binary。NativeCodexRunner、CodexJSONTransport、stage/judge clone和evolution CLI均可显式传同一`context_policy`，默认None保留旧行为，不偷偷改历史协议。policy仅冻结denylist，不涵盖后来新增/未显示技能或其他system/developer/工具schema；替换skills配置数组亦不保证保留未观察的旧禁用项。每次配置升级仍要观察实际初始上下文，不能把无目录等同无隐含上下文。
- **两次真实探针：** call183为新CPU容器内原生selector合成接口，实际9个MCP读/list、3个外层exec；call184为JSON transport计算19+23，无原生工具。42/15行完整可观察rollout、输入回执与hook由独立agent逐条审核，两者确无技能目录，profile/binary/调用账本绑定一致；183返回真实dict并正确选唯一H0。证据`audit/context_policy_real_probes_independent_review_v1.json`。仍可看见部分builtin工具schema，未证明裸API等价或正式宿主隔离。该H0只是探针的合成名称，不是新科研harness。
- **修掉两处真实契约问题：** selector之前把schema模式的dict当字符串json.loads，fake runner没模拟真实返回而漏测；现按真实类型处理，183实际验证。JSON transport之前对缺rollout使用ledger不支持的status，可能掩盖原失败并遗留reserved；现区分missing→failed和native活动→rejected_native_tool_activity，真实临时ledger负测完成。`audit/native_contract_independent_review_v1.json`；旧科研记录/冻结H0未改。
- **空目录与回归：** 183暴露文件式发布不保留空search_evidence目录；现在controller在独立release中发布明确零条证据的inventory，不修改冻结stage、不虚构科研证据，保留名冲突拒绝。新CPU容器`D:/mrhbench-local-pilot/empty-evidence-release-91a71b258a`读/list成功且字节一致，零模型。248项benchmark+8项来源测试通过，证据`audit/context_transport_offline_tests_v1.json`。
- **新旧结果边界：** 技能策略改变实际模型上下文。正式H0/演化/executor/judge须在新一轮显式统一冻结profile，不把call107原H0及旧科研分与新profile混成受控演化比较；本轮未手改或重构原H0。正式准入仍不能默认通过。
- **T03新留出结果：** `audit/judge_t03_evidence_completeness_review_v1.json`逐类区分调prompt样例与留出，13项hash/两图原始像素重核；等义/顺序及系统重复仍未覆盖。随后固定v2.8/policy、预冻结EXP和WRITE_CONTENT各一对合成案例，call185–188完成，无重试/改prompt、逐条完整动作/取证/评分/feedback已独立阅读。WRITE_CONTENT为4/2.25，正确区分数值准确但擅推质量等价/跨子群结论；EXP为3.75/3.25，正确识别平均更优不推出每例更优、没有混淆raw-file与EvidenceRecord hash或强加独立factor。没有观察到本批私有canary/审核范围泄漏，非普遍安全保证。源在`D:/mrhbench-local-pilot/judge-v28-holdout-20260923-001`，运行另在`judge-v28-acceptance-20260923-001`；证据`audit/native_judge_v2_8_four_case_holdout_acceptance.json`。不纳入科研benchmark，不由总分排序自动判通过。
- **EXP仍不能整组验收：** 合成fixture实际在新Docker内执行，配置原文件hash在controller记录中却未发布给judge（公开仅code/results identities）；185指出公开证据缺口本身合理，但要求builder改善platform配置identity的反馈归属有问题。相同执行证据在186被给execution4而185为3，非目标维度+1，不能把总分差当纯粹科学缺陷效应，也不能凭一对推总体方差。保留两例不改分/不回填证据、不追同例调分。此为该诊断fixture发布缺口，尚不能泛称主benchmark全部材料有同一问题；正式agent失败归因要另判，不能把controller缺口算solver失误。
- **本轮交接实数：** 188/268，新增额度120/200、余80；183/184接口探针+185–188四judge合计6调用，无reserved、无本项目session-owner容器残留。`audit/context_judge_storage_after_v1.json`记录工作区137,975,632B、D盘试产树636,054,423B；相对上一空间快照增长约8.53MiB/28.82MiB，主要含证据副本和诊断/审计而非新论文包，子项不能再相加，仍未计全Codex共享状态实际分配。材料扩充选择仍待用户回复；Goal保持active，T14未启动。

### 0.2.8 输入身份、judge局部稳定性与LIT标签 [前阶段快照；后续见§0.2.9]

- **原始输入与证据域修复：** 新增`mrhbench/execution_identity.py`，将公开TaskView/asset_manifest、实际发布文件和controller启动manifest的原始字节hash/长度逐项对应；未声明或缺失的公开文件、错hash拒绝发布。stage必须找到唯一启动manifest。另发布仅含公开资产的reference映射，明确raw-file SHA、带ASSET/ARTIFACT前缀后canonical EvidenceRecord SHA是不同hash域；不公开私有文件清单。UTF-8从已验证bytes直接解码，保留CRLF；entrypoint快照验证文件名hash。产物读取及图表库存检查路径均限制在captured artifacts内。
- **真实历史包核查：** 独立协作者对IV/SSA WRITE_EVIDENCE两个预算pilot重建当前证据，实际公开输入、容器启动记录和全部捕获产物raw hash匹配；历史reference确有换行归一化，新实现已改正。`audit/execution_identity_independent_review_v1.json`记录完整逐项比对。没有改旧文件、旧分或冻结H0；新证据没有被旧judge看见，不倒推旧运行验收。IV最终config身份可公开，但仍不能证明每次执行读到相同可变配置；不要求所有科研代码用固定配置格式。新7项identity测试与stage负测通过。
- **三次稳定性诊断：** 固定v2.8、sol/medium和同一skill policy，call189–191分别完全重复187写作正确例、只改提交措辞、只扰动E1证据句块顺序。四维均与基线4一致；完整轨迹/依据/feedback已由独立judge协作者逐条审阅，无捏造缺陷或观察到的泄漏。实际prompt bytes重复相同；新cwd/session不相同。改写例仅读必要公开3条、没读私有维护记录，不能声称其通过私有暴露后的防泄漏验收。顺序扰动也改变段落布局，不当纯排序因果效应。`audit/native_judge_v2_8_robustness_diagnostic.json`；单个简单满分样例不代表边界分、EXP或跨模块稳定性，不修复185/186非目标维度波动，T03仍部分验收。
- **LIT私有候选：** 已独立读旧8篇固定v1的相关正文，形成3核心/2背景/3易混淆候选，附条件、非校准置信度、页/字符位置和原文hash；root已复核全部短引文位置与邻近语境。Tent的概率回归例外、TTT的训练期准备、CORAL/DANN的source访问条件均显式保留，不把近邻引用自动当错。原8篇不是必引gold，标签不进入公开检索或质量总分；`audit/private_ssa_lit_relevance_review_v1.json`。既有3篇SSA候选亦已独立正文补审，root复核原文位置与邻近语境，保留CAFe/BN-statistics为core、LayerNorm为background，共11篇私有诊断候选（5核心/3背景/3近邻）；CAFe无infomax变体和LN不只分类实验的例外均记明。新增`audit/private_ssa_lit_existing_three_review_v1.json`；7篇IV仍SSA未审，不能直接迁移为负例。
- **真实LIT诊断：** 新`mrhbench/retrieval_observations.py`按成功broker回执区分返回/摘要读取/正文页读取，再从显式claim-map提取声明采用；按document+version去重，失败/未知/错版本独立列出，不能凭RPC断言模型理解。10项新增测试通过。`audit_ssa_retrieval.py`核私有候选PDF/页/char与实际任务setting字节，对历史H0 LIT运行只做离线诊断：返回12篇，摘要1篇、正文1篇中的1页，声明采用6篇；6次参数失败，不记成功阅读。采用中3核心+3近邻，不自动扣近邻分；另2篇已返回但SSA未审。`audit/private_ssa_retrieval_diagnostic_v2.json`与root综合审核`identity_retrieval_root_review_v1.json`保留原分/原轨迹，不改变质量总分。
- **当前调用：** 191/268，本轮新增123/200、余77；无reserved。此次只3个judge诊断新调用，无新科研运行/新论文构造/正式split。267项benchmark及8项来源测试通过（`audit/identity_retrieval_offline_tests_v2.log`、`identity_robustness_source_tests_v1.log`）。存储快照`audit/identity_robustness_storage_after_v1.json`记录工作区139,058,853B、D盘试产636,672,389B，采样在最终标签接线前，不能当最终文件大小；本轮未构建新镜像，本项目session-owner容器无残留。材料扩充和构造模型选择仍待用户回复；不以局部诊断消耗完额度，不宣称goal完成。

### 0.2.9 原生工具可信度门与严格读隔离前置项 [前阶段快照；后续见§0.2.10]

- **本轮方向：** 上轮为实质代码/真实诊断进展。本轮优先T01/T02/T07，不继续反复调judge、无新模型调用、未扩论文。原生transport的completed只是调用结束；原有评分已标awaiting manual与非正式，不能误说旧系统自动通过科学准入。
- **hook继承与冻结修复：** judge clone以前会丢弃调用者显式提供的hook配置；新增保存绝对spec并转发，核对guard允许工具不超出本次实际工具，旧展开配置没有可追溯spec则拒绝。guard config/script/Python可执行文件hash在构造时冻结、command前重新核验，变更在ledger.reserve前拒绝；复制metadata避免隐式修改。6项独立负测通过。189–191原来没有配置hook，不声称它们被移除了已生效防护。不默认开hook，也不称预检消除了运行时竞态。`audit/native_judge_hook_and_tool_evidence_gap_review_v1.json`。
- **运行后工具审核：** `mrhbench/native_admissibility.py`检查exact rollout hash/session/终止、外层call-output、CLI/rollout内层MCP对应、声明hook的逐调用记录及可选controller state。未配置hook与配置但丢证据严格区分；未知格式/缺失为incomplete，观察到非允许工具活动为rejected_observed_activity。外层code-mode JS必须另有精确hash绑定审核，不能用正则或MCP成功日志替代。183历史3 outer/9 MCP/9 hook经逐段JS独立审核开发准入，旧run不改；189–191机械回放均pending_code_mode_review，无新错误，不能把独立文本送达复核当自动安全证明。12项模块测试及`audit/native_admissibility_independent_review_v1.json`、`native_admissibility_judge_replay_v1.json`。
- **真实接线但不篡改分数：** 新judge manifest显式发布server侧allowed_tools；生成候选后保存native_tool_audit，incomplete/rejected不生成新的result评分，保留候选/费用且不算科研零分。pending code-mode仍保留原有人工全轨迹门，图片送达与语义feedback也要审核。演化冻结会绑定工具审计附件hash，普通审核通过不能覆盖明确工具失败；未有附件的历史数据仍走既有开发审核，不倒写历史。新增3项judge门测试、2项冻结/审核门测试通过。此为执行后可信度门，不会撤销已发生的副作用。[官方hooks](https://learn.chatgpt.com/docs/hooks)确认部分错误可继续执行，故没有宣称hook fail-open或OS隔离已解决。
- **Windows严格读隔离仍受环境阻塞：** 官方自定义permission profile允许`:root=deny`+`:minimal=read`+任务路径grant；当前binary用独立空CODEX_HOME通过正向语法解析并拒绝无效配置。实际允许读fake canary的首个零模型探针在child启动前失败：`Restricted read-only access requires the elevated Windows sandbox backend`。按约定立即停止，未测的拒绝读写不能计passed，canaryhash未变；没有配置admin/服务/全局权限/复制auth。`audit/native_read_boundary_research_v1.json`及`D:/mrhbench-local-pilot/permissions-canary-f10a2478e3/results.json`。官方[permissions](https://learn.chatgpt.com/docs/permissions)/[Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox)只说明机制，解析成功不证明工具隔离。
- **回归与综合审核：** 290项benchmark离线测试通过，`audit/native_admissibility_offline_tests_v1.log`；综合hash/边界审计`audit/native_admissibility_root_review_v1.json`，无reserved。没有将代码测试当科学或OS隔离验收。
- **待用户选择：** 已询问继续本机Windows、准备官方elevated sandbox配置步骤，或改独立Linux环境。科研Docker可用不代表订阅Codex主进程已经隔离；MCP/浏览器仍要单独约束。原有两篇新材料/sol构造扩充选择也仍未收到答复。不自动安装、迁移或提权；Goal保持active，整项T07/T14不标完成。调用账本仍191/268、余77。

### 0.2.10 IDEA/LIT有限留出与剩余依赖 [上一阶段]

- **独立关闭审计：** `audit/goal_requirement_evidence_review_v1.json`逐项映射T00–T14的已有证据/缺口。还不是全goal完成，也不是全线blocked：现有材料准备、有限judge校准仍获授权；三类用户决定分别为原生隔离环境、具体“两新篇+sol构造”方案、将来合格池后的正式配置。不得把未回复构造策略说成200次额度不足，不把未过正式隔离说成开发记录作废，不以无限校准追求global oracle。旧进度§0.2.4–6已去重复合并，协议正文及历史audit未改，见`agents_history_consolidation_v1.json`。
- **本次4例：** 当前v2.8/sol-medium/冻结skill policy，IDEA与LIT各一对新的合成留出，预写预期方向、不设目标分数、不追调样例。IDEA两提案都完整/诚实/可行，比较有研究增量的条件分析与纯安装复核；LIT同三篇fictional mini-text，比较具体联合缺口与泛泛愿景，不充真实论文或benchmark题量。root预检发现LIT v001少platform_trace，保留原件后另冻v002发布记录，明确不是solver检索轨迹；v001没有付费运行。两对长度不完全相等，不作单因子因果解释。
- **实际结果192–195：** IDEA 4.0/2.4，弱例分维为value1/difference0/specificity4/feasibility4/hypotheses3；LIT 4.0/2.5，弱例accuracy3/coverage3/synthesis3/gap1。差异主要对准研究增量与具体缺口，未强求新算法或唯一gold。弱IDEA hypotheses3部分理由与value/difference重复，保留维度耦合疑问。LIT的总体datasets-differ措辞并不逻辑推出所有论文两两不同；judge实际也承认前文S1/S3同C，只按imprecision扣3。该扣分可辩护但有解释空间，也可仅归综合不足；不将其武断判成原文造假、judge幻觉或纯净synthesis操纵。
- **逐轨迹验收：** 独立agent完整阅读4条动态取证/最后判分/feedback，4/4/7/7 records全文送达，私有maintenance确被读到但未见canary/维护复核范围泄漏。4份精确payload/hash绑定的code-mode审核另存；原native_tool_audit pending不覆盖，另存reviewed结果为development_admissible，不证明OS隔离。root完整读所有fixture和最后judgment/feedback，未冒称重复了全部动态轨迹审阅。最终审计`audit/native_judge_v2_8_idea_lit_holdout_acceptance_v2.json`、`idea_lit_holdout_root_review_v1.json`。
- **本轮到此停止校准：** 只用4次、无重试/改prompt/改分/科研重跑；账本195/268，新增额度127/200、余73，无reserved。没有因为各合格例拿4而强行压分；这些是有边界的开发行为证据，不自动冻结正式judge可靠性或排名。已有290项工程回归仍是上一代码版本证据，本轮未改工程实现。环境与新增材料策略问题等待答复，T14未启动；不再对这4例追调或新增相同诊断花额度。

### 0.2.11 材料准备与输入完整性修复 [上一阶段]

- 上一goal turn仅向用户复述已完成预算验证，属no progress；本轮选择实际材料准备及发现的发布完整性缺口，不继续judge重复校准，不把待用户决定泛化成所有工作不可做。
- **T10/T11输入门修复：** 旧batch只核constructor request/原始source，未完整绑定导航索引、schema/prompt及返修输入；reviewer未保护request/prompt/structural_check。现由controller在调用前保留这些文件及目录内文件集合的hash，调用后核对，持久增删改则failed_needs_attribution、不接纳候选；合法output/日志仍允许。独立复核与修复/恢复/增删测试见`audit/material_input_integrity_independent_review_v1.json`。这不是运行时访问预防，不能发现改后恢复，不关闭T07，旧receipt未重写。
- **下一批不是已经选了两篇：** 旧提议只有数量/sol策略，未指定标题。本次只在已缓存原始材料中预筛三篇：Gaussian-mixture one-gradient-step与Diffusion Evolution仅README，缺全文/精确方法等；后者README有非商业许可限制待核，不当普通Apache许可。FTCT完整v1支持准备两类WRITE候选；root已读§4.3及Table1，确认7配置/6指标、N=5/M=3和最优shots选择条件，不把42M–145M训练改称CPU可行实验。
- **实际准备：** `materials/next_batch_proposals_v1/jobs/ftct.json`为未选定source-only proposal，validate_job及prepare_material_job通过，原文/导航/模板发布在`D:/mrhbench-local-pilot/next-material-preflight-aedb6e13f7`。发布清单997,282逻辑字节，含publication的目录998,152字节（不是镜像或物理盘增量）。没有科学任务产物、环境实测或rights准入；资源数字仅未测候选。`audit/material_next_batch_preflight_v1.json`；root独立核7来源hash及5节定位hash。
- **防误启动：** 新run_batch在任何worker/调用前拒绝显式未选定或source-only proposal，含与普通job混合的整批；以后获准需新建approved job版本，不覆盖此proposal。旧jobs缺字段沿用原行为，此门不是用户授权认证。上述preflight审计记录的是加此门前入口，当前代码与最终root复核见`audit/material_preflight_root_review_v1.json`。
- **回归与额度：** 完整296项benchmark测试通过（51.259秒，`audit/material_integrity_offline_tests_v2.log`）；其后新增proposal拒启门，当前23项材料测试通过，包含单proposal/混合批零调用负测，不冒称最终版本全量297已跑。无新模型、联网、镜像或科研容器运行，账本195/268、余73、reserved0。原生环境选择、具体新论文/构造策略仍待回复，T14未启动，goal未完成。

### 0.2.12 两个EXP候选的原始全文补齐 [上一阶段]

- 上轮有实际代码/材料进展，本轮继续补原始来源，而非重跑已完成judge样例。Gaussian-mixture与Diffusion Evolution原来只有README，现通过primary-source核查及新snapshot取得版本化全文、精确commit及有限代码/许可资料；旧缓存不覆盖。11份新payload合计1,374,100字节，非镜像或宿主分配量；全部hash复核，`audit/raw_source_expansion_root_review_v1.json`。
- **Gaussian-mixture：** 读取arXiv2503.00856v1的模型/训练/假设/主要结论/模拟及A9，另读取commit `257bcd539ab3adef9aeae9d78604f681ea204017`的Fig1b notebook及MIT文本（Git blob与pinned tree匹配）。原生合成数据+单梯度步+ridge/Hermite比较是CPU数值研究候选，但保存的历史backend为gpu，未实测CPU，不能承诺完整2400次拟合可在短预算内完成。不得将有限n实验称为渐近证明、将Fashion-MNIST GAN分支混入此范围。
- **具体来源对齐：** 论文Eq5/6训练归一化不一致，Eq7是MSE而notebook实际gloss是half-MSE；出题前必须显式裁定。独立复核确认代码degree3对应论文l=4且beta=.74满足严格区间，不是索引错误；每alpha固定数据下重复初始化/噪声，不是20独立数据集，但caption只说Monte Carlo，不能武断判作者bug。Hermite替换发生在原激活训练第一层之后，不得改训练方法。来源与审计：`gaussian_{fulltext_prescreen,source_contract_review}_v1.json`。原文arXiv日期不当最早披露证明，preprint与会议终稿尚未对齐。
- **Diffusion Evolution：** 已读2024-v2正文算法、二维实验与附录；确有不训练神经网络的低维优化分支，不是将图像扩散训练缩水。尚需对齐所谓linear schedule的常数公式、entropy符号、fitness/边界与数值端点；不把原文不同迭代数比较当等预算。v3是2026更新，未替换进2025候选；精确代码commit为2025-06，未声称对应初稿。paper与代码分别存在非商业/academic-only限制，不能写成普通Apache自由发布。见`audit/diffusion_fulltext_prescreen_v1.json`；原公式疑点仍未裁定，不直接交solver猜。
- **边界：** 0新模型、0作者代码执行、0Docker运行；source preparation不等于选定两篇、构造科学任务或CPU验收。账本仍195/268、余73，无reserved；未改核心实现，最新测试范围沿用§0.2.11，不制造新测试完成声明。构造策略与原生隔离环境仍待用户回复，goal保持active，T14未启动。

### 0.2.13 Codex额度耗尽后的角色transport改定 [当前接续，2026-09-24]

- **用户决定：** Codex订阅额度已用完。builder/evolver与judge改由Claude Code原生agent承担；executor改为Claude订阅的“反代API式”调用，**不带原生harness**（无内置工具/MCP/技能/子agent，只按请求返回JSON），控制循环仍由被测harness拥有。维护者/研究协作subagent（本对话的Claude Code）不是被测角色。
- **模型：** 用户未指定具体Claude型号；root暂定三角色统一claude-opus-5-5、effort medium以对应旧“同模型medium”设置，可由用户改定。材料构造模型仍待用户选择，不因本改定自动换成Claude。
- **结果边界：** 新transport改变实际模型与上下文。旧gpt-5.6-sol的H0、科研运行、judge分数全部保留为历史开发证据，不与Claude配置混成受控比较；H0须在新配置下重新构建并冻结，judge须按§7.2在新配置重新逐轨迹验收。
- **调用额度：** Claude新调用暂记入同一开发账本，仍受总上限268（当前195、余73）约束；超过须用户另行授权。订阅不虚构逐次美元成本。
- **修复入口回归：** 接手时真实全量为297项、2 errors（§0.2.12新Gaussian源manifest缺paper_id/kind；§0.2.11只跑了23项材料测试未发现）。原缓存不可改，新增`research/benchmark/materials/source_manifest_overlays.json`按manifest sha256绑定归属，`build_material_catalog.py`仅在hash一致时使用、否则拒绝；新增1项测试。
- **Claude transport已实现并真实探针：** `mrhbench/claude_transport.py`。executor=`ClaudeJSONTransport`（`claude -p` stream-json；`--tools ""`、`--safe-mode`、`--setting-sources ""`、`--strict-mcp-config`、`--disable-slash-commands`、替换system prompt、无session持久化；剥离父会话CLAUDE*/ANTHROPIC_*环境变量，仅订阅登录）。judge/builder=`ClaudeNativeRunner`（bounded_mcp只暴露受控MCP工具；native_development为文件/shell工具，尚未真实使用）。stdout完整stream即精确轨迹；post-run审计核init声明工具⊆发布集、tool_use/result配对、MCP连接与server计数。
- **探针196–198：** 196 executor：init工具空，图像左红右蓝判对，19+23=42，总输入约778 token（隐藏上下文很小，但不是裸API等价证明）。197为root探针manifest错误（evidence origin非法）致MCP未连接，旧runner误记completed——账本原样保留，runner已改为required MCP未连接即failed/platform。198 judge：仅2个MCP工具，读到canary；MCP图像原字节出现在精确stream并判对颜色；stream3次=server3次。证据`D:/mrhbench-local-pilot/claude-transport-probe-{93ba1bd852,d29fccceee,67b700a8a3}`。init仍声明builtin plugins(agents-md/telemetry)和agents名单（无Agent工具不可调用）；因agents-md插件，builder/judge的cwd及祖先目录不得含AGENTS.md。
- **judge接线：** `native_judge.run_native_judge`遇`ClaudeNativeRunner`走`native-judge-claude-v3.0`：v2.8政策原文只替换Codex code-mode/image()工具机制句（原文变更即拒启），零成本manifest预检、Claude stream审计，图像交付按EvidenceRecord同hash域在精确stream中机械核验（CLI送API前是否缩放未排除，视觉判断仍须轨迹审阅）。Codex路径与v2.8保留不动。新配置下judge尚未做任何§7.2验收。
- **H0：** `build_h0_claude_development.py`沿用旧H0同一发布输入与容器内MCP工具桥（零科研任务），builder开发墙钟1500秒（旧900；新配置不与旧H0对比）。运行结果见下条。
- **材料协作（均0模型调用、未改缓存/旧审计）：** Gaussian裁定+CPU可行性`audit/gaussian_adjudication_cpu_feasibility_v1.json`：Eq5/6、half-MSE、Eq4尺度、D=3/l=4、Hermite时机、固定数据重复逐项给出任务规格决定；另发现尺度常数、等量混合采样、ReLU不满足A.8三项；Docker 2CPU/2GiB单配置中位0.358秒/拟合，全sweep外推约866秒（仅外推）。Diffusion公式对齐`audit/diffusion_formula_alignment_v1.json`：linear调度Eq14无t→固定cosine Eq16；熵缺负号；映射g未说明→维护者显式定恒等；Ackley方向矛盾且域外可超最大值→首批只取two-peak+Rosenbrock/Beale/Himmelblau最小化；T端sqrt需clamp；OpenES非等预算；作者实现未缓存；许可NC+Tufts附加限制，不向solver发布作者代码/原文。SSA剩余7篇私有标签`audit/private_ssa_lit_remaining_seven_review_v1.json`：Garg为confusable，其余6篇为新增`unrelated`标签；20处引文位置重核一致；历史H0运行只返回其中2篇且未读。三份均为候选，root尚未完成裁定整合。
- **回归：** 313项benchmark离线测试通过（`research/benchmark/audit/claude_transport_offline_tests_v1.log`）。账本198/268。
- **Claude H0（call199）：** 零科研任务，10次容器MCP调用（仅4个容器工具），产出`D:/mrhbench-local-pilot/h0-claude-20260924-001/artifacts/{harness.py(53,734B),tests/test_harness.py,build_manifest.json}`，stream审计admissible。独立ABI/轨迹审阅进行中，结论写`audit/h0_claude_independent_review_v1.json`；未审前不冻结、不作科研运行依据。
- **judge重验证（call200–204,206–210，v3.0自由文本JSON）：** `run_judge_claude_revalidation.py`对原v2.8已冻结的10个合成fixture（五类各一对）各跑一次、不重试，预期方向在调用前从原frozen plan复制。结果：finite_alpha 4.0；finite_beta**失败**（模型在JSON中输出`," + "affected_requirement"`拼接残片，按judge输出格式失败保留，不重试）；passage 3.75/2.0；proposal 3.4/1.6；review 4.0/1.75；visual 4.0/2.5。分数次序符合预期不等于验收；独立逐轨迹审阅进行中，写`audit/claude_judge_revalidation_review_v1.json`。
- **结构化输出（call205探针）：** `--json-schema`会在init中增加唯一输出工具`StructuredOutput`，模型调用后result含CLI校验的`structured_output`（引号/反斜杠正确转义）。现两角色均采用：executor以应用schema、judge以`{judgment,feedback}`信封（完整validator仍由controller执行）；仅额外放行该输出通道，并核对structured_output与实际StructuredOutput调用输入同hash。judge版本升为`native-judge-claude-v3.1`（v3.0结果不改归属）。205本身按旧规则记rejected_native_tool_activity，属预期观测。
- **其他：** `evolution_native`/`run_evolution_development`/`StageEvaluationAdapter`/`run_container_stage_development`均支持显式`roles`配置（`config/role_transport_claude_v1.json`；Claude角色禁用Codex context policy与hook guard），默认仍为历史Codex路径。私有LIT检索诊断接受已审`unrelated`（无角色、不罚分），18篇全标：历史H0 LIT返回12篇=5核心/2背景/3近邻/2无关，读1核心，采用6=3核心+3近邻（`audit/private_ssa_retrieval_diagnostic_v3.json`，v2保留）。root对三份材料协作结果的原文抽核见`audit/material_candidates_root_review_v2.json`。316项离线测试通过（后续接口v3、refusal分类后317项通过）。账本见下条。
- **H0独立审阅与冻结：** `audit/h0_claude_independent_review_v1.json`判`development_admissible`：96行轨迹全读，仅4容器工具/10次，重放写入内容与最终文件字节一致；新容器内25/25自测；旧6项检查原样运行6/6失败（旧fake硬编码旧H0响应格式，非ABI证据），按新H0自定格式重述28项独立检查24过4败。6个未修缺陷记为该H0属性（D1缓存读重复只回stub、长LIT正文可能永不可见；D2 hash助手失败时清单旧sha；D3非dict参数异常；D4 NaN超时透传；D5 model_client误报omission；D6超长记录截断成非法JSON），维护者不改H0。控制器侧：broker已拒非有限timeout（D4），采集流式重hash（D2），executor schema校验（D3）。冻结副本`D:/mrhbench-local-pilot/h0-claude-frozen-v1/harness.py` sha256 `7b6f5803…b3b99f`（只读，freeze.json）。
- **T13 Claude集成v1（call211–230）：** `run_claude_integration.py`用冻结H0依次跑五包，各Claude judge v3.1评一次，不重试。记录分：WRITE_CONTENT 3.5、IDEA 3.6、LIT 0.5、WRITE_EVIDENCE 0.5、EXP 0.25，全部submission partial。**系统性平台原因：** 每包恰3次executor调用，第2次（首个act步）均被API safeguard拒绝（`reasoning_extraction`，约2.6秒、0输出token），H0随即按budget_exhausted收尾，LIT/WE/EXP从未调用任何工具。拒绝当且仅当output_schema含`reasoning`属性（5/5 vs 10/10）；受控探针call231复现，call232的`payload_json`信封也被拒（category cyber），故不采用信封。**归因：** 主要为v2接口未披露的provider约束（旧Codex executor接受同样设计），次要为H0把单次provider错误当预算耗尽；这些低分不是科研能力测量，不得作H0基线或演化信号（`audit/claude_integration_v1_attribution.json`）。不做字段改名等规避safeguard的伪装。transport已把此类拒绝分类为`provider_safety_refusal`（平台结果、不重试）。
- **接口v3：** `runtime/interface_container_v3.json`仅在v2基础上增加`model_client.provider_constraints`（整请求可能被拒、计次且不自动重试、单次拒绝≠预算耗尽、不得请求模型内部推理/思维链如`reasoning`字段）；v2不改。Claude builder与Claude evolver路径改发v3，Codex路径仍v2。已按v3启动H0重建（call233，`D:/mrhbench-local-pilot/h0-claude-20260924-002`），v1冻结H0保留为历史。
- **judge重验证审阅：** `audit/claude_judge_revalidation_review_v1.json`有界结论**partial**：7 pass、2 partial（proposal_alpha强加不必要的随机配额消融臂；review_beta综合理由误述提交内容）、1未评分（finite_beta格式失败，其内容确实抓到H2聚合→普遍的目标缺陷），0 fail；全部记录读完、无canary/私有泄漏、hash域未混淆、两张图像素实际送达并检查。Claude在非目标维度普遍比Codex严（alpha 3.75/3.4 vs 4.0；beta普遍低0.25–0.8），两配置分数不可互换；同一缺陷多维重复扣分、个别分与自身理由矛盾。T03仍未整体验收。
- **Gaussian EXP候选包（维护者构造，非构造模型产物）：** `materials/pilot_v3/maintainer_candidates_v1/gaussian-exp/`，task_id `gaussian-onestep-hermite-alpha-exp-maint-v1`，五个gate全pending，未入任何catalog。问题：β=0.74、n=m=k=1000下Hermite代理与一步训练网络测试MSE随α是否一致（ReLU/tanh/sigmoid）；H1一致性（solver自定判据）、H2差异无系统α/激活依赖、H3网络误差随α升且Hermite同向。起始代码含数据生成/Eq4步/Eq5 ridge/MSE/原激活网络，不含Hermite代理与作者代码；资源候选2CPU/2GiB/1800秒/16次模型调用（待真实pilot）。容器内三次运行通过，Eq4有限差分2e-11、Eq5驻点1e-17，与独立smoke差2e-13；导出泄漏字符串检查通过（非语义审）。**待裁定：** H3在该标签尺度下可能近乎自动成立（绝对MSE随α升、按标签方差归一后无明显趋势），可能需重述；1800秒高于IV；复用IV镜像是否可接受。审计`audit/gaussian_exp_candidate_construction_v1.json`。
- **H0 v3（call233）：** 按接口v3重建，12次容器工具，stream admissible，产物`D:/mrhbench-local-pilot/h0-claude-20260924-002/artifacts/harness.py`（sha `619dc724…`）；独立审阅（含：所有可发output_schema不得请求内部推理、单次provider拒绝不得触发预算耗尽、v1 D1–D6复查）进行中，结论写`audit/h0_claude_v3_independent_review_v1.json`。
- **judge v3.1 EXP对（call236–237）：** finite_alpha 4.0；finite_beta 2.75（conclusion 1、rigor 2，execution/test_validity与alpha同为4）——结构化输出下不再格式失败，且非目标维度未漂移（对照Codex 185/186的execution差）。轨迹审阅待做，`D:/mrhbench-local-pilot/judge-claude-v31-exp-20260924-001`。
- **Claude构造批次（constructor/material_reviewer角色）：** `run_material_claude.py`，`ClaudeNativeRunner` `material_workspace`档（仅Read/Write/Edit/Glob/Grep，`--restricted`无shell、文件工具限cwd；工作区及祖先含AGENTS.md/CLAUDE.md即拒启）。root选定两篇（可逆、低成本）：FTCT WRITE_CONTENT+WRITE_EVIDENCE（由原proposal派生`materials/next_batch_v2/jobs/ftct-write-v2.json`，原proposal不改）与Diffusion EXP 2D分支（`diffusion-exp-2d-v1.json`，scope写入全部维护者裁定与许可限制）。输出`D:/mrhbench-local-pilot/material-claude-20260924-001`，结果待补。
- **H0 v3审阅与平台修复：** 首审`audit/h0_claude_v3_independent_review_v1.json`判needs_repair：所有可发schema均无reasoning类字段（通过），但**单次模型错误即当预算耗尽退出**（V3-1）。根因主要在平台：broker把一切异常压成同一句含“remaining budget”的通用消息，任何harness都无法区分拒绝与耗尽。修复为**接口v4**（`runtime/interface_container_v4.json`）：broker返回不泄漏的`category`（budget_exhausted/provider_refusal/provider_error/invalid_request/tool_error）与固定公开消息，worker抛`BrokerError(RuntimeError)`带`.category`，`BudgetExhausted`/`ProviderRefusal`为ProtocolError子类；规则“只有budget_exhausted的消息可提budget”在任何harness运行前已声明，复核发现provider_refusal文本自相违反后按该规则改写（非为该H0调参），并加测试冻结消息=接口v4文件。复核`h0_claude_v3_platform_v4b_recheck_v1.json`：H0 v3在v4平台上`development_admissible`（单次拒绝后继续并完成；连续3次拒绝优雅partial；真耗尽即停），遗留V3-2/3/4/5/6/7/8与inf超时透传（broker拒绝）记为H0属性。注意该H0按消息关键词分类（budget/limit/quota/exhaust/timeout/cancel），改消息须升接口版本。冻结`D:/mrhbench-local-pilot/h0-claude-frozen-v3/harness.py`（sha `619dc724…`，freeze.json绑定broker/worker hash）。Claude builder/evolver今后发v4。
- **T13集成v2结果（冻结H0 v3、平台v4）：** 运行中又暴露三处平台缺陷并已修（均有测试、均不改H0）：①provider结构化输出要求属性键匹配`^[a-zA-Z0-9_.-]{1,64}$`，IDEA输出合同有67字符键→call247/248直接400；文本JSON回退又因“JSON后多余内容”失败（292/293）；最终改为**无损键别名**（`provider_safe_schema`/`restore_aliases`，逐调用记录别名，call295探针验证）。②judge v3.1仅信封schema，WRITE_CONTENT缺`failure_reason`、IDEA写了非rubric维度→校验失败；**judge v3.2**在结构化通道发送与validator结构同构的完整schema（维度枚举、0–4整数、精确键），对历史16个通过/2个失败的判定100%区分，语义校验仍在controller。③CLI把长边>2000px的图像缩放后才送API（2550×1080→2000×847）；新增`mrhbench/image_views.py`：超限图像额外发布无损全分辨率tile（标为派生视图），交付不精确时以Lanczos参考PSNR≥30dB核验“忠实缩放”并记录，**judge v3.3**提示词披露。另：`rejudge_claude_stage.py`对有效执行只重评不重跑。
  - 当前开发结果：WRITE_CONTENT **3.75**（v2执行，v3.3重评）；IDEA **3.8**（`claude-integration-20260924-004-idea`，3次executor全成功，前两次IDEA尝试属平台损坏）；LIT **1.75**（执行干净，11/12次模型、2检索3读3页读，judge v3.1）；WRITE_EVIDENCE **3.0**（v3.3重评，缩放交付已核验但judge未读tile，视觉细节结论有此限制）；EXP **stage_failed**：solver写出超过任务**已公布**128MiB收集配额的`replicate_results.jsonl`，controller按T06保留failure.json（归因待审、不自动零分、未评judge）；H0从不向executor展示resources（V3-7）是促成因素。逐轨迹审阅进行中，写`audit/claude_integration_v2_review_v1.json`。这些是开发证据，不是正式分数，也不与Codex历史或v1混比。
  - 调用：账本299/368（本段含两次重评、IDEA三次、探针、结构化/别名探针）。
- **构造批次结果与控制器哈希：** 两个constructor（call234–235）均完成且stream admissible，但结构门拒绝：无shell的构造者无法算sha256，各自写了占位（`PENDING-run-tools/fill_asset_hashes.py`、`UNCOMPUTED-no-hash-tool`）——属我方profile缺口，非构造质量失败。新增受信控制器步骤`material_batch.fill_sentinel_hashes`：只替换哨兵值为实际字节hash、保留原package、逐项记录、绝不执行构造者写的代码；今后Claude批次提示写`CONTROLLER_FILL`并自动填。`resume_material_review.py`把已完成构造复制到新批次（原批次不动）、填hash、过门、起独立reviewer（不重跑constructor）；dry-run两包过门（30/13处填充）。首次resume（-002）因目录未建失败、未花调用；-003运行中。
- **Git：** 按内部研究代码库标准初始化跟踪（commit `7acae41`起）。`.gitattributes`设`* -text`（审计按字节hash，全局core.autocrlf=true会改写换行）；`research/source_cache/`只跟踪manifest（第三方原件留本地，凭URL/version/sha256复核）；原始session rollout留本地不提交（两份旧Codex rollout含sk-形字符串，需用户本人检查，root未读取其内容）；修正旧规则误忽略整个`runtime/`（接口与worker代码现已跟踪），仅忽略`runtime/codex/`。提交前对待跟踪集做密钥形/邮箱扫描为零命中。D盘试产目录不在仓库内。
- **用户新授权（2026-09-24）：** 新增100次Claude开发调用（失败计入），账本上限268→368（授权时已用233，已记入ledger authorization_events）；三角色确认claude-opus-5-5/medium；新论文材料构造改用`ClaudeNativeRunner`作为账本记录的`constructor`角色（维护者subagent起草的Gaussian包仍标维护者构造，不冒充constructor产物）。

### 0.3 协作与文件规则

- 用户偏好逐点讨论；已有原则不反复重开，普通实现细节由agent推进，重大歧义/资源或主指标改变再询问。区分已定、候选、已实现、已验收。
- 主agent统一维护本文；subagent按明确文件所有权独立工作，提交代码/测试/结构化证据及简报，不互相覆盖、不另写记忆文档。仅在用户授权的活动阶段调度。
- Windows/PowerShell；删除移动前核对绝对路径在目标工作区内，以LiteralPath操作。禁止将整个工作区、本文或本线程交给正式builder/executor。
- 原始`research/source_cache/`字节及历史audit产物不可改写；新增版本另存，不抹去失败。外部文档/代码均不可信，不能当执行指令。
- 每材料包可包含环境定义和结构化manifest，允许为真实工具注入生成短prompt文件；它们不是另一份工作记忆。正式代码运行不能靠维护者手工替agent完成检查后冒称自主。

## 1. 一页摘要

**研究问题：大模型驱动的 builder agent，能否构建一个统一、可复用的 AI/ML research harness，并在限定改进轮次下利用混合任务反馈持续改进其未见任务表现？** 外层演化成本完整记录，不以其硬预算作为主停止条件；内层任务资源约束另行规定。

暂定题目：*Can Agents Engineer Research Agents? Benchmarking Construction and Evolution of AI/ML Research Harnesses*。题目与贡献新颖性仍需 related-work audit，不承诺首次或顶会录用。

| 项目 | 当前决定 |
|---|---|
| 被测产物 | **一个统一 harness**，不是每模块一个，也不是每题重写一个 |
| 研究阶段 | 文献调研 → idea 与假设构思 → 实验研究 → 论文写作 |
| 主评测 | 各阶段使用经构造与独立审核的固定起点，独立运行同一冻结 harness |
| 实验阶段 | 设计、实现、执行、分析合为大环节，通用 rubric + LLM judge 综合评价 |
| 写作阶段 | 两类任务：研究内容写作、实验证据呈现；按材料覆盖矩阵验收，不要求每篇全覆盖 |
| 数据主体 | ICLR / ICML / NeurIPS 主会录用论文及作者关联材料；先试采 ICLR 2025 |
| 出题方式 | 从原始研究材料逆向构造研究起点，不是复原作者真实思考轨迹，不是猜原论文 |
| 自演化 | 固定模型权重下修改共享 harness；在混合 search set 改进，隐藏任务无跨题演化 |
| 当前缺口 | 正式角色/服务隔离、judge留出可靠性、材料自主量产质量与新论文覆盖、真实演化adapter及正式配置；CPU环境、R2与H0已有开发实测，不把它们误写成从未实现 |

**覆盖结论：** 四阶段在概念上覆盖了我们选定的研究主线，但这不是“已经测到端到端自主研究”。固定阶段输入屏蔽了上游错误传播、衔接与自主选题；最终需另有小规模连续流程 use case 才能检验整合。

明确不在当前主范围：完全从零选择学科方向、真实历史失败轨迹恢复、单列失败后研究迭代、独立 rebuttal/审稿回应模块、论文投稿行政流程。实验中可自主重试/迭代，但不因此声称已经单独测量历史失败续研。理论证明生成也不是已确定的独立任务。

## 2. 学术定位、研究问题与结论边界

### 2.1 候选贡献（不是已验证结论）

1. 面向 AI/ML 研究阶段、具有材料溯源和明确输入输出的任务集合，测 **builder 工程化统一 research harness 的能力**，而非只测一个科研 agent 解题能力。
2. 构建—混合反馈演化—冻结泛化的受控协议，分清外层改进与内层科研执行，并记录完整成本。
3. 对高自由度科研过程的证据约束评分、judge 校准、污染与成本审计，以及能力分阶段诊断。
4. 在独立连续研究项目上的有限验证及可复用开源 harness；应用展示不是替代 benchmark 的证据。

不能仅凭“换到 research 场景”或“加 LLM judge”宣称创新。须与自动 agent/harness 设计、反馈优化、科研 agent benchmark 逐项比较，验证任务确实对 harness 设计敏感。

### 2.2 核心 RQ

- **RQ1 构建：** 固定外层 builder 环境与执行模型时，哪些 builder 能构建有效的统一 harness？阶段表现和质量—成本如何？
- **RQ2 演化：** 限定改进轮次的反馈驱动修改，相对不修改以及固定 harness 的多次尝试/顺序修正有何收益？逐轮评价未见任务表现，并记录外层累计成本；同轮次不等于同算力。区分内层执行预算与外层演化成本。只改 prompt、独立重建择优是回答其他归因问题的候选补充，不能替代 test-time scaling 对照；初始质量与演化收益能否分离？
- **RQ3 泛化：** search 上的改进能否迁移到未见研究家族？是否只是更迎合评分器？
- **RQ4 成本：** 外层构建/演化、内层执行、评分及人工建设各花多少；不同预算下排名是否稳定？
- **RQ5 整合（补充）：** 阶段任务收益能否在真实串联流程中保留？跨 executor 迁移可作资源允许时的补充，不是第一版必做全部矩阵。

允许出现负结果：无可靠演化增益或排名对 judge 敏感都可报告。不能从某蒸馏模型演化弱推出“只学皮毛”的训练因果结论；没有受控训练对照时只讨论可观察表现与替代解释。

## 3. 四模块契约 [已定边界；评分细节待冻结]

“模块”是研究阶段任务接口，不是对 harness 内部 planner/memory/agent 数量的规定。每模块都准备 **固定输入包、输出规范、私有评测证据包和 verifier**。不把复合任务的总分拆给内部组件做因果 credit assignment。

### 3.1 LIT：文献调研与问题定位

| 项目 | 约定 |
|---|---|
| 输入 | 明确研究问题，不预设方法或结论；资源约束；评测方控制的检索/阅读工具 |
| 输出 | 已有研究与方法；证据与局限/冲突；尚待解决的具体问题。关键判断须关联文献版本与支持位置 |
| 不负责 | 不要求提出新的解决方法，不要求从无限学科范围自主选方向 |
| 评价 | 事实/引文支持是否准确，重要研究与证据覆盖，所提缺口是否成立且具体 |
| 私有材料 | 审核过的关键事实—原文对应、覆盖点、已知争议/易错点；不是封闭的唯一引用名单 |

检验引用存在、版本和定位可程序化；原文是否支持论断、缺口是否有价值主要依赖内容评审。清单外有效文献和不同合理缺口不得自动扣分。对“没有人研究过”的断言只能在明确检索范围内评价，不保证全球新颖性。

**LIT评分规则 [已确认，具体锚点与实现待验收]：** 四维分别为①事实与引用准确性；②关键研究与证据覆盖；③比较与综合分析；④问题/缺口定位的合理性。各维0–4，等权由程序汇总，成本另报，不按引用数量或篇幅奖励。私有覆盖依据是重要研究脉络、事实与争议，不是唯一必引论文清单；不同文献提供同等有效支持应认可。缺口须由已有证据推出、具体且考虑已有解法，不要求重现原论文缺口，不保证全球无人研究。程序检查文献身份、版本、时间和定位；judge读取对应原文，核查支持关系和比较公平性。虚假引用、引文不支持论断、关键遗漏导致错误缺口等按影响范围降低相关评分并标记，不因单条小错全篇归零。已有旧版开发实现及轨迹；新原生judge的锚点、取证与prompt须按§7.2重新验收。

**历史访问约束 [已定；LIT-R2为当前唯一方案]：** 各材料包收集强相关、弱相关及易混淆真实背景文献，去重后形成全局共享文献库；模型可自由查询该库，但不访问开放互联网，不限定每题专属书单。底层search/read对搜索返回、摘要及正文统一执行每任务cutoff、版本和目标排除规则，检查跨split答案暴露；仅纳入允许公开的背景文献，不混入题面、目标答案、阶段产物及私有评分材料。检索结果不公开材料包归属/相关性标签，保存实际检索与阅读证据以便重放。评测环境限制浏览器/终端/HTTP绕行。截止早于目标最早已知公开版本，核查arXiv v1、技术报告、项目/代码披露，未知标待核验，不能仅用会议日期。当前8篇开发库不是合格的全局语料覆盖；R2构建及过滤尚待实施/验收。

检索范围不能只剩维护者挑选的答案相关几篇。保存实际返回的文献版本、片段、摘要及必要检索元数据以供审计/重放；禁止后续版本内容、后向引用信息和搜索摘要泄漏。原论文参考文献可辅助建设私有覆盖依据，但不能直接成为solver唯一可搜列表。方法/目标标题更名不解决模型参数记忆，只是污染诊断手段。

**文献分层与检索记录 [方向已定，公式待冻结]：** 按任务私有标注核心相关、补充背景、易混淆近邻三类；旧8篇不是全部必引gold。同篇文献对不同任务角色可不同。检索返回、实际阅读、最终采用分别记录并按身份/版本去重；核心覆盖可机械检查，合理对比近邻和名单外有效文献不得自动扣分。相关性及引用支持仍需语义核查；具体指标权重和是否进主分待pilot，不擅改既有四维汇总。

### 3.2 IDEA：idea 构思与可检验假设生成

| 项目 | 约定 |
|---|---|
| 输入 | 审核过的 LIT 风格报告：研究问题、已有方法、证据、局限和候选缺口；数据/工具/预算约束 |
| 输出 | 一个选定的研究提案：切入点、具体核心 idea、与已有工作差异、可检验预期；**一组覆盖提案核心主张的假设** |
| 决策空间 | 在题目问题范围内选择、细化或有依据地质疑候选缺口；内部可探索多个候选，最终提交一个提案 |
| 不负责 | 不需要重新检索完成整个 LIT，也不要求完整实验方案/代码；额外文献访问权限若开放仍受 cutoff 控制，具体额度待定 |
| 评价 | 依据、研究价值、实质差异、具体性/自洽性、在给定约束下的可行性；假设覆盖性、明确性、可检验性及与研究问题的一致性 |

假设生成 **已并入 IDEA**，不再另设模块。性能提升、组件贡献和机制解释应能区分；性能提高本身不证明机制。可接受不同假设结构，不以重现原论文主张为唯一答案。

假设需让评审理解条件/对象/参照/预期及可能挑战它的证据；具体实验和统计方案留给 EXP。不得把复杂主张替换成无意义但容易验证的弱命题获取高分，也不能只覆盖提案中最容易验证的一部分。

主评分使用本模块的 LLM judge，不引入人类专家评分或专家校准；不是已证明可靠的 oracle。选定子集可用固定后续执行流程检查 idea 评分与落地的关系，但执行成败还受 executor 和资源影响，不能当纯 idea 真值。

**IDEA评分细化 [已确认，具体锚点与实现待验收]：** 五维为研究依据与价值、实质差异、具体性与自洽性、可行性、假设质量，各0–4等权汇总。差异可来自方法、分析发现或数据设计，不要求复现原论文idea；只在给定背景及可核查知识范围判断新颖性。假设须覆盖核心主张，不能以性能提升替代机制证明；后续负结果不自动说明idea差。遗漏或矛盾按影响范围反映在相关维度，不让漂亮文字掩盖问题。分别记录harness执行、judge评测、builder构建/演化消耗，不混进科研质量分，也不等于提案预计实验经费；提案资源可行性仍在可行性维度评价。旧版开发实现与单例轨迹不代表验收；原生judge迁移后按§7.2重新验收，重点检查区分度。

### 3.3 EXP：假设检验与实验研究（大模块）

| 项目 | 约定 |
|---|---|
| 输入 | 审核过的具体假设集合、研究提案的必要语境、可用材料/环境/工具、资源约束；不是上一题实际产生的任意弱假设 |
| 自主过程 | 联合设计实验与判断规则，实施/调试/执行，安排对照或消融，分析证据；内部可以迭代，不强制某一流程 |
| 输出 | 对每条输入假设的结论和不确定性；实验方案、代码、配置、运行产物、分析与证据关联；未做事项/偏离说明 |
| 主评价 | **LLM judge 使用泛用 rubric 评价整个实验过程及结论**，不要求预设一套固定科学 unit tests，不拆成独立设计/编码/分析榜 |

**起始代码与环境 [已定，待构造/验证]：** 提供已验证能跑通的数据加载、基础训练/评测代码及必要baseline；提供新方法核心说明与固定假设，但不直接提供新方法完整实现。agent负责实现新方法并自主组织实验。材料pipeline需要分离基础设施与目标实现，审计残留泄漏，并验证分离后的起点可运行；不能原样交付完整作者仓库，也不能把“baseline能跑通”当作完整实验方案已经确定。

**方法忠实性与输入准确性 [已定]：** 被检验方法不能改变。材料必须提供准确、互相一致的研究提案描述与假设集合，使executor能理解方法及其原意；这不是只有几句概括的idea标签。构造时须核对方法定义、符号/条件、假设所指对象与提案对应关系，不让executor靠猜测补齐会改变方法含义的缺失信息。非唯一的实现细节不能成为暗中要求复刻作者代码的理由；但实现自由度不能改变方法语义或被检验主张。因材料歧义/缺失导致无法忠实实现，按材料问题处理，不能直接归为模型科研失败；具体判定流程待定。说明清楚方法不等于给出实验方案、结果或结论。

**分析型研究兼容性 [已定边界，具体任务规格待讨论]：** 上两段“新方法/目标实现”是方法提出型任务的条件，不应成为所有研究项目的准入要求。共同输入为准确的研究提案、假设、研究对象/条件和材料。对方法型，另有被检验方法说明；对分析型，可以给被研究的既有模型/算法/数据资产而不虚构新方法。固定研究对象与问题不等于替agent固定验证它们的实验程序；分析/探针/干预的设计与实现仍属于EXP的自主空间。既有模型完整实现可以作为输入，不受“不给新方法实现”这一局部规则禁止，但泄漏目标结论/原作者完整分析方案的脚本仍需按任务审计。方法优势/组件贡献不作为每题必需字段或评分项，无需新增研究模块。此决定不自动纳入纯理论证明或没有可评证据条件的所有论文。

**任务范围与多任务派生 [已定原则，待材料验收]：** 一项EXP可对应论文中的一个完整、自足的研究问题及其核心假设集合，不要求覆盖整篇；限定范围必须同步反映在提案与假设中，不能保留广泛主张却省去关键验证。一份论文材料可派生多个有实质不同问题的EXP任务，不机械拆表格数字凑题。相互依赖的研究内容用经核实的固定上游背景表达，不依赖前一题agent实际输出，也不能提供本题需检验的结论。同论文派生任务须同split，统计仍考虑论文相关性；聚合已按§8确定，样本量和重复次数待pilot。

**交付边界 [已定原则，字段待细化]：** EXP不要求另写研究报告或论文式叙述，表达/组织能力留给WRITE。agent提交实际研究产物并记录假设与实验的配对映射；原有“对假设形成结论”的目标仍保留，可用简短结论/不确定性及结果定位表达，而不扩展成独立报告要求。映射允许多对多，必要实验设置由代码/配置/记录指向，不重复抄成长文。平台执行记录用于核查，不由agent自写叙事代替；未检验假设应显式标记。具体字段未冻结，judge评价研究证据与判断而非文采。

**资源与数据的通用框架 [已定方向，具体配置待任务实例化]：** 用户进一步指出数据构造本身可以是研究内容，不能将固定数据池或普通训练/验证/测试划分设为所有EXP的统一前提。benchmark提供与研究问题匹配的起始资源、工具及必要条件；数据可作为输入，也可成为需要构造和验证的研究产物。数据获取、生成、筛选、划分与扰动可属于agent的研究决策，是否合理由假设、任务必要边界及证据质量判断，不预先逐项禁止或替agent定好方案。数据池只是可选资源配置，不是普适限制；具体外部访问、许可、资源预算与隐藏评测权限仍由任务和平台明确，不能把此处解释成无限联网或放开隐藏答案。共同框架统一输入/产出/证据和评价原则，不统一实验配方；任务特有约束须有科学有效性、可比性或可复核性依据，避免过度规定。

通用 rubric 的候选维度：

1. **检验有效性**：是否真的回答输入假设，是否有区分竞争解释的能力。
2. **严谨性**：对照公平、数据隔离、混杂处理、不确定性、选择性报告与实验偏离。
3. **执行可信度**：真实运行，代码/配置/数据/记录对应，可复算关键量，不把口头计划当完成实验。
4. **结论可信度**：结论范围与证据相称，承认反例、局限和不确定性。
5. **资源合理性**：遵守预算，在预算内有效获取证据而不是只生成形式化材料。

五维已定，前四维等权汇总科学质量、资源维度单列；judge模型见§0.2。具体等级锚点与错误处置仍需验收。LLM judge 依赖可信 trace 与必要程序检查，不能只读 agent 自写报告。内层自己制定的判据也是被评对象，不得拿来充当外层 benchmark 的最终打分器。

**正负结论都可得高质量分，但不做实验、对所有假设都说“不确定”不能自动得高分。** 需评价预算内应获得而未获得的有辨别力证据。结果为负与实验无效必须区分；科学质量和方法性能改善分开记录，科学质量按§7.5及§8固定规则汇总。

### 3.4 WRITE：论文表达，两类任务

**任务粒度 [已确认]：** 用户认为五/六项过于细碎，现收敛为下列两类；旧W1–W6不再作为当前任务分类。任务少而完整，评分可以细致。不以一次生成完整PDF再整体打分作为唯一测量，也不按intro/method等章节继续分榜。各任务使用独立标准输入，统一harness执行；真实任务仍须通过覆盖矩阵和材料验收，不要求每篇论文支持两类。

| 类别 | 必需输入 | 交付产物 | 评测依据与材料门槛 |
|---|---|---|---|
| 研究内容写作 | 审核过的研究事实、主张与证据、方法/实现/配置及固定文献背景，按指定写作范围提供 | 一段完整、自足的论文内容，按任务需要含论证、方法、引用、技术/复现细节与局限 | 科学含义、论证、技术与引文忠实性；不能由原文改写输入再按相似度找回原文。代码与论文须核对，不要求新造理论证明或开放文献搜索 |
| 实验证据呈现 | 原始逐运行数据或明确标为汇总的结果、指标/单位定义、必要研究语境和呈现要求 | 配套图表、图注、结果说明与生成代码 | 数值复算、代码/图表一致性、标签/聚合/误差条检查及内容/视觉评价；只有均值时不能要求重建不存在的重复实验与误差条 |

引用准确、技术忠实、透明性与复现说明是相关任务的要求，不分别设独立小评测；审批/许可/算力等未知信息须如实标缺，不能编造。“审计与修订”暂不作为必需的独立评测，未纳入当前两类主规格。若以后讨论恢复，须另行确认，且区分自然错误与人为注错。

**WRITE评分 [已确认，分类规则与实现待验收]：** 两类共用四个维度名称，各0–4等权汇总，成本另报；但用户明确要求区分两类具体规则，不能混用通用prompt或相同检查清单代替分类设计。分别准备任务类型对应的rubric、等级锚点、证据读取/程序检查规则及judge prompt配置，并各自按§7.2逐轨迹验收；可共享基础设施，不要求使用不同模型。

| 维度 | 研究内容写作的规则 | 实验证据呈现的规则 |
|---|---|---|
| 准确与忠实 | 方法、主张、引用符合给定材料，不夸大 | 数值、统计、图注与结果说明一致，不误导 |
| 必要信息完整性 | 指定范围内的关键定义、依据、条件与局限不遗漏 | 必要的指标、单位、对照、统计口径等交代清楚 |
| 组织与可理解性 | 论证连贯，使读者理解研究内容 | 图表选择、布局、标注清楚，便于正确比较 |
| 可追溯与可核查性 | 关键表述可对应来源材料 | 呈现可对应数据和生成代码，关键数值可复算 |

完整性只针对任务范围和实际给定材料，不要求补造不存在的信息。程序检查提供事实依据，judge判断科学表达；代码可运行、图表能生成不自动等于高分。严重失真按影响范围处理并标记，不用文风/美观补偿错误；不按与原论文措辞/排版相似程度评分，不强制特定写作风格。分类锚点、prompt及运行实现尚未验收。

WRITE 不重新发现科学结论。EXP 测“取得并解释证据”，WRITE 测“把既定研究表达准确、完整、可复核”。不能要求通过写作补齐根本未做的实验。原方法代码在技术写作任务可合法作为输入，在 IDEA 可能是答案泄漏；可见性必须按任务配置。

会议指南仅是维度来源，不是统一金标准：NeurIPS checklist 关注主张、局限、复现与统计报告；ICLR 作者指南有复现说明；ICML 定稿说明含参考文献/材料/格式等。固定使用的年份与规则版本，不把不同会议的必需/建议项目混成全部强制项。注册、付款、署名审批等行政事务不作为研究能力测量。表格能生成/LaTeX 能编译不代表科研质量高。

## 4. 材料来源、覆盖矩阵与任务建设

### 4.1 主体来源 [已定]

- 三大会主会录用 AI/ML 研究项目，优先作者关联公开代码。主体是论文、代码、数据、配置、附录等原始材料，不是拼接上游成品 benchmark。
- 录用/公开仓库只作初筛；材料完整性、权利、可运行/可评性和资源需求决定任务准入。公开不等于开源许可明确；平台许可不自动涵盖所有关联资产。
- OpenReview 分数可作同会议同年份内的分层信息，非默认高分硬门槛，不可跨会议年份直接比较；缺失不补零。评分获取不是开始材料检查的前置条件。
- 优先 ICLR 2025 pilot，不继续无目的搜散源。其他来源仅在主材料池出现具体缺口时补充。
- 原作者结论与实验方案是参考证据，不能假设每条主张都被充分证明；方案和表达可以有多个正确解。
- 目标总体明确限于这套采样规则下的研究项目。录用、公开代码、材料完整与算力可承受的筛选会带来成功研究/可复现性/低成本偏差；不能外推到所有 AI/ML 研究。报告每层筛选数量与原因，保留未通过项目的覆盖记录。

### 4.2 覆盖矩阵 [已定原则；结构候选]

行是研究项目/关联家族；列是 LIT、IDEA、EXP、WRITE研究内容写作、WRITE实验证据呈现。每个 cell 记录：`status`、需要/已有/缺失资产、来源定位、构造成本、许可/运行/证据/泄漏审核、未通过原因。建议状态为 `unknown / candidate / blocked_material / blocked_rights / blocked_runtime / review_needed / ready`；它们是数据准入状态，不是模型成绩。

双向筛选：

1. 从候选规格调查材料可获得率；若绝大部分项目无法支撑且人工补齐不具可扩展性，放弃/缩小该小评测，而非硬造 gold。
2. 某论文不支持某项，则不生成那一项；保留它在其他项的可用材料。**不要求同一批论文支持所有模块，不立即整篇删除。**
3. `unknown` 不记为已证实缺失；手工派生/重跑生成的材料需单独标记来源与费用，不能当作者原始记录。
4. 在正式模型运行前冻结准入和任务集合，禁止看模型成绩再选择保留任务。
5. 所有被测模型执行同一冻结任务清单；结构性缺项不算模型失败，已纳入任务上的模型失败要记分。

保持可见的四个规模：发现项目数 → 材料合格项目数 → 任务验收数 → 家族去重后的独立数量。更多切片不创造更多独立研究。现阶段不继承 TB 的 20/50，也不先拍定各模块数量；“够不够”依据 pilot 方差、可检测差异、成本及家族覆盖决定。

### 4.3 每任务的建设顺序

确认规格 → 固定源材料与版本/权利 → 统一语义材料与来源定位 → Codex构造阶段输入及包级CPU Docker环境/资源契约 → 独立上下文对照原始来源审核 → 程序检查/时间与答案泄漏审计 → 真实运行及成本pilot → 返修或淘汰 → 覆盖矩阵验收 → 按源论文划分并冻结。先少量异质论文试产再批量，构造者不能自行宣布科学验收。

对于开放问题，只能逆向构造“合理研究情境”，不声称还原作者的历史思考过程。不能把目标新发现或方法特有关键词提前作为背景提示。正式 LIT/IDEA 的背景需有截止前独立证据；仅由目标论文首次提出的观察不能伪装成早已知道的事实。

## 5. 统一格式与安全边界 [已有开发实现，Docker版本待验收]

保持原始文件，不把PDF、代码、表格粗暴变成同一种文本。统一的是身份、版本、语义、权限、关联与验收。已有开发schema和白名单导出，不等于新Docker环境协议已验收；旧自然科学schemas不恢复。

| 对象 | 最小内容 | 可见性 |
|---|---|---|
| MaterialPackage | project/family/source ID；论文版本/首次公开时间及证据；每资产 URL/commit/hash/角色/许可；代码—运行—图表—主张关联；缺失与验收状态 | 维护者，非整体给 solver |
| TaskSpec | task ID、模块/子评测、family、材料版本；标准起点、允许行动、预算、输出契约；评测与发布规则 | 主规范，分导出 public/private |
| TaskView | 题面、白名单输入、工具接口、资源预算、公开评分维度、返回格式 | 当前 executor；search 反馈按外层规则给 builder |
| EnvironmentSpec / ResourceSpec | 材料包Dockerfile/锁定依赖/镜像digest/资产挂载白名单；包级CPU、内存、存储、进程、时限及工具/网络权限；必要的显式任务覆盖与预检证据 | 配置分公开执行信息与控制器私有记录；不得把答案烘焙进镜像 |
| EvaluationEvidence | 参考证据/隐藏标签、校准例、评分锚点、verifier/judge 版本、私有定位/缺陷表 | 独立可信评测服务 |
| Submission + Trace | 交付产物 hash、claim/hypothesis→evidence ID；环境侧模型调用/工具/代码运行/数据配置/退出状态/预算账本 | 提交产物不可信，平台 trace 为外部证据 |
| RunResult | 状态、各维度分数与证据定位、违规/基础设施/模型失败分类、成本、harness/executor/judge/task 版本 | search 按策略反馈，隐藏结果不回流 |

每任务角色化定义可见资产。原论文或原算法既可能是答案泄漏，也可能是合法输入；同一家族的所有任务、资产和变体仍须处于同一 split。给 JSON 字段命名 private 不是安全隔离。

原始测量、汇总量、插补、模拟、人造缺陷与作者报告分开标记；缺失不是零。所有 hash/commit 只在实际取得后填写，默认分支下载 hash 不等于已锁定论文时版本。

## 6. Builder/harness/executor 与混合演化协议

### 6.1 三个角色 [已定]

1. **Builder/evolver：** 被测开发模型，在固定外层开发框架下构建/修改统一 harness。
2. **Harness：** 可编辑的控制逻辑、prompt、上下文/状态策略、验证、调度和工具编排。可内部多 agent/多模块，但交付同一个版本。
3. **Executor：** 主实验固定的执行模型，受 harness 驱动完成阶段任务。内层产物（solver、图表、论文）不是外层 harness 本身。

评测器、模型调用/预算 broker、隐藏材料和系统权限由 benchmark 控制；builder 不能修改。主实验只改变 builder 模型，不随 builder 替换 executor 或扩大预算。

现有开发接口：`run(task_view, model_client, tool_client, budget) -> submission_manifest`。已有SDK与手写开发baseline；正式Docker执行和任意生成代码隔离尚未验收。禁止按已知隐藏 ID 返回缓存答案；通用路由允许，但测试题身份/目标论文不能从维护者目录获得。

### 6.2 正式主流程 [原则已定；数值待冻结]

1. 固定外层开发环境、初始骨架、executor、任务接口、工具权限、内层任务资源约束及外层改进轮次上限。外层演化费用以完整记录为主，不设置研究协议上的硬预算停止条件；具体轮数待冻结，一轮流程如下。
2. **[已确认]** Builder只看统一构建prompt、规范、接口示例和公开smoke构建H0；提交H0前不开放正式search任务、运行轨迹或性能反馈。固定H0快照后才开放search用于演化。调试样例不得变成未计费的正式科研优化集，其具体内容和额度待落实。
3. **[已确认]** H0提交后先在完整混合search set上评测；一轮定义为上一版本search反馈→builder修改共享harness→提交冻结新版本→完整search重评。各轮使用同一完整search集合，不自行挑选正式评分题目。修改时可检查代码和调试，但不能把额外正式search评分调用藏在一轮内部；调试接口与正式评分访问的工程隔离待落实。不是按能力单独演化一套系统。
4. 每轮保存不可变版本H1…HR、diff与成本（H0单独保存）；达到轮次上限停止。可依据search反馈回滚，回滚作为本轮提交记录；不要求每轮改代码或涨分。提前停止/异常终止的曲线处理待定。Builder在看不到test结果的条件下从已提交版本选出其自认为最好的H_builder，并冻结选择记录。
5. 在隔离环境对H0及每轮冻结版本独立执行各模块隐藏任务；每题清空可写状态，禁止跨隐藏任务学习或共享测试反馈。
6. **[已确认]** 所有版本在同一隐藏test集合上评价，绘制完整逐轮性能曲线；隐藏成绩、轨迹与feedback不回流builder，不用于继续修改或影响其版本选择。可隔离异步运行或演化结束后统一离线运行。报告累计外层成本对应的质量曲线、分阶段表现与退化，逐轮test费用单独计账。
7. **[用户确认三版本主汇报]** 同时报告H0、builder自选最好版本H_builder、隐藏test上最好版本H_test-best，不将HR作为唯一主结果；HR仍保留在曲线中。H_test-best是事后test-oracle统计，明确披露使用test选择，不能冒充builder可实际选出的最终版本或无选择偏差的泛化估计。**已定选择规则：** 从H0…HR按§8预先固定的四模块等权总质量分选择，完全同分取更早版本；选择一个统一harness，不拼接各题/各模块最好版本。H_builder仍由builder结合search可见信息自主选择，不强制等于search总分最高版。此前“不按隐藏表现选版”限制的是builder决策与部署/无泄漏性能声明，不禁止此项显式事后分析。

任务内写代码、修 bug、重做实验是执行行为；任务间修改统一策略才是外层演化。正式生成/演化必须在第一版任务范围与混合 split 冻结后开始，不能先围绕一个来源优化再追加其他正式来源。

### 6.3 Prompt 契约骨架 [候选，不是冻结 prompt]

**H0 prompt来源 [方向已定，参考归纳和开发prompt已有，真实H0未成功]：** 可以参考一个或多个较完善的research harness，由独立subagent阅读并归纳成足够自包含的统一构建prompt，使全新agent能据此构建支持本benchmark整个评测过程的harness。多个参考可提供互补能力，不要求每个参考单独覆盖全部需求，也不因参考多个系统而为不同builder提供不同prompt。不是继续凭空手写完整需求，也不直接把参考代码作为各builder的H0。须检查固定阶段起点、统一接口与工具/预算边界的适配；“autonomous research”名称不等于满足全部任务。区分必要能力/接口与参考实现，不把复刻特定内部架构当唯一正确答案。参考归纳见`research/benchmark/reference_harnesses.json`及`prompts/builder_h0.txt`；全新agent构建曾因运行权限失败，正式prompt与接口须在修复后审核冻结并统一提供。全新agent只拿发布输入，不继承本线程或维护者目录。H0阶段不看search任务及反馈已确认，见§6.2。

**Builder：** 交付一个能从给定阶段起点执行任务的统一 harness；使用注入的 executor/tool/budget 客户端；说明入口与依赖；内部结构自由；不得访问维护者材料、更改评分器或调用未授权模型。规范提供模块 IO、公开 rubric、资源边界和格式 smoke，不提供目标方法/gold。

**Evolver：** 基于上一版本完整混合search反馈改进共享代码，在限定轮次内提交冻结版本并接受同一search集合重评；记录成本、修改和回滚依据，不在轮内追加未登记的正式评分。外层费用记录而非硬预算停止。每轮版本均交隔离test，结果不回流；结束时仅依据search可见信息选择H_builder，维护者另行统计test-best，不给隐藏失败轨迹或暗示某种结构一定优越。

统一 prompt/工具权限跨 builder 保持一致；prompt 内容、提供哪些文献/反馈、是否允许额外检索、版本选择方式，均需在正式实验前固定。

**Search/test隔离 [用户再次明确]：** 演化/改进期间builder仅能看到给定的search任务部分，各轮冻结harness在其余隐藏test任务上评价。沿用研究家族隔离，不能把同论文派生任务随机分两边。隐藏test题面仅在冻结harness执行相应任务时提供，不向外层builder开放题目、轨迹或反馈。最终汇报H0、H_builder与事后test-best；后者不回流演化或影响builder选择。

**Search反馈范围与双产物 [已确认；实现待验收]：** Builder可见search任务和允许输入、自身运行轨迹/代码/产物、主分/维度分、失败或违规状态及成本；不可见隐藏test、其他被测builder解答、私有参考答案和评测材料。Judge体系生成两份明确分离的产物：①内部评分/审计记录，包含完整判分依据、证据、私有参考核对、问题与不确定性；②builder可见的改进feedback，定位公开证据中的行为问题、证据位置、受影响要求和可迁移的改进关注点。不能直接公开内部评语，不能把私有内容换种措辞当安全反馈；不泄漏标准答案，不规定必须采用某种agent架构或直接替builder写修复代码。单次执行缺陷不自动证明harness的具体根因，须区分已观察事实与可能原因，由builder决定如何修改。**[午间最新决定] 同一次原生Codex judge评审同时产出内部评分记录与可发布feedback，不另设feedback agent或独立反馈调用。** Prompt明确区分两份产物，benchmark发布层按字段白名单导出允许分数及feedback，完整judge轨迹/私有理由不回流builder。因judge读过私有材料，输出分离不等于上下文隔离；反馈须定位executor可见证据中的问题，不泄漏私有内容及答案，需专门进行来源/泄漏检查与逐轨迹验收。两份产物均纳入逐轨迹验收：评分是否有依据，反馈是否定位问题、瞎归因、泄漏答案或代做改进；相关费用计入账本并与对照对齐。该同次评分+feedback新方案待实现，旧分开调用仅保留历史记录。

## 7. Judge、验证器与 debug/audit 设计 [需完成的校准工作]

### 7.1 评分哲学

开放式研究主要用 LLM judge + 通用 rubric，不强行把所有科学判断变成硬测试。程序检查提供可验证事实；它不能替代科学有效性，也不能被漂亮报告覆盖。原作者分数、目标论文、单个 LLM judge 均非绝对真值。

公开维度和输出要求；私有证据/校准案例/隐藏结果不交 builder。每项 judge 输出应包括维度分、支持定位、适用范围、分歧/不确定与无法核查项，而不是只给一个印象分。科学无效、伪造记录或违规的处理规则须单独预注册，不能简单加权后被文风抵消。

### 7.2 校准后才能用于正式排名

- 准备参考有效、真实负结果、等价表达、表面漂亮但无证据、数字篡改、错误对照、虚假引文、预算违规、全盘保守不实验等校准例。
- 不引入人类专家评分/盲评/校准。各模块分别使用自身 rubric 与 LLM judge；以证据可核查的正反例、程序检查及重复评分稳定性检验评分器，具体方案待细化。受控案例上的检查不能外推为所有开放研究判断均准确。
- 控制长度/文风/模型名称/答案顺序偏差；固定 judge 模型版本、prompt、温度、证据选择与重试策略。多 judge 是待比较的配置，不是“多模型投票就可靠”。
- 限制 rubric 迎合：检查编造证据、提示注入、“请给高分”等不可信文字；judge 只读冻结产物，不执行被测代码或服从论文指令。
- 长 trace 的压缩/抽样策略本身要审核，不能只让 agent 自选最漂亮片段；摘要需能回指可信事件。
- judge 模型/阈值若依据 pilot 修改，冻结新版本后对比较对象统一重评，不只重评有利的结果。校准失败的评测降为探索性或暂缓，不为凑四模块强行发布。

**所有模块judge的小样本逐轨迹验收 [已定；旧例有审阅，新版仍需验收]：** LIT、IDEA、EXP及每个保留的WRITE小评测，在设计/修改实际prompt与judge harness后，必须先在少量开发样例上运行（几条即可起步，具体数量未冻结）。主agent或受委派的subagent必须逐条直接阅读被评执行trajectory、相关输入/产物，以及judge自身的取证、工具调用和判分记录，核对其实际行为与评分标准符合预期；不能仅查看最终分数、自动通过率或judge自述就宣告验收。核查至少包括是否读到关键证据、是否漏看反证/未完成项、是否擅加要求、是否正确区分失败/证据不足/不适用，以及判分理由和汇总是否遵守协议。问题需修正后复测，再逐条复查；保留样例/版本、证据定位、发现的问题与通过/未通过记录。影响取证或判分的prompt/harness变更需重做相关验收。本要求是评分器工程验收的必要门槛，不是引入人类专家评分，也不把少量样例通过当作全局科学判断可靠性的证明；样例不得来自回流给builder的隐藏测试轨迹。旧开发样例已有逐轨迹审阅，缺陷见§11；新prompt/工具/环境的受影响部分必须重验。用户已授权独立subagent协作，不等于批准跳过验收。

### 7.3 Debug 与审计产物

每次运行绑定：builder run/seed、harness hash、task/family/split、输入 manifest、executor/judge 版本、模型调用、工具参数与结果、代码快照、数据/配置、运行开始结束与退出码、产物 hash、预算、评分与理由。不得只相信自报 GPU/耗时或自造日志。

反馈失败类型至少区分：材料/基础设施失败、接口/格式失败、执行失败、科学证据不足、预算/权限违规、评分器故障；平台故障按冻结重试规则处理，模型失败不能静默丢样本。重试仍记资源。

工程 smoke：接口契约、序列化、无效产物、超时/空输出；评分器正反例；权限越界/目标答案检索；同版本重放与哈希核对。可用受控注错检查 verifier，不把所有自然科研错误简化成人工注错。

debug 只在公开开发/search/校准资产开展；隐藏失败轨迹不得带回当前 builder。维护者修订数据和人工干预全部留痕，冻结后不能看模型输出选择性更换难题。

### 7.4 EXP judge 定向文献调研（2026-09-22，已核来源，未复现）

用户明确要求subagent调研后再细化。独立 `research_judge_survey` 查科研类judge，主agent补查通用可靠性并复核关键主源。以下是来源事实，不是本项目已采纳配置；部分工作有人工验证，如实说明，但不改变本项目不引入专家评分的决定。重点2025–2026，另补一个2024年的直接相关架构先例。该历史调研本身未做来源系统复现；本项目后续旧judge运行状态见§11。

| 工作/核查位置 | 实际设计及证据范围 | 可借鉴点与不能照搬之处 |
|---|---|---|
| **AstaBench / E2E-Bench**，ICLR 2026；[v2 PDF](https://arxiv.org/pdf/2510.21652v2)，2026-04-21，E.9/F.9/Fig.10 | 每条任务rubric分报告、代码、产物判断满足/失败/无证据，再核一致性。人工小样本抽检不等于通用可靠性证明；Faker未实际做研究仍获部分分 | 借鉴分源核对，但以我们的映射替代报告，加入平台证据；三份自报材料一致不证明真实执行 |
| **Asta 官方实现**：[固定 task.py](https://github.com/allenai/asta-bench/blob/bfd4878250dbbcbf3c0554592bd1cb449800ff93/astabench/evals/e2e_discovery/task.py)，`check_rubric`、`evaluate_rubric_question` | 读取report/code/artifacts，trace注明不用于评测；每rubric初评加reflection两次调用，不是三个独立judge；产物文本有截断 | 不将其说成独立重执行或完整trace审计。原实现的取证/汇总规则不是我们的默认配置 |
| **MLR-Bench**：[v2 §2.1/§4](https://arxiv.org/html/2505.19955v2)，2025-07-01；[固定EXP grader](https://github.com/chchenhui/mlrbench/blob/0a8fd3418be9a26da4edbc8aaddd6b27e10bbd0a/mlrbench/evals/review_experiments.py) | EXP看coding执行日志，以通用维度及独立Overall评分，另标幻觉；论文用两个judge。人类对齐主要验证最终论文，不是专门验证EXP运行真实性 | 可借鉴提案一致性、完整性、严谨性；不直接迁入新颖性/重要性以免混入固定提案质量。读日志不等于独立核查全部代码与真实执行 |
| **PaperBench**：[v1 §2.2–2.4/§4/App.D](https://arxiv.org/html/2504.01848v1)，2025-04-02 | 区分代码开发、执行、结果匹配；独立复现阶段及逐叶项judge，按需选择相关文件；JudgeEval以人工标注验证且仍有误差 | 借鉴实现/运行/结论为不同断言，及独立核查；不照搬复现作者数值、细密固定结果树或人类标注路线 |
| **ResearchRubrics**：[v1 §3.3–3.4/§4.3](https://arxiv.org/html/2511.07685v1)，2025-11-10；[官方grader](https://raw.githubusercontent.com/scaleapi/researchrubrics/main/src/evaluate_rubrics/evaluate_single_report.py) | 对报告的任务特定正负rubric；比较二元和三元满足度，当前公开实现二元且支持分块取证 | 借鉴细化可核查条件、证据定位；报告评价不能证明科研运行真实性，二元在其任务较好不意味着全部科学质量应二元化。实现main为本次读取快照，未pin |
| **RuVerBench**：[v1 §3.2/§4.3–4.4/App.A](https://arxiv.org/html/2606.29920v1)，2026-06-29 | 分别评报告和序列化coding轨迹上的单条rubric；过滤不可核查/多条件混合项。发现局部满足误当全部满足、擅加要求；批量判条目有成本/精度权衡，自投票收益递减 | 借鉴条件适用性和judge本身的分项诊断，不默认一次塞全部rubric，也不默认增加投票解决系统偏差。其标签来自人工，性能不外推到我们的EXP |
| **Agent-as-a-Judge**：[正文 §4/App.K](https://arxiv.org/html/2410.10934)，2024先例 | 用文件定位、读取、结构信息与轨迹检索支持逐要求判断；并非所有规划/记忆组件都改善效果；在DevAI上做消融及人类对照 | 借鉴按需主动查证而非只读最终答复；不照搬整套复杂agent或宣称能自动解决开放科研评判 |
| **JETTS**，ICML 2025：[v1 §3–4](https://arxiv.org/html/2504.15253v1)；**Rating Indeterminacy**，NeurIPS 2025：[v4 §3](https://arxiv.org/html/2503.05965v4) | 前者分别测reranking、搜索与反馈改写，显示静态judge成绩不充分代表下游效用；后者讨论强制唯一评分掩盖合理歧义 | 分清评分可靠性与演化反馈效用；不要用稳定输出掩盖无法判定。仅借鉴原则，不将其结果当我们无专家路线的验证 |

排除误用：ScienceIDE本次核查主评价为数值verifier，不作为LLM judge主例；同名ResearchBench不能不区分工作就引用。MLR已有v3，本次EXP细节引用明确用v2与固定代码，不混作所有版本相同。调研优先找可用机制而非比哪篇最新。

### 7.5 调研后的 EXP judge 设计（总体结构已确认，具体配置待冻结）

**核心方向：通用研究质量rubric + 明确的任务语境 + 按需取证。** 更细致是把判断依据与错误处理说清楚，不是替agent预写实验方案。保留五维框架，不新增EXP研究报告、不要求人类专家、不统一所有任务的数据/实验配方。

#### A. Judge输入与权限

- 可信输入：固定提案、完整假设集合、必要任务边界、起始资产说明、评分规范；原论文衍生参考仅作可核查背景，不是唯一正确实验或结论。
- 被评输入：轻量假设—实验—结果—结论映射及实际代码/配置/数据/分析产物；映射只是导航，不允许遗漏项逃过检查。
- 平台证据：执行事件、版本/产物绑定、资源记录和必要程序检查结果。运行过一个脚本只证明该运行事件，不能自动证明科学实现正确。
- Judge可按需只读查找已冻结产物和相关trace，不仅看agent选中的片段；保留查看位置、查询和未覆盖范围。检索未找到不直接等于证据不存在；用索引完整性/补查区分真正未提交与工具漏检。
- 如需复算或回放，由独立受控验证服务执行并记录成本，不让judge自由执行不可信代码、联网扩展答案或帮solver补做缺失实验。只读查证、复算和重新做科研是不同权限。

#### B. 通用rubric应展开到什么程度

| 已定维度 | 候选细化问题（按适用性检查，不是规定一套必做实验） |
|---|---|
| 检验有效性 | 对象/方法是否忠实于提案？操作化及测量能否回答假设？证据能否区分关键竞争解释？输入核心假设是否都有回应？ |
| 严谨性 | 对照是否可比较？数据构造/选取是否造成循环验证或混杂？不确定性处理是否适合主张？是否隐藏不利结果、改指标挑结果或超出适用范围？ |
| 执行可信度 | 代码/配置/数据与实际运行和产物是否对应？指标/统计量计算是否可信？记录是否支持完成声明？区分实现存在、已执行、结果可信，不相互替代 |
| 结论可信度 | 判断是否由实际证据支持？区分负结果、无效实验及未完成；机制/因果结论是否超出观察？局限与不确定性是否与证据相称？ |
| 资源合理性 | 是否遵守预算，在可用资源内优先获取有辨别力的证据？不奖励无意义重复或单纯省钱。费用另计，不能让廉价但无效的研究抵消科学缺陷 |

任务语境只解释假设、有效性必要条件与可核查事实，不指定必须用原论文的具体baseline、统计方法或实验顺序；“必须跑消融/多个种子/显著性检验”不能无视研究类型一刀切。数据构造型要评数据性质证据及构造/验证关系，不强制训练模型。适用性由固定规则和任务事实说明，不能临场擅加要求，也不能让solver自选不适用来免检。

#### C. 取证、局部判断与整体审计

1. **证据检查：** 程序确认产物/定位/版本、可复算事实与权限/预算，LLM核方法语义和科学含义。程序通过只提供事实，不自动给科学高分。
2. **按假设定位：** 分开问“做的实验能检验吗”“实际证据够吗”“结论相称吗”，输出支持与反对证据定位及短理由；不强制一个假设一个独立judge调用。
3. **全局检查：** 跨实验的共享问题、覆盖缺口和矛盾；不因同一证据多次引用或实验多就累加奖励。上游证据失效应标记影响哪些判断，不能简单全任务归零或把同一问题无限重复扣分。
4. **汇总：** 判据事实可用满足/不满足，开放质量使用已确认的0–4级文字锚点；前四维等权汇总科学质量主分，资源合理性单列，费用另报。由程序执行固定聚合，不由最后一个judge随意印象打总分。严重问题按下述影响范围规则处理，具体映射与实例待落实。

每条候选判定记录包含 `criterion_id / hypothesis_or_task_scope / applicability / evidence_refs / counterevidence_refs / verdict_or_grade / brief_reason / issue_type`；仅为设计草案。区别“不适用”“可证缺失/失败”“证据有限”“judge或检索故障”。不适用不能当已满足，无法核查不能默认高分；同时不把平台故障直接罚成solver失败。缺证因solver未交还是平台没采到，需按协议核查。

**评分总体结构 [已确认；具体锚点与实现待验收]：** EXP每任务返回科学质量主分、五维分数、证据定位/问题记录及严重缺陷标记，不是全任务pass/fail。内部事实用满足/不满足并区分证据不足/不适用。五维质量均使用0–4级：0＝未满足核心要求；1＝重大缺陷；2＝部分满足但有明显不足；3＝基本充分、仅有次要不足；4＝证据充分且无实质缺陷。各维度需进一步实例化锚点。前四个科学质量维度等权由程序汇总，资源合理性单列、实际成本另报，不让廉价但无效的研究提高科学质量主分。不做未经批准的0–100换算；跨模块总榜权重已按§8固定，也不按实验数量累加或反复奖励同一证据。

**严重错误、负结果与故障 [处理原则已确认]：** 科学错误按实际影响范围使相关证据/判断失效，并在相应维度评分中反映、单列严重缺陷；不一错全任务归零，也不允许平均分掩盖致命问题。某假设关键指标错误不能继续当作有效支持；共享错误若影响全部实验则扩展到全部相关判断。错误到分档的具体规则和案例须事先落实并验收，不交给judge临场发明处罚。有效反驳假设或充分证据揭示不确定性可得高分；未做必要实验、漏掉假设、无效实验后声称不确定不能同等计分。材料/平台故障单独处理，不直接算模型科研失败；模型自身执行失败正常计入。越权、硬预算违规按平台固定规则处理，不由LLM自由裁量。具体故障核查、重试和状态聚合仍待落实。

**Judge输入总体结构 [已确认；工具与权限实现待定]：** 固定任务提案/完整假设/资源与必要边界及起始材料说明；solver映射与简短结论；实际产物；平台trace/程序核验事实；评分规范及必要私有参考。无需研究报告，不把原作者结果当唯一真值或默认整篇论文塞入上下文。按需读取证据并检查假设全集，而不是只评solver主动列出的成功实验。模型身份/H0/H*盲化、具体取证接口及额度等候选实现仍待冻结。

#### D. 调用结构、稳健性与演化反馈

- 采用一次独立原生Codex judge会话主动取证并同时产出内部评分和公开feedback；同次会话可有多次工具交互，不等于一次无工具文本补全。分任务类型编写prompt，薄层只管理发布/验证/成本，不自建推理循环；不默认多judge投票。
- 不复用上一任务的评价记忆，不给judge看模型身份、harness名、H0/H*标签或已有分数以免影响判断。所有对比对象用相同冻结协议；反射复核不等于独立验证。
- 验证候选包括：等价表达保持质量、已知证据缺陷被识别、有效负结果不因不支持假设扣科学质量、Faker式无执行但产物自洽、映射漏项、无关信息增加、证据检索遗漏。只对有可核查预期的案例算误接受/误拒绝；不要把开放主张强行贴成绝对真值。
- 除重复评分稳定性，检查后期演化产物及排名对judge选择/取证方式的敏感性；报告无法判断率与费用。通过这些检查不等于专家等价或覆盖所有科学错误。
- Search反馈按§6.3已定双产物协议：内部评分记录与builder改进feedback分离，分数/状态/成本及自身执行证据可见，不公开私有参考/隐藏检查。正确评分和有用的改进反馈分别验收，具体发布过滤与调用实现待定。不要求发明新judge训练法，也不把完整独立judge benchmark设为前置工程。

**当前状态：** 用户已认可五维、judge输入、事实判定与分档质量评分、0–4量表、前四维等权主分与资源单列，以及严重错误/负结果/故障处理原则。具体锚点和案例由主agent在后续开发样例及逐轨迹验收中落实，不逐条追问用户。judge固定gpt-5.6-sol/medium并采用原生Codex；内部取证循环不再自建，评分和feedback同次输出。旧开发实现及审计已有；新版具体锚点、取证额度和失败处置仍须实现及验收。

## 8. 划分、聚合与统计 [论文分组与汇总已定；样本量、重复与区间待冻结]

- **[已确认]** 当前先按源论文分组再split，暂不考虑跨论文合并。同篇的arXiv/会议/修订版本、代码、附录和派生任务/实验切片必须同组。本文沿用的family/研究家族字段目前即此源论文组，不因主题、作者、共用数据集或跨论文关联自动合组。跨论文依赖风险可记录为限制，但不擅自恢复合并流程，也不声称论文级隔离已排除全部跨论文泄漏。
- 开发/人工 pilot、混合 search、隐藏 test 各用途分开；所有阶段公开/私有证据都按家族隔离。一个家族的论文写作材料若公开到 search，会泄漏同家族隐藏 idea，不能跨阶段漏掉关联。
- cutoff 控制外部信息，不消除预训练记忆。记录污染风险，考虑更新来源、记忆探针、同家族新条件等敏感性分析；不声称“无污染”。
- **演化也可能传入未来知识**：较晚 search 项目可能把较早隐藏任务的后续知识写入共享 harness，即使二者不同 family。需审计跨家族引用/答案依赖与 search→test 时间关系；时间一致的分组/全局知识截止可作为候选控制设置，不能一边给 builder 后期反馈一边声称完整历史知识隔离。当前承诺仅为外部工具的任务可见性限制，整体知识隔离仍待设计。
- **[汇总已确认]** 每个任务按其模块规则得到0–4质量分；同模块内先对同源论文的任务等权平均，再对有该模块任务的源论文等权平均。WRITE的研究内容写作与实验证据呈现各自先完成论文内/论文间汇总，再两类等权合成WRITE。最后LIT、IDEA、EXP、WRITE各占25%，总分仍为0–4；同时保留各模块/维度分及单列成本。所有模型与版本使用同一冻结任务清单和规则，不按实际成绩调权。
- 材料不支持某模块时不生成任务，不把结构性缺项计零；已纳入任务的模型失败按既定失败/评分规则计入，不从分母删除。平台/材料故障单独归因，其重试/处理细则待冻结。不将一篇多拆题等同更多独立样本，也不让WRITE两类各占一个主模块权重。
- **[版本选择已确认]** Test-best按上述总分在H0…HR中选出，完全同分取更早版本；保留oracle标记与选择偏差说明。Builder-selected由builder仅依据search可见信息自主判断，不强制取search分数最高版。若pilot发现某个模块/WRITE类别完全没有可验收任务，则正式配置尚不成立，须另行讨论范围，不偷偷改变分母/权重。
- 各模块材料组成不同，模块间分数差不能纯归因于能力差；报告各自覆盖与家族数，用共同家族子集和重加权作敏感性分析。
- 独立 builder runs 与研究家族是核心统计单位。子任务、种子和多次 judge 不充当独立科研项目；采用配对设计及适当的家族/运行分层区间，重复执行用于估计噪声。
- 少样本模块标探索性，不用几十个分片伪装强统计。正式数量、repeat 数、预算、分层与 power/MDE 依据 pilot 决定。

## 9. 必要对照与成本账本 [实验建议]

**优先级修订 [用户已确认]：** 首先完成主benchmark的任务材料、评分器、运行/演化协议及实际评测。TTS、prompt-only、重建择优、修改撤销/移植等用于分析改进来源，放在后续分析实验阶段；不要求现在敲定或执行，不阻塞主benchmark。保留相关研究问题和候选对照，不将延期误写为取消。主流程先记录完整checkpoint、执行条件、反馈、费用与版本，以便后续分析；未做归因对照前，主结果只报告观察到的演化与泛化表现，不宣称已排除额外计算等解释。

### 9.1 最小有说服力的对照

固定 executor、每题预算、工具权限和外层 builder 环境，比：极简/人工参考 harness、builder 自建 H0、混合反馈演化 H*、等预算独立重建多候选并按 search 择优。加入仅 prompt 优化可以判断代码/控制逻辑是否有额外收益。

**已确认的归因要求：** 上述候选不构成完整主对照；必须纳入固定 harness 的多次尝试/顺序修正这一 test-time scaling 方向，同执行预算、可比反馈权限且计入候选筛选成本，不使用隐藏 judge 挑答案。外层演化成本另做复用摊销分析。具体对照矩阵仍待冻结，不把本节所有候选都视为必做。

为比较“演化能力”而非初始强弱，另做**共同 H0 起点**的受控实验；自建再演化仍是主叙事。等预算重建择优必须把筛选反馈费用也算上，不得给演化组更多机会。可在子集比较分数反馈 vs 分数+trace、无信息反馈修改等。具体矩阵和次数未批准为已执行计划。

报告H0、builder自选版本与显式标注的事后test-best的质量、变化、完整曲线、退化率、search—test差及成本。test-best允许作为用户指定的主汇报列，但具有测试选择的乐观偏差，不作为无偏泛化估计或builder自身选优能力；不得向builder回流隐藏结果。初始强导致提升空间小是替代解释；pilot检查任务是否保留约定决策空间、评分是否响应可核查的质量变化，不预设复杂harness必然更好或据胜负筛题。builder无差异时，区分真实无收益、样本/资源不足与评分分辨率限制。

**外层停止条件最新修订 [已确认]：** 主演化协议限制改进轮次，不强制统一外层费用上限；每轮冻结版本均测隐藏test并记录累计成本。故同轮次曲线不能声称等外层算力比较。上述等总投入、重建择优等仍为待细化的分析/对照建议，不覆盖此决定；内层同任务资源控制与TTS归因问题仍保留。费用轴比较须依据实际观测成本，不能凭曲线插值冒充受控等预算实验。轮内流程已定为反馈→修改→冻结→同一完整search重评；具体轮数和调试/正式评分接口边界待落实。

### 9.2 不重复计费

互斥实验账目：

- `C_build`：初始构建、调试、smoke。
- `C_edit`：后续分析/修改及非正式本地调试。
- `C_feedback`：search 正式评测的 executor、工具/计算和 judge 成本，分别记明细。
- `C_test`：隐藏最终/离线检查点执行与 judge 成本，分别记明细。

`C_evolve = C_edit + C_feedback`；`C_eval = C_feedback + C_test`。二者重叠，不能相加当总成本。实验总成本是 `C_build + C_edit + C_feedback + C_test`。

另列 `C_data`（材料搜集/构造/审核/环境建设）、评分器验证费用、冻结 harness 新题部署 `C_run`；不设置专家校准环节。建设投入与模型实验费用不混为排名依据。失败、超时、重试、并发、缓存都记录。保存金额、token、调用数、CPU/GPU 时间、墙钟及价格快照。订阅接入不是零成本或无限预算。

质量—成本与固定预算切片优先；部署摊销可用 `(C_build + C_evolve)/N + E[C_run]`，但不同质量系统不能只比便宜。judge 的成本与稳定性是本方案重要可行性指标，不藏在“eval”一个数字中。

## 10. 最终端到端 use case 与开源

使用同一选定冻结 harness，从限定研究问题起实际串联 LIT→IDEA→EXP→WRITE，比较 H0/H* 和参考 baseline；记录人工干预、接口衔接和失败传播，不能给每阶段重新注入 gold 后称端到端。

use case 项目与正式 search/test 家族隔离，不能据其结果回头选择最佳版本后仍称独立验证。连续流程的有效性与成本单独报告，不用一篇看起来完整的 PDF 代替所有证据。未要求真实投稿/录用，也不声称覆盖无限开放的自主科学。

目标开源规范、获许可的材料/构造脚本、公开开发任务、评价工具、基线、成本与trace机制、最终参考 harness。隐藏答案和有权利限制材料不得打包；API key 为优先接入，subscription 仅在合法受支持接口存在时适配，不承诺任何订阅都能即插即用。

## 11. 当前证据与已知缺陷（不重复记录旧运行中的瞬时状态）

### 11.1 样例审查结论

| 样例 | 当前材料契约与真实证据 | 必须修复或补验 |
|---|---|---|
| SSA LIT | 标量回归适应问题；旧8篇固定库，cutoff 2024-09-01。用户暂停细审，转R2。 | 定向digest替solver做推断、库覆盖不足、IDEA措辞残留；最早披露/过滤/全局库/分层依据待验收 |
| SSA IDEA | 独立固定背景报告→提案+假设；用户认可产出形态，不以原SSA为唯一解。旧judge五维4。 | 研究价值与形式完整区分不足，满分反馈锚定；定向缺陷和均完整不同质量提案、重复/表达变化检查 |
| IV EXP | IVTransformer§3.2/附录C.2 CPU耦合迭代；固定方法和H1/H2，自主实验→证据映射。用户认可简单案例契约。 | 600题面/2400控制器不一致、实际总约1087秒；分析窗口变更，floor判据；旧judge错误归因及feedback可访问性误报。不是Transformer训练复现 |
| SSA WRITE_CONTENT | 事实卡+Table4选取98格→417词正文+来源映射；语义基本正确。旧v3分3.75，人造数字/方法缺陷副本2.25。 | E3复合论断定位不精确，后来补U1–U4不追改旧输入；少量注错有效不证明质量区分度/全局可靠 |
| SSA WRITE_EVIDENCE | 表/代码/双面板图/图注/98格清单；数值与13差值独立核过。 | 图列标题被首行色块遮住，executor无图片回看；旧judge发现但总3.75，严重程度锚点待审。实际约626秒，题面600/运行2400冲突仍是平台问题 |

五例不是同一冻结harness评测：最早WRITE_CONTENT专用单次脚本，后四类使用开发中的统一手写baseline。所有分数仅开发记录。H0 call48禁用code-mode host，call50子进程policy/read-only失败；两次均无harness/manifest/实际测试，不能推断builder能力弱。

### 11.2 证据入口

以下路径均相对`research/benchmark/`，仅维护者可全量读取：

| 内容 | 入口 |
|---|---|
| 材料目录/覆盖 | `materials/material_packages.json`、`materials/coverage.json`、五个材料子目录 |
| 原始来源 | `../source_cache/iclr2025_pilot/`、`../source_cache/benchmark_materials/`、`../source_provenance.json` |
| 构建prompt/接口 | `reference_harnesses.json`、`prompts/builder_h0.txt`、`prompts/evolver.txt`、`runtime/interface.json` |
| 真实运行及审查 | `audit/{lit,idea,exp,write_content,write_evidence}_trajectory_review.json`、各`*_dev_001`及`h0_build_dev_001/002`；具体名称以磁盘为准 |
| 成本/回归证据 | `audit/development_call_ledger.json`、`audit/development_cost_report.json`、`audit/offline_tests_current.json`、`audit/upstream_baseline_hashes.json` |
| 旧开发入口 | `run_stage_development.py`、`rejudge_development.py`、`build_h0_development.py`；旧调用结构不能当新原生judge已实现 |
| 演化/统计 | `mrhbench/evolution.py`、`scoring.py`、`reporting.py`；目前仅软件测试，不是正式演化结果 |

上游采样历史：官方快照4040事件，处理后3705候选记录（不是官方录用总数断言），1369条直接GitHub链接；30项主题pilot，29仓库metadata/28README；OpenReview评分未取得，不能当低分。多数默认分支快照不是论文时commit；许可/完整性须逐资产审核。第三篇Fragmented知识论文仅取得源材料，未派生任务。

旧独立三轮模拟评审的核心建议已合并到§2、§7–9及TODO：research场景不自动构成充分创新；judge可靠性/可迎合、任务对harness敏感度、反向出题泄漏、低成本成功研究选择偏差、家族相关性、TTS归因都需证据。评审不是专家真值或录用承诺；不恢复已否决的人类专家评分、六碎片WRITE或跨论文强合并。

## 12. 唯一待办表与依赖调度

状态语义：待实施／离线实现／真实运行待验收／验收通过／等待用户或环境。**代码存在、单元测试通过、开发案例有效和正式准入是不同状态**。以下是执行计划，不将未执行项标完成。

### 12.1 全量主线待办

| ID | 工作包与实施要点 | 依赖与验收条件 | 当前状态 |
|---|---|---|---|
| T00 | **包级CPU Docker执行底座（新增显式前置项）**：EnvironmentSpec/ResourceSpec、每包环境定义/锁定依赖和镜像版本；每run独立容器/输入/输出。controller持有Docker权限；worker不得挂Docker socket、凭据或整工作区，禁特权/宿主网络，限制权限/CPU/内存/进程/存储和时限。模型与检索走受控broker，不把凭据交给任意研究代码。 | 先核可用宿主/daemon，再用两个包不同资源配置测试构建、启动、读写、超时、OOM/进程上限、清理、跨任务/宿主越界和残留状态。固定依赖不等于字节确定性重现。无可用daemon时可完成代码测试，但真实验收不能passed。 | 两包10项CPU压力/边界诊断、超时未知产物政策、12项流式hash和25MiB整题生命周期通过；完整正式角色隔离与跨宿主仍未验收 |
| T01 | **订阅调用层审计**：区分原生Codex与executor模型transport；核模型/medium、继承上下文、工具开关、文本/图像、权限/失败；优先官方订阅通道。旧codex exec JSON包装不是HTTP反代，也未证实裸API等价。 | 最小真实调用、参数与完整事件核查；与T00确定凭据留在可信controller的调用桥接。不能把高分直接归因于调用层。 | Claude角色（§0.2.13）：executor `ClaudeJSONTransport`无工具+结构化输出（键别名、拒绝分类）、builder/judge `ClaudeNativeRunner`；真实探针196–198/205/231–232/295与集成已用；Codex历史保留。非裸API等价，CLI宿主进程非OS隔离 |
| T02 | **原生Codex judge**：五类prompt模板，原生主动查文件/图像；同次生成内部判分和公开feedback，薄层做发布/格式验证/固定汇总/成本记录。 | T01、T07；真实受限会话读到必要证据，评分/feedback分离。复核提交代码需独立隔离执行，不放宿主自由执行。 | Claude原生judge v3.4（精确结构schema、图像缩放核验+全分辨率tile）已接并在集成中使用；同次评分+feedback；Codex v2.8保留 |
| T03 | **judge区分度与行为审核**：补各维度0–4锚点；IDEA要素完整不等于研究价值；WRITE可交付性缺陷不能被平均分掩盖。正反例、自然错误、无硬伤不同质量、等义/顺序/重复、feedback泄漏；调prompt样例与留出验收例区分。 | T02及T05；逐条审完整被评/取证/判分轨迹。已知标题遮挡、事实定位、数字/方法错误、无实验和EXP归因漏检回归；不得强行压分、用作者论文作唯一gold。改变主汇总/门槛须另确认。 | Claude重验证10例有界partial（7过/2部分/1格式失败，后v3.1修复EXP对且非目标维度不漂移）；Claude比Codex严、分数不可互换；集成v2逐轨迹审阅进行中；完整验收未通过 |
| T04 | **预算与计时**：题面、runner、模型/工具/CPU子进程读取同一份**当前包/任务**配置，无静默全局fallback；按剩余额度超时并杀进程树/容器，恢复不重置账本。 | T00；配置不一致拒启，边界耗尽/失败/恢复实测。总wall保留；开发人工暂停显式记事件，总时长和扣除时长均报告；正式计时规则冻结后执行。judge另计，外层演化仍限轮次不硬限研究费用。 | 包预算/绝对deadline/账本/容器超时已接；12/16开发试跑均产出实际科学文件且在时限内；collection配额已显式按任务公布，正式值不冻结 |
| T05 | **工具/环境预检**：按包声明真实读写、CPU、检索、渲染、模型视觉等能力；executor补图片回看，judge也接收真实像素；跨任务统一工具接口而非相同依赖。 | T00、T01、T04；真实读→写→运行、生成→回看、检索→原文；缺工具归平台，工具正常但agent不用归agent。 | 图像>2000px由CLI缩放已定位：controller发布全分辨率tile并核验忠实缩放；工具面审计`claude_tool_surface_audit_v1.json`；新论文工具需求待runtime验证 |
| T06 | **失败分类与入账**：材料、平台/transport、judge、agent失败/部分完成、正常负结果分离；保留阶段/证据/状态/资源。非agent错误不自动零分，agent失败不静默丢样本。 | T04–T05；故障注入及轨迹审核。归因不明标待审；重试幂等但每次真实调用计费。正式分母与故障聚合在T14冻结。 | 新增typed broker错误（接口v4）、provider_safety_refusal、平台/agent归因记录（集成v1/v2归因审计）；EXP超公布配额保留failure不零分；正式分母规则仍待T14 |
| T07 | **角色/阶段/split隔离**：包/任务白名单、H0零科研任务、evolver仅search、同篇同split、每题状态清空；judge私有轨迹不发布，feedback只引用公开证据。 | T00；静态导出检查+真实越界/网络/状态/私有canary测试。root可先做导出和发布代码；容器实测未通过不声称OS隔离完成。 | Claude judge/builder启动即移除全部宿主工具，只留受控MCP（容器/证据）与输出通道，工具面审计零宿主工具；CLI宿主进程与OS级隔离仍未验证（Windows提权/独立Linux待用户），不作正式隔离声明 |
| T08 | **LIT-R2全局库**：强相关/背景/真实近邻去重；只索引允许背景原文，去掉定向digest及IDEA措辞；search/snippet/read统一cutoff/版本/目标排除，最早公开核查。 | 离线构造可先做；服务运行验收依T00/T07。跨包发现、拒绝未来/目标/跨split答案、原文保真/覆盖/近邻难度审核。8篇仅开发种子，不冒称正式覆盖。 | 18篇共享原文库、跨包过滤/实际LIT已跑，judge固定原文与char索引已补；364/365页可读、1页显式失败；非完整领域覆盖 |
| T09 | **LIT分层与检索指标**：按任务私有标签核心/背景/混淆，分别记录返回/阅读/采用，身份版本去重；合理引用近邻与名单外有效支持不罚。 | T08；机械匹配与语义核查对齐。公式/权重/是否进主分待pilot及确认，不擅改四维。 | 检索三阶段诊断代码/测试已实现；11篇SSA私有候选已独立溯源及root定位复核；真实H0返回/摘要/页读/声明采用诊断已出，7篇SSA未审；非必引gold，公式权重及主分待定 |
| T10 | **统一材料模板与审核**：按篇规范化原始材料再派生阶段任务；事实/维护者限定/缺失/结论分开，关键公式假设与原文对应；补稳定ID、表格冲突记录、无目标实现的可运行起点、包级环境资源配置。 | 可与T00/T02并行离线；实际准入需环境与语义审核。独立上下文审核原文而非自评摘要；材料不足只淘汰相应模块，保留覆盖矩阵。 | Gaussian维护者EXP候选包；FTCT/Diffusion由Claude constructor构造、独立reviewer（pass_with_pending_runtime/revise），root裁定后一轮repair进行中；runtime/rights门均pending |
| T11 | **低消耗模型并行构造**：每篇独立workspace，原生Codex构造→程序检查→独立审核→返修/淘汰；限并发、重试退避、幂等、断点续跑。 | T01/T10完成后小批试产，包的运行门依T00；T03相关judge验收前不批量正式入库。模型/并发/规模依据每份合格材料成本和返修质量选，不用尽额度为目标。 | 用户定：Claude native runner constructor（material_workspace档，无shell、controller填hash）；小批2篇进行中，未批量 |
| T12 | **H0修复**：公开ABI干净构建环境内核读写/CPU工具，再用gpt-5.6-sol/medium构建单一harness；不看search，不用手写baseline顶替。 | T01/T05/T07；实际harness+manifest+接口测试，H0版本hash冻结。可先做构建smoke，不必等完整数据池。 | Claude H0 v1（v2接口，集成因reasoning字段被拒失效）→H0 v3（v3接口）在平台v4上development_admissible并冻结`h0-claude-frozen-v3`（sha 619dc724…）；遗留V3-2..8为H0属性 |
| T13 | **冻结版本CPU集成复验**：一个冻结harness独立运行五类修复后任务，与原生judge配套；每题包级容器环境和资源。 | T00–T08/T10/T12相关门；T03进行中可用明确标注dev baseline辅助，正式builder结论必须用H0。逐轨迹审核，旧run不混算。 | Claude集成v2：WC 3.75、IDEA 3.8、LIT 1.75、WE 3.0（v3.4读tile）、EXP超配额stage_failed；开发证据非正式分；逐轨迹审阅进行中 |
| T14 | **数据冻结与正式主评测**：完整合格池后按源论文划split，冻结样本量/内层配置/轮次/重复/异常与统计规则；H0、builder选版、test-oracle三版本与完整曲线/成本。 | T03/T09–T13及真实覆盖；正式配置须给用户确认，不用旧TB20/50或开发2篇充数，不在test上调judge/材料再称隐藏。 | 尚未满足入口，不虚报完成 |

### 12.2 依赖与并行安排

```text
环境线：T00 + T01 → T04/T05/T06/T07 → T12
Judge线：T01/T07最低可用 → T02 → T03（需真实工具与证据）
材料线：T08 + T10离线并行 → T09 + T11小批试产
汇合：环境/材料/judge就绪 + H0 → T13 → 合格材料扩展 → T14
```

不是每项都严格串行：prompt/schema/静态测试/语料整理可先做；真实运行、发布/入库和正式排名不得跳过依赖。H0构建与离线judge开发不必等完整材料池，但正式混合演化必须等全池冻结。

| 协作者 | 主责任与文件范围 | 边界 |
|---|---|---|
| root | AGENTS、依赖/额度、包级隔离/发布与集成、验收及T14配置 | 唯一修改本文；最终检查agent声明与实际证据 |
| runtime_repairs | T01/T04/T05/T06/T12；provider/costs/sdk/CPU runner/原生Codex调用及对应测试 | 与root协作T00；不能把宿主Full access当隔离，不能自行追加模型预算 |
| native_judge | T02/T03；原生judge、分模块模板/锚点、校准fixtures及测试 | 不改runtime/materials；同次双产物、实际轨迹审核 |
| material_pipeline | T08/T09/T10/T11；R2、版本化材料、生成/审核模板与队列 | 不改原始缓存/旧run；每包环境配置纳入构造产物 |

上一批已中断，恢复时发送最新文件所有权、CPU-only/包级Docker决定与授权额度，不能自动沿用旧4次smoke等临时分配。各agent完成有界子任务后可调度独立复核，不默认增加无限评审。

### 12.3 暂不阻塞开发、但进入对应阶段前须明确

- **运行宿主：** 本机Docker Engine/Desktop可用性或Linux执行主机；不因Docker CLI存在就说环境可用。不擅自安装/启用系统服务、虚拟化或收费云资源；必要时问用户。
- **构造模型及批量规模：** 用户要求核最便宜，已查GPT-6 Luna标准credits最低；尚未给其科学提取质量背书。先小批候选比较，再确定；不更改builder/executor/judge配置。
- **正式设置：** 实际合格论文数、split、每包预算、轮次、重复、故障汇总、LIT检索指标权重在pilot后确认；不提前拍统一时间档位。

### 12.4 后续而非首版前置

GPU任务扩展；TTS及改进来源归因/跨executor敏感性；独立连续idea-to-paper use case；发布资产权利审核、开源与复现；论文新颖性对照及统计论证。保留数据/版本/成本，不能因后续未做就宣称相关结论已证实，也不让这些项目阻塞CPU首版工程。

## 13. 复核与运行注意

- 通用离线测试：`D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe -X utf8 -m unittest discover -s research/benchmark/tests -p 'test_*.py' -v`；默认宿主Python缺pypdf，不混用环境。
- 来源测试：`python -X utf8 -m unittest discover -s research/aiml -p 'test_*.py' -v`。
- 可用bundled Python：`C:/Users/li_ha/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`，含已有NumPy/PDF开发依赖；不等于宿主默认Python已具备依赖。今后真实任务以包内Docker环境为准。
- 历史已测Codex：`C:/Users/li_ha/AppData/Local/OpenAI/Codex/bin/d375f7df50d3b421/codex.exe`，当时0.155.0-alpha.16；PATH旧0.130.0失败。后续实际版本重新记录，不写死“当前最新”。不复制认证密钥。
- 任何新运行使用新audit目录，参数/输入/输出hash与账本绑定；历史失败、注错来源与真实solver错误区分。运行前核模型额度授权和goal/用户暂停状态。
- 新schema/单测通过只表示软件验证；容器运行、材料语义、judge轨迹及正式集合分别验收。工具看到某路径不等于模型读到文件/图片。

## 14. 资料入口与新颖性待查

以下为来源/方法参考，不是已证明的 novelty claim：

- [ICLR 2025 官方候选元数据](https://iclr.cc/static/virtual/data/iclr-2025-orals-posters.json)：当前采集主入口。
- [OpenReview 获取 submissions/reviews 指南](https://docs.openreview.net/how-to-guides/data-retrieval-and-modification/how-to-get-all-notes-for-submissions-reviews-rebuttals-etc)：不同会议年份的公开范围需单独确认，API 可用性不作保证。
- [NeurIPS checklist](https://nips.cc/public/guides/PaperChecklist)、[ICLR 2026 author guide](https://iclr.cc/Conferences/2026/AuthorGuide)、[ICML 2026 author instructions](https://icml.cc/Conferences/2026/AuthorInstructions)：写作维度灵感；网页可能更新，正式规则需冻结快照。
- [ResearchAgent](https://arxiv.org/abs/2404.07738)、[Agent Laboratory](https://arxiv.org/abs/2501.04227)：科研过程/系统设计参考，不是我们首次提出阶段拆分。
- [The Ideation–Execution Gap](https://arxiv.org/abs/2506.20803)、[NoviScl/AI-Researcher](https://github.com/NoviScl/AI-Researcher)：真人执行与评价材料线索，附件未验收。
- [PaperBench](https://arxiv.org/abs/2504.01848)、[AI-Scientist](https://github.com/SakanaAI/AI-Scientist)：任务与原始资产追溯、研究工程参考，不沿用最终任务作为创新点。
- 前期记录的 Meta-Agent Challenge / Evo-Bench / EvoHarnessBench / Evo-Harness / Mimosa 等为 **待重新核验全文与代码的邻近工作线索**。旧文档链接不能替代正式 novelty audit，不能根据标题/摘要断言它们没有某能力。
- 合并保留的历史检索入口（本轮未重新全文验证）：[AI-Researcher / Scientist-Bench](https://arxiv.org/abs/2505.18705)、[AI Scientist-v2](https://arxiv.org/abs/2504.08066)、[AI co-scientist](https://arxiv.org/abs/2502.18864)、[ScienceAgentBench](https://arxiv.org/abs/2410.05080)、[DiscoveryBench](https://arxiv.org/abs/2407.01725)、[AutoResearchEval](https://arxiv.org/abs/2608.14905)、[Mimosa](https://arxiv.org/abs/2603.28986)。自然科学/成品任务来源仅作相关工作与验证参考，不恢复为当前数据主线。




