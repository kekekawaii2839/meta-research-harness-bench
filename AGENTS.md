# Meta Research Harness Benchmark：唯一研究方案与工作记忆

更新：2026-10-12（Claude Code；多会话同步规则见§0.3）。本文是唯一研究协议、待办与工作记忆；代码、结构化材料、原始快照、trace和测试报告是证据，不另立PLAN/STATUS/TODO文档。

## 当前断点（2026-10-12晚整理，Claude Code；接手先读；任何会话改变状态后立即更新本节）

本节只写现状与待办；2026-10-12当天的过程与证据原文移到§0.2.25，更早的见§0.2.20–0.2.24。

**现状**
- **在跑：** 控制台`mrh-console`（http://127.0.0.1:8770/；重启须`schtasks /End`后按8770端口找PID结束，再`/Run`）；executor反代在127.0.0.1:8765运行（计划任务`mrh-wrapper`，`run_wrapper.cmd`）。其他`mrh-*`计划任务均已结束，没有在跑的模型运行。
- **额度：** 账本`research/benchmark/audit/development_call_ledger.json` **3334/3358（2026-10-12晚+40），上限3395（2026-10-13 +15、+10、+12），已用3391，余4**（失败/429计入；追加记录见authorization_events）。下面多数待办需追加额度。
- **search set v1.3（用户2026-10-13；`audit/search_set_v1_3_membership.json`，22篇，membership `abca25a5…`）：**A2与Poster→Oral替换合并做——①3篇Spotlight（qpXc、qgsX、SyVP）的旧LIT+IDEA在factory-v8.4重建；②2篇Poster（KeRw：旧IDEA；aXuW：旧LIT）移入`audit/held_out_pool_v3.json`（8篇）并在其工厂目录放`SPLIT_HELD_OUT.json`，标记以后再重建；③加入2篇Oral：**4OaO3GjP7k（Flat Reward，RL）、QFO1asgas2（Advantage Alignment，多智能体RL）**，在v8.4新建（状态in_construction）。注意：140篇批准名单中未开始的Oral实际只剩4篇（此前记“7篇”有误），另两篇kRoWeLTpL4（LM版权融合）、CxXGvKRDnL（扩散压缩）CPU风险大；未开始Spotlight 8篇。**用户2026-10-13批准+180（上限3395→3575，已记authorization_events）。**零调用：`factory_v8_4.py carry-paper`把qpXc/qgsX/SyVP论文级阶段从factory-v5带入v8.4（公开截止日qgsX 2024-09-20、SyVP 2024-09-18，旧根未改）。**在跑：**计划任务`mrh-searchset-v13`（`factory-v5-driver/run_searchset_v13.cmd`→`searchset_v13_v84.py`，3篇并行，A2每篇area_brief+bg_screen+LIT/IDEA上限28次，新Oral每篇fetch→compile上限48次，合计180；撞429不开新任务，恢复后手动`schtasks /Run /TN mrh-searchset-v13`，`--retry-platform`续跑），日志`D:/mrhbench-local-pilot/factory-v8_4/searchset-v13.log`，结束写`searchset-v13.done`；监视脚本`watch_searchset_v13.py`（零调用，报429/失败/单元编译/撤回）。完成后：新单元生成checks.json（`checks/gen_generic_checks.py`）、新论文背景并库后再冻结文献库。**2026-10-13 17:21撞429停（HALT，无自动重试）；恢复后手动`schtasks /Run /TN mrh-searchset-v13`续跑（已完成单元0调用）。**已编译：qpXc LIT+IDEA（A2完成，24次）、qgsX LIT、QFO1 EXP/WC/LIT、4OaO EXP。撤回：4OaO WE（第2轮仍有WE-F07与DATA_README原文矛盾，可日后维护返修≈3次）。QFO1 WE runtime `failed_needs_attribution`：字符串泄漏检查命中私有check_deliverables.py与公开load_league.py共有的`hashlib.sha256()`分块读文件样板（误报）——**待用户批准把泄漏规则B扩展到该样板**，再零调用重跑runtime/compile。被429打断：QFO1 IDEA（frame）、4OaO WC（repair）、qgsX IDEA（construct）及其余未跑单元；SyVP未开始。监视器`watch_searchset_v13.py`的429判定已修（原按“429”子串误报）。**第2次运行已启动（额度恢复后，账本起点3479）：**各任务上限改为第1次剩余份额（QFO1 22、4OaO 27、qgsX 14、SyVP 28，合计91≤余96），qpXc已完成不再跑；QFO1 WE仍待泄漏规则决定，未被重跑。**v1.3构造已全部结束（`SEARCHSET-V13 DONE`，2026-10-13 21:38；本批共147次，3391→3538，余37）：**编译12道——A2：qpXc、qgsX、SyVP的LIT+IDEA全部6道；新Oral：QFO1 EXP/WC/LIT/IDEA（IDEA第1轮判L2泄漏、重写后通过）、4OaO EXP/LIT。均已生成checks.json。撤回3道（均4OaO，第2轮仍有小缺陷，可日后维护返修各≈3次）：WE（公开事实WE-F07与DATA_README和原文矛盾）、WC（私有检查D4对子串'acknowledg'一律判失败，比公开要求10严）、IDEA（背景报告引bg025用了原文没有的措辞，只需框架作者改一句）。QFO1 WE待泄漏规则决定。**search set v1.3现有有效题86道**（LIT 14/IDEA 14/EXP 19/WC 20/WE 19）。**用户2026-10-13批准返修4OaO三道（用余下37次额度）：**`maintenance_repair_v6.py`加v8.x根分支（导入factory_v8_4，备份`*.pre-v84.20261013`），WE/WC用维护返修（各3次，返修说明=被接受的审阅意见，`maintenance_notes_factory-v8_4/`）；IDEA因缺陷在锁定背景报告需框架作者，改为整单元重建（旧单元改名`units/IDEA.dropped-1`、论文`units`阶段记录挪入history，备份`state.json.pre-idea-rebuild.20261013`），上限16次。**在跑：**计划任务`mrh-maint-4oao-v84`（`run_maint_4oao_v84.cmd`），日志续写`factory-v8_4/searchset-v13.log`，结束写`searchset-v13.done`。**用户2026-10-13两项决定（均零调用完成）：**①泄漏规则B扩展到标准库文件hash样板（`hashlib.<algo>()`+`with open(...)`、`for chunk in iter(lambda: f.read(N), b""):`；`leak_rule_v6.py`，备份`*.pre-ruleB2.20261013`；正反例测试通过），新`rerun_runtime_v84.py`重跑**QFO1 WE runtime+compile通过（lint 0）**，已生成checks.json——**search set v1.3有效题87道**。②cpu.run签名：`s3_cpu_note.py`为46道v5/v6/v7 EXP/WC/WE题各建新发布目录**`release-s3`**＝原release逐字节复制、仅在public.prompt平台说明第4条后加第5条（`cpu.run(script, arguments, timeout_seconds)`用法，措辞只取自interface_container_v4.json），并改写3个绑定task.json hash的文件；记录`D:/mrhbench-local-pilot/s3-cpu-note-applied.json`与各包`s3_provenance.json`；pilot dry-run加载2道确认题面含第5条；46个checks.json改绑release-s3（旧件`checks.json.pre-cpu-s3.20261013`）。**今后这46道题试跑/重评用`@release-s3`。****4OaO三道返修全部救回（2026-10-13 22:40，`MAINT-4OAO DONE`，18次，3538→3556）：**WE、WC维护返修通过并编译（release，lint 0），IDEA整单元重建后第2轮通过并编译；均已生成checks.json。**search set v1.3现有有效题90道**（LIT 14/IDEA 15/EXP 19/WC 21/WE 21）。账本3556/3575，余19。S3零调用重编译可并行（跳过在重建的6个单元与2篇新论文）；文献库冻结T17在全部题目建好之后，冻结后LIT题须在冻结库上用v3.10.2试跑/重评，再冻结题目清单T15。
- **search set v1.2**（`audit/search_set_v1_2_membership.json`，22篇=Oral 3/Spotlight 4/Poster 15，membership `a89d4a8a…`；held-out池v2 6篇在`audit/held_out_pool_v2.json`）。**已编译90道：LIT 14/IDEA 15/EXP 19/WC 21/WE 21。**其中8道仍是v5/v7旧版、待按S1重建（A2）：qpXc、qgsX、SyVP的LIT+IDEA，KeRw IDEA，aXuW LIT。缺题：z21D、h0vC、Bt1v、d1NW、oANk、spDU、kbjJ无LIT/IDEA（kbjJ用户已放弃；其余5篇Poster按方针不补）；撤回5qg6 LIT（可维护返修）、msEr EXP、Bt1v WC；qgsX、oANk无EXP，kbjJ无WE。
- **最新工厂根：factory-v8.4**（`factory-v5-driver/factory_v8_4.py`，根`D:/mrhbench-local-pilot/factory-v8_4`；含v8.3的OpenReview公开日修复与v8.4 IDEA判据O1+O2）。今后新论文与重建都用它。
- **3篇Oral已全部试跑完（2026-10-13，material package pipeline optimization会话）：** 计划任务`mrh-p11-v84-oral-rest`已结束（输出`D:/mrhbench-local-pilot/p11-v84-oral-rest-s46low/`，55次调用3280–3334全部completed、无429）。**Xo0Q IDEA 2.8**（v8.4单元，4次；硬检查全过）；**Xo0Q LIT 1.25**（29+1次；executor耗尽模型调用前没写review.md、7处论点只依据搜索摘要——冻结H0预算/观察窗口缺陷类，非材料问题）；**GMwR LIT 2.0**（20+1次；bibliography.json未写、12处“abstract”定位指向没读过的摘要、个别引用不支持论述）。两道LIT硬检查files与schema-bibliography均失败（solver未交）。3篇Oral共12道均分2.25（Xo0Q WC3.25/WE2.5/EXP2.25/IDEA2.8/LIT1.25；GMwR WC3.25/WE1.75/EXP2.25/IDEA2.2/LIT2.0；kbjJ WC3.0/EXP0.5），单次运行、开发证据。为此零调用做的平台改动：开发库**`D:/mrhbench-local-pilot/shared-library-v7`**（factory-v1…v8_4全部背景608篇，未冻结，sha `42477cd9…`；两道LIT的`lit_corpus_configuration.json`改指v7，v5原件`*.pre-libv6.20261012`；`shared-library-v6`因一页PDF抽不出文字致judge证据构建失败、从未使用）；`factory_library.py`建库时跳过“仅PDF且有页抽不出文字”的背景（备份`*.pre-pdfcheck.20261012`，本次跳过1qq1背景2209.10652）；`pilot_v5.py`的judge文献预载上限2500万→8000万字符（`JUDGE_LIT_MAX_CHARS`，备份`*.pre-litcap.20261012`）。额度：用户2026-10-12批准+40（3318→3358）。待办：T17冻结库时以v7为起点；这两处驱动改动与`run_p11_v84_oral_rest.cmd`需并入git清单。
- **judge v3.7（2026-10-13，material package pipeline optimization会话；用户批准“按顺序做、额度批准”）：** 只改证据访问，评分规则1–10、锚点、schema与控制器校验不变。实现在驱动目录（仓库不改）：`judge_v37.py`（进程内把`EvidenceSession.read_chars`单页上限6000→24000）、`bounded_mcp_v37.py`（MCP服务器：目录只列控制器选定记录、新增只给位置不可引用的`evidence_search`）、`rejudge_v37.py`（用原v3.6同一份evidence.json重评，原评分保留，写`<run>/rejudge-v37/`）。A：LIT目录只列solver检索/读过/引用及评审指引点名的文献，另加`lit-library-catalog`，其余文献仍可按id读；B：允许一轮并行多次读取；C：model-action与platform-rpc合并为`platform-action-timeline`（带偏移索引、内容逐字节不变），删减Codex时代hash段；D：LIT新增`lit-citation-bundle`（每条solver引用在锚点处的原文段与偏移）。零调用dry-run 12题全过：LIT提示词约16–17万→3.2–3.3万字符（列出文献Xo0Q 39/561、GMwR 32/604），非LIT约2.2–2.9万；MCP子进程读取/检索/凭证重放实测通过；GMwR引用核对包31条锚点全部找到。**验收重评已跑完（13次调用3334→3347，无429）：**12道中10道出分，Xo0Q WC 3.25→3.75、GMwR WC 3.25→3.25、kbjJ WC 3.0→3.75、GMwR WE 1.75→1.75、Xo0Q WE 2.5→2.25、Xo0Q EXP 2.25→2.25、GMwR EXP 2.25→2.25、kbjJ EXP 0.5→1.0、Xo0Q IDEA 2.8→2.6、GMwR LIT 2.0→2.0；2道被控制器拒收：GMwR IDEA（judge抄错1个凭证字符）、Xo0Q LIT（首次MCP连接失败=平台故障，目录`rejudge-v37.failed-1`保留；手动重跑1次后judge为引用evidence_search结果编造了凭证id——v3.7回归）。已零调用修为**v3.7.1**（规则15+工具说明：refs只能是evidence_read返回的凭证，检索结果不可引用），尚未用模型验证。成本（10道配对）：原始输入911万→315万token、轮数109→约37、输出-17%；按列表价（缓存读10%）输入费用约-36%，总体约省三成；judge读到的字符12题中10题更多（未少读）。**逐轨迹审读结论（`D:/mrhbench-local-pilot/rejudge-v37-review-A.json`，root抽查属实）：v3.7未通过验收。**升分有偏松：Xo0Q WC、kbjJ WC的升分理由含错误陈述（如“所有符号已定义”，实际α、系数a未定义），kbjJ EXP什么都没测却把检验有效性给1；降分两道可辩护但有一处重复扣分。LIT：引用核对包让judge读全了31条引用并查出v3.6漏掉的一处误引，但又漏掉v3.6抓到的核心错误（FSQ与STE），且没读私有LIT评审指引。judge读的字符更多，偏松不是读得少，更可能是轮数被压缩后核查变浅。**正式judge仍为v3.6。**用户2026-10-13同意v3.8方案并追加额度+15（上限3358→3373，已记authorization_events）。**judge v3.8**（`judge_v38.py`+`bounded_mcp_v38.py`，叠在v3.7.1上）：保留A/C/D与规则15；单页上限改12000、并行只用于开头打开已知记录；规则16核实步骤、17无结果用0档、18必读清单（提示词逐条列出id）；控制器关卡G1（task、全部私有reference-*、≤6万字符的submission文本、LIT引用核对包须读到底）与G2（3/4分维度须引用≤6000字符的针对性读取或图片凭证），不过即拒收不出分。离线：G2正好抓到v3.7偏松的升分维度；G1连v3.6多数也不过（v3.6常不读完长私有参考），故v3.8会比v3.7多读。8道零调用dry-run通过。**验收在跑：**计划任务`mrh-rejudge-v38`（`run_rejudge_v38.cmd`：先v3.8评8道→`<run>/rejudge-v38/`，再v3.6复评同8道作噪声基线→`<run>/rejudge-v36-repeat/`，共16次，撞429即停），日志`D:/mrhbench-local-pilot/rejudge-v38.log`，结束写`rejudge-v38.done`。8道=Xo0Q WC、kbjJ WC、kbjJ EXP、Xo0Q WE、Xo0Q IDEA、GMwR LIT、GMwR IDEA、Xo0Q LIT。**v3.8验收已跑完（16次，3347→3363，无429）：**v3.8八道全部出分、关卡零拒收、凭证零错误：Xo0Q WC 3.75、kbjJ WC 3.25、kbjJ EXP 0.5、Xo0Q WE 2.5、Xo0Q IDEA 2.8、GMwR LIT 2.0、GMwR IDEA 2.6、Xo0Q LIT 1.0。**v3.6同证据复评（噪声基线）**：3.25、3.5、1.5、2.5、2.8、失败（MCP未连接——仓库原版服务器同样出现，故为大体积LIT证据包的平台问题，非v3.7引入）、2.6、1.0；v3.6自身每题平均差0.31、最大1.0（kbjJ EXP 0.5↔1.5）。v3.8与v3.6两次均值平均差0.19、最大0.5，7道中6道落在v3.6波动范围内，仅Xo0Q WC高0.5。**成本：**v3.8相对v3.6原始输入-48%，但按列表价总费用仅约-8%（缓存写入占55%、输出占28%；judge读字符为v3.6的1.5–2倍）。零调用测得：给judge私有参考的压缩视图（删source_manifest、事实原文定位/hash、与公开题面逐字重复的事实陈述）可使必读字符-29%（各题16–46%）。**v3.8审读（`rejudge-v38-review-A.json`）：**错误比v3.6复评少（3对5），LIT抓到FSQ/STE核心错误且读全31条引用，无结果EXP稳定给0；但两道WC可理解性4仍基于“符号都已定义”的错误笼统断言（v3.8比v3.6高的0.5/0.25全来自此），G2只验有引用不验支撑。**judge v3.9（用户2026-10-13“做吧”）：**`judge_v39.py`+`symbol_check.py`（叠在v3.8上）：私有参考judge视图（删source_manifest/事实溯源/与公开题面逐字重复的陈述，原件不列但可读）使必读字符-30%；控制器符号检查（未定义/先用后定义/同字母两种字体，作为候选交judge确认）能抓到已知的`a`、裸α与A/B冲突；规则19（逐条确认符号候选并写notation检查）+关卡G3（WC缺该检查即拒收）；规则20输出长度上限；MCP_TIMEOUT=120000。8道dry-run通过。**v3.9验收已跑完（8次，3363→3371，无429）：**Xo0Q WC 3.25、kbjJ WC 3.5、kbjJ EXP 0.75、Xo0Q WE 2.5、Xo0Q IDEA 2.8、GMwR LIT 2.0、GMwR IDEA 2.4、Xo0Q LIT 1.5；7/8落在v3.6两次评分范围内（Xo0Q LIT高0.25），v3.8在Xo0Q WC的+0.5消失。GMwR LIT首次被流审计判incomplete——CLI对慢MCP工具发的`tool_progress`事件未被识别，属良性平台事件；已零调用修为**v3.9.1**（审计忽略该事件，`judge_v39.revalidate`对原产出离线重走审计/校验/关卡，原结果另存`judge_run_result.audit-incomplete.json`），得2.0、三关卡全过。**成本（8道，按列表价折算）：v3.6 174万→v3.8 161万→v3.9 122万（-30%）**，原始输入-66%、输出-4%、总轮数124→48。**v3.9审读（`rejudge-v39-review-A.json`）：**符号检查与judge视图有效（WC不再误称符号全定义，压缩未丢必要内容，LIT仍抓FSQ/STE），但错误5处=v3.6复评5处且偏松（kbjJ EXP结论可信度2违反规则17、kbjJ WC忠实性4、重复扣分、符号计数不符），暂不替代v3.6。**judge v3.10（用户2026-10-13批准，触发即拒收不自动压分，+10额度→上限3383）：**`judge_v310.py`：规则21+G4（EXP按单元checks.json，全部非代码交付缺失时检验有效性/严谨性/结论可信度≤1）、规则22+G5（serious_issues点名的维度不得给4）、规则23缺陷归属对照表、规则24+G6（符号核对id须为notation-c<N>-r<M>且N+M=候选总数）、IDEA必读加任务说明与背景报告。离线对v3.9输出：G4拒kbjJ EXP、G6拒两道WC、G1拒两道IDEA（未读完背景报告），WE与两道LIT通过，无误拒。8道dry-run通过。**v3.10验收已跑完（8+2次，3371→3381，无429）：**Xo0Q WC 3.5、kbjJ WC 3.25、kbjJ EXP 1.0、Xo0Q WE 2.5、GMwR LIT 2.0、Xo0Q LIT 1.5；两道IDEA首评被拒（judge抄错64位凭证：多一位/只写4位），失败目录`rejudge-v310.failed-1`保留。零调用做**v3.10.1**（`bounded_mcp_v310.py`：每次读取附短编号R<n>，控制器按tool_state读取顺序映射回凭证后再交原校验；子进程端到端验证映射一致），重评两道IDEA：Xo0Q 2.8、GMwR 2.2，全部用短编号、六道关卡全过。新版本累计凭证错误4次（v3.6 19次评分0次），短编号为根治。成本（8道，列表价）：v3.10 约122万，与v3.9持平，比v3.6（174万）约-30%。**v3.10审读（`rejudge-v310-review-A.json`，root抽查kbjJ WC第49行属实）：**修好无结果EXP结论分、重复扣分、IDEA背景报告、反馈泄漏；但错误7处（4松1严2无分数影响：kbjJ WC把F27“would drive”写成“drives”仍给忠实性4、kbjJ EXP检验有效性1、Xo0Q WC可追溯性4、Xo0Q LIT覆盖2等）。各版本同8道错误数v3.8 3/v3.9 5/v3.10 7/v3.6复评5，单次运行、8道，差异在噪声内；继续针对这8道加规则有过拟合风险。**root建议：**冻结v3.10.1为候选，在8道之外的已试跑题上与v3.6各评一次对照验收（≈16次，需追加额度），通过再替换正式judge（全量约省三成）；其余修法（条件措辞检查等）暂记。**正式judge仍为v3.6。****用户2026-10-13：批准新题验收+12额度（上限3395），后改为只测3篇Spotlight以省token。**冻结v3.10.1，选qgsX（IDEA/LIT/WC）、qpXc（EXP/WE/LIT）、SyVP（EXP/IDEA/WC/WE）共10道（五类各2），与这些题已有的v3.6评分在同一份证据上对照（3道取`rejudge-v36/`的证据与评分，`rejudge_v38.py`新增`<run>#<subdir>`）；通过标准：错误数不比v3.6多2处以上、无系统性偏向、关卡无误拒、列表价省≥20%。**Spotlight 10道已跑完（10次，3381→3391，无429）：**v3.6→v3.10.x：qgsX IDEA 3.0→2.8、LIT 1.5→2.0、WC 3.5→3.25；qpXc EXP 0.75→0.5、WE 2.5→2.75、LIT 1.75→1.75；SyVP EXP 2.0→2.25、IDEA 2.8→2.6、WC 3.0→3.25、WE 3.25→3.25。平均差+0.04、平均绝对差0.22（小于v3.6自身0.31），升4降4同2，无系统偏向；**列表价费用218万→166万，-23.7%**，轮数187→71。关卡误拒1次（SyVP WC的G6：符号检查列表截断到40而judge按总数46计）——控制器bug，零调用修为**v3.10.2**（列表不截断、G6接受完整计数），原评分离线重走全部关卡得3.25（原结果另存`judge_run_result.gate-misfire-v3101.json`）。**held-out审读（`rejudge-v3101-spot-review.json`，root抽查qgsX WC属实）：v3.10.x错误3处（1松2无分数影响），v3.6错误5处（3松1严1无影响）；预注册标准全部达成（错误不多于v3.6+2、无系统偏向、误拒已修、省≥20%）。**v3.10.x还抓到v3.6漏掉的真实缺陷（禁止的ω0调参建议、H2a解释与自身数据矛盾、代码偏离固定方法），漏掉1处（qgsX LIT gap_grounding应为1）。单次运行、10道，属开发证据非全局可靠性证明。**→ 正式judge改为v3.10.2**（`judge_v310.py`/`judge_v39.py`/`judge_v38.py`/`judge_v37.py`、`bounded_mcp_v310.py`/`v38`/`v37`、`symbol_check.py`、`rejudge_v38.py`，均在驱动目录，未入仓库，需发git管理会话）。**注意：**旧v3.6分数与v3.10.2不可混比；search set冻结前须用v3.10.2对全部已编译题重评（≈90次，需另授权）。
- **v8.4新编译IDEA 4道**（Xo0Q、v1B4经重判；EJfL、pdF8重建，共16次调用；checks.json均已生成；§0.2.25）。
- **试跑：** 新3篇Oral共9道，均分2.32，旧论文同配置2.31（单次运行，开发证据，§0.2.25）。
- **固定配置：** 构造/审阅/裁定/builder/judge=Claude原生claude-opus-5-5/medium；executor=faithful反代claude-sonnet-4-6/low；judge v3.10.2（2026-10-13起；此前v3.6）；H0冻结v3（`D:/mrhbench-local-pilot/h0-claude-frozen-v3`，sha `619dc724…`）。
- **方针（用户2026-10-12）：** 先提升源头质量：需大修的Poster题直接换成Oral（Oral不够再用Spotlight）新建，不再花额度修。泄漏规则改动需用户同意。

**待办（建议顺序；★=零调用可直接做）**
1. ~~给v8.4新IDEA生成checks.json~~（已完成：Xo0Q、v1B4、EJfL、pdF8）。
2. ★O3记忆风险标记：给“盲推者认出论文”的IDEA单元加标记，报告时做含/不含两种口径（Xo0Q等；依据见§0.2.25的IDEA撤回分析）。
3. 试跑v8.4新IDEA中剩下的v1B4、EJfL、pdF8（Xo0Q已测2.8；IDEA实际每道约5次）。需额度。
4. **Poster→Oral替换第2步：** 在v8.4根新建Oral论文（每篇≈45次，平均出≈3.8道）。换哪几篇、换几篇由用户定；候选为140篇批准名单中未开始的Oral 7篇、Spotlight 8篇。
5. 3篇Spotlight的A2：qpXc、qgsX、SyVP的LIT/IDEA在v8.4重建（≈80次）。
6. 剩余Poster题：KeRw IDEA与aXuW LIT的A2、5qg6 LIT维护返修（≈3次）。按方针更可能直接替换，待用户定。
7. 材料小问题（U5）：GMwR EXP的task.md没写明`experiments`/`key_numbers`的类型（schema要求字符串/对象）；下次维护返修时改task.md或放宽schema。
8. ~~★S3~~ **已查（2026-10-13，零调用）：**盘点`D:/mrhbench-local-pilot/s3-release-inventory.json`——search set v1.3现有74道有效题全部已是最新发布格式，**无需重编译**（旧v5单元的最新release也已是新格式）。已为46个单元生成checks.json（40个缺失+6个改按最新维护release重生成，旧件备份`checks.json.pre-s3.20261013`）。遗留：①YOc5、n8h1 LIT（factory-v8）缺`lit_corpus_configuration.json`，BdmV/EJfL/msEr/pdF8/v1B4 LIT仍指v5库——在T17冻结库时统一写/改指；②v5/v6/v7的46道EXP/WC/WE题面没写`cpu.run(script, arguments, timeout_seconds)`签名（构造者写的内容，重编译加不上；若要加须新平台说明，待用户定）。
9. ~~T17~~ **已冻结（2026-10-13，零调用）：`D:/mrhbench-local-pilot/shared-library-v8`**（factory-v1…v8_4全部背景，655篇=v7的608+新Oral 47，跳过1篇同v7；corpus sha `686bca8f…`，1312文件逐个hash，`FROZEN.json`/`file_manifest.json`，仓库副本`audit/search_set_v1_3_library_freeze.json`；脚本`freeze_library_v8.py`）。v1.3全部14道LIT的`lit_corpus_configuration.json`改指v8（备份`*.pre-t17.20261013`），YOc5/n8h1按其frame截止日2024-10-04补建。pilot dry-run验证：BdmV LIT通过（可见650篇、证据679条）；第2道起因系统内存不足被系统停止（非脚本错误），剩13道待重跑（建议每道单独进程）。**全部重评/试跑估算（零调用，`D:/mrhbench-local-pilot/v1_3-rejudge-pilot-estimate.json`）：**90道中80道需完整试跑（从未试跑59、题面改过19、LIT因换库2）、10道只需v3.10.2重评；方案A≈906次（上限≈1300），方案B（题面改过的19道只重评旧运行）≈741次；待用户定方案与额度。**用户2026-10-13选B（“想先尽快拿到整体结果，额度不充裕”），+745（上限3575→4320）。**计划`D:/mrhbench-local-pilot/v1_3-v3102-plan.json`（`plan_v13_v3102.py`）：沿用已有v3.10.x评分12道（0次）、v3.10.2重评旧运行17道、完整试跑61道（LIT 14/IDEA 13/WC 12/WE 12/EXP 10），估约729次。**在跑：**计划任务`mrh-v13-scoring`（`run_v13_scoring.cmd`→`run_v13_scoring.py`：先重评后试跑，每题单独进程`pilot_v310.py`（=pilot_v5流程+judge v3.10.2），按IDEA→WC→WE→EXP→LIT，撞429即停、续跑跳过已完成），输出`D:/mrhbench-local-pilot/p11-v13-v3102/`，日志`v13-scoring.log`，汇总`v1_3-v3102-summary.json`，结束写`v13-scoring.done`；release-s3的46道试跑用`@release-s3`。
10. T15：冻结search set题目清单（题目ID、发布包hash、预算/资源、库版本、judge、executor、H0 hash；每道新题至少试跑一次）。
11. git：**已提交（2026-10-14，用户批准）：**工厂驱动10-12清单75个+v8.3+v8.4共88个文件（`scripts/factory_v5_driver/`，含`prompts_next/v8_4/`、`tests_v8/`）与本文。按用户决定search set相关`audit/`新文件（membership/held-out池/审稿分审计/库冻结副本）不提交；账本运行中不提交。**待提交（等用户“提交”）：**judge v3.7–v3.10.2、search set v1.3构造、S3/T17、v1.3评分等驱动文件（清单已由material package pipeline optimization会话发git管理会话）。
12. 之后：T18第一轮演化（单轮完整search评测约1,200–1,500次，需另授权）；T19 test set（可从held-out池v2及未用候选选源）。

**待用户决定：** 待办4–6的范围与对应额度；第一轮演化额度；配额违规计分规则；OS级隔离环境；test set规模。演化轮数R与重复次数在第一轮后定。

**已知限制：** 背景文献只从arXiv取，非arXiv领域（如神经科学的kbjJ）背景天然不足；Bt1v背景只取到2/21篇。O3做不到真正“无记忆”对照（没有知识早于ICLR 2025的可用模型）。

**代码与运行约定：** 仓库核心`research/benchmark/mrhbench/`；工厂驱动`D:/mrhbench-local-pilot/factory-v5-driver/`（大部分未入仓库）；运行目录与审计副本在`D:/mrhbench-local-pilot/`（不入git，勿清理）。撞429即停，额度恢复后手动`schtasks /Run`；`failed_needs_attribution`须先核因、把阶段挪成`<stage>.failed-N`并写history，再重跑。计划任务触发器一律`/SC ONCE /SD 2020/01/01 /ST 00:00`。

## 历史交接记录：2026-09-27，Codex → Claude Code（已完成，仅供追溯）

**结局（2026-10-06补记）：** 下文的v5降本对照已完成：旧臂调用622–624，审阅revise、裁定drop（旧流程整包重写把被排除的作者结论重新写进公开事实）；增量臂619–621通过。增量臂总输入/输出/模型时间分别比旧臂少26.3%/30.8%/28.1%，**未达到**预注册的45%/50%目标（`D:/mrhbench-local-pilot/factory-efficiency-v5-20260927-001/audits/pair_result_v1.json`）。之后v5生产工厂采用了含增量返修的质量组合（§0.2.20前、`factory_v5.py`）。下文其余内容保持原样，状态以“当前断点”与§0.2.20之后为准。

**用户因Codex额度即将用完要求交接。Codex已停止新增调用，goal工具已返回`paused`（不是完成）。下面是当前断点；旧§0.2历史次数/状态不能覆盖本段。Claude Code按用户交接继续同一目标，不需要重跑已完成步骤。**

### 当前断点与预算

- 工作区：`C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench`；`master`，HEAD `fbe302f9afaa29a1b6032fcf47cfce2ed0415f05`。交接时134项git状态条目，包含此前工作，**未替用户commit/push/reset/clean**。大量不可替代证据在D盘，不在git内，勿清理。
- 权威ledger：`research/benchmark/audit/development_call_ledger.json`，**621已用、0reserved**。用户本goal累计上限**700**，余79（失败也计数）；全局1668不是本goal可用上限。当前v5小阶段**baseline618、最多6次、硬止624**，余3，正好旧臂。第一429即停、不自动重试/买额度，不用完额度为目标。调用数不包括本对话/协作agent全部系统消耗；订阅美元未知。
- 当前试验根：`D:/mrhbench-local-pilot/factory-efficiency-v5-20260927-001`（下称V5）。`execution/manifest.json`冻结156代码/prompt/config文件，交接再次verify通过；**不改任何绑定文件**。新工程修改必须另存版本/另freeze，不修改历史候选、失败、源缓存或旧审计。
- 首臂`write_content_repair/incremental`调用619–621已经全部terminal，session41267已exit0；没有本阶段在途模型调用。3个协作agent均completed。烟雾容器已实际核无残留。**旧臂目录尚不存在，尚未启动call622。** 不因旧lock/started文件猜测活进程；以后观察超时先核同handle，不重启。

### 已完成、可接续的证据

- 全离线622项：610过、12依赖跳过，219.069秒，`research/benchmark/audit/factory_efficiency_v5_full_tests_pre_freeze.log`。v5 driver5整链/负测、batching4及输入预检已独立复核。原146/150历史冻结也核未变。
- V5案例仍是原预选未用于efficiency比较的`iclr2025-6ouZaBzeNO`、单WRITE_CONTENT、round2，顺序**incremental→old**。40输入文件逐字节复制、24来源hash匹配；fresh指本次对照未跑，不是从未构造/审核。两臂相同full policy/identity/paging/decision consistency；增量多seed/navigation及可选批量Read提示，测流程组合，不称纯constructor因果。
- `arms/write_content_repair/incremental/result.json`：completed，620 reviewer pass_with_pending_runtime，621 adjudication pass。三call总输入**6,471,033（含cache write/read）**、输出**60,166**、模型**688.017秒**、pipeline**696.063秒**。未跑旧臂，**不能报告新降幅**。
- 619候选实际runtime：`runtime/write_content_repair/incremental/runtime_record.json` passed，fresh1CPU/1GiB/64PIDs/512MiB/600秒环境，非root/无网络/只读3公开文件，smoke3.14秒。不是完整solver预算充分性或正式隔离验证。
- actual release在 **`release_staging/write_content_repair/incremental-002`**，task+3资产，known identity0、binary0。初次`incremental` staging因root错误把source_manifest传成字符串而失败；`audits/incremental_compile_invocation_error.json`保留归因。第二次使用constructor/request.json的sources数组，没改candidate、没重新调模型。不要误用第一次不完整staging。
- 科学/最终发布独立报告：`audits/write_content_incremental_independent_science.json`、`write_content_incremental_independent_release.json`，local-development pass，无blocking。共享审阅260.050521秒，不能将两报告字段相加。24来源为全库存身份绑定，不称所有全文已读。盲审在未读620前完成，后另补native意见及最终面。
- 全轨迹：`audits/call619_constructor_independent_audit.json`、`call620_reviewer_independent_audit.json`、`incremental_native_full_trace_audit.json`，务必同时读`incremental_native_trace_delivery_clarification.json`：原字段名误写35，实际32 mathcells，数组正确，旧审计未覆盖。620/621各一次密集HTML bulk Read超25k-token工具上限，之后补取必要公式/条件；620全部Eq1–12、621Eq4–12与引理/B2关键条件送达，不称全论文/完整证明读完。不存在已观察的阻塞轨迹/结构完整性缺陷。
- root已另存 **`audits/write_content_repair.incremental_gate.json`**，绑定science/runtime/actualrelease/trace及计数澄清；已实际执行v5`check_order(..., 'old')`通过，**没有启动旧臂**。交接预检`audits/claude_handoff_preflight.json`记录621/0reserved、156freeze与gate。此gate只允许开发对照下一臂，不是公开发布/正式benchmark准入。

### Claude接手的下一步（不要从头来）

1. 读本段、`research/benchmark/audit/factory_efficiency_v5_cases_v1.json`、`factory_efficiency_v5_phase_authorization_v1.json`和上述gate/reports；核实时ledger仍621/无reserved、old不存在、156冻结未变。Python为`D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe -X utf8`，PowerShell设置`$env:PYTHONPATH='research/benchmark'`。角色保持claude-opus-5-5/medium，不因交接改变比较配置。
2. 仅在确认上述状态后启动原计划旧臂（最多3次、止624），不再跑incremental：
   `& D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe -X utf8 research/benchmark/scripts/active/run_factory_efficiency_v5.py run --root D:/mrhbench-local-pilot/factory-efficiency-v5-20260927-001 --case write_content_repair --arm old`
   将输出另存V5新log并记录session。首次429/失败停，不绕开gate追调。所有旧模型输出保留。
3. 旧臂完毕后同样独立审核完整轨迹/必要原文/全公开面；先读生成Dockerfile、requirements、smoke再执行新容器runtime。release使用新目录，`source_manifest`必须传该constructor/request.json的`sources`数组，不传路径字符串。两臂release settings已在`audits/write_content_release_settings.json`固定4模型/60工具/600秒、16MiB/500entries，只是开发候选值；旧臂不得另调低科学要求/资源。
4. 两臂都达到同等质量后，按完整三角色input（含cache）/output/model time/pipeline time算每例降幅，失败与人工审阅另外透明报告，不虚构美元或声称覆盖全订阅系统消耗。保持原冻结targets（aggregate input/time≥45%降低、output≥50%，希望接近既有约50%/60%），不得看结果再改门槛。**V5仅第一组新鲜对照**；goal还需第二组新鲜案例、质量/成本通过后的未调试单元prospective。后续阶段另存有界授权/冻结，总帽仍700，不把单WRITE通过改写为全部目标完成。

### 不要丢失的失败与后续诊断

- 613–615 EXP drop（作者趋势泄漏），616–617矛盾pass+core_science issue被拒；618另存显式adjud诊断drop（绝对下降量误判比例弱化）。这些永久保留，旧EXP未配对，不能计成功降幅。root未手修候选冒充模型通过。
- `D:/mrhbench-local-pilot/factory-scope-preflight-20260927-001/`有H2新操作化、9个逻辑边界例及独立审核/root_scope_decision：仅批准未来独立development_regression输入，不追认历史通过、不称新鲜。H2固定选择性去共享，solver选择合理归一化/相对/匹配对照，H1不暗中加严；方法/资源不变。尚未应用/调模型，先完成当前V5比较。
- 新小模块`material_decision_guidance.py`只提醒既有issue/unknown不能pass；`evidence_read_batching.py`只给可选读取调度，不能减少科学证据/独立review/adjud或改输出。已冻结于V5，不再编辑。
- `audit/source_navigation_oversize_diagnostic_v1.json`（research/benchmark下）显示此paper三个unit因text+巨量child_ids超16KB，整个分页fallback；并非只有17KB长text，数学已经用alttext。未来可另存精确可重建text+child_ids分片，**尚未实现、未证降本**。不删嵌套locator骗取压缩；先看本对照结果再决定改造，勿改变正在比较的156冻结版本。
- 版权公开再分发/完整solver/正式judge与benchmark准入仍未通过；本goal不启动正式评测、批量扩产或服务器迁移。AGENTS仍是唯一工作记忆，不另立HANDOFF/PLAN/STATUS文档。

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

**阅读顺序：下表已于2026-10-12按当前状态更新；§0.2.1–0.2.19为历史快照，最新进展见§0.2.20–0.2.24、文件开头“当前断点”及实际账本/state。**

| 项目 | 当前状态 |
|---|---|
| Builder/evolver | **Claude Code原生agent**（claude-opus-5-5/medium，订阅登录；用户2026-09-24改定）。H0 v3已冻结（接口v4，§0.2.13）；旧gpt-5.6-sol+Codex记录为历史配置，不混算。尚无真实科研演化 |
| Executor | **claude-sonnet-4-6 / effort low，经faithful claude-code-openai-wrapper反代**（2026-09-30改定，§0.2.20；2026-10-06用户确认正式运行也用它，§0.2.23）。opus-5-5过强、haiku-4-5过弱已弃用；此前opus/ClaudeJSONTransport结果仅作开发证据 |
| Judge | **Claude Code原生agent**（claude-opus-5-5/medium，受控MCP取证）**v3.6**（v3.4+规则1–10），10题逐轨迹验收带保留通过（§0.2.20）；同次评分+feedback。全局可靠性未证，Codex v2.8为历史 |
| 材料构造模型 | **Claude native**（constructor/material_reviewer/adjudicator/source_auditor/scout，opus-5-5/medium）经标准工厂流水线（factory v5→v8.2，§0.2.16–0.2.24；LIT/IDEA用v8.x不见论文的公开面流程）；root与用户只做终验。旧Luna/sol构造为历史 |
| 调用授权 | 共享开发账本上限**3318**（2026-09-24起逐次追加：368→568→1668→1818→1868→2318→2918→3168→3318，见ledger authorization_events）；2026-10-12晚已用3265。失败/429计入；订阅不虚构美元。正式演化需另授权 |
| Goal/协作 | 用户在线逐点决策；本机试产，未迁移服务器；git提交由用户指定的git管理会话负责（其他会话只提交文件清单）；不启动未确认的正式评测 |
| 已有交付 | search set v1.2：22篇、已编译88道，题目清单未冻结（§0.2.24–0.2.25）；共享文献库v5（271篇）；工厂v5–v8.4；冻结H0 v3；judge v3.6；48道题的P11试跑分（Sonnet4.6/low，均分约2.3，开发证据）；只读控制台 |
| 既有测试 | 仓库离线全量测试以git管理会话最近一次提交时的运行为准（见提交记录/日志）；factory-v8/v8.1/v8.2驱动39项离线测试通过（`factory-v5-driver/tests_v8`）；Docker包级镜像与烟雾随每个单元的runtime门实际执行。测试不替代材料语义或judge验收 |
| 未通过关键项 | 8道旧LIT/IDEA待A2、Poster→Oral替换第2步未做；search set题目清单与文献库版本未冻结；test set未构建；OS级角色隔离未验证；judge全局可靠性；真实混合演化未运行；正式配置（轮数/重复/样本量）未定 |

账本额度是开发transport调用上限（构造、审阅、裁定、试跑executor/judge都入同一账本），不含本对话/研究协作subagent的完整系统用量；不得声称覆盖全部订阅消耗。缺失usage不记零，订阅不虚构逐次美元成本。额度授权不是必须用尽的目标，也不是已定正式样本量。

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

### 0.2.13 Codex额度耗尽后的角色transport改定 [历史，2026-09-24]

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
  - **逐轨迹审阅** `audit/claude_integration_v2_review_v1.json`（85份转录/提交hash）：WC/IDEA/LIT/WE均`measurement_valid_with_caveats`，EXP `not_a_valid_measurement`。要点：WC唯一扣分（字数）依赖计词口径（706/621/552），判“fail”偏自信；IDEA提案接近隐藏SSA方法，记忆污染不能排除；LIT低分是合法测量——**新H0缺陷**：只把最近4条原始观察放进上下文（setting与CAFe页读过但写作时不可见），且未用record_note；WE——**新H0缺陷**：从不告诉executor公开资产挂载在`/inputs/public/...`，浪费4次调用，脚本内嵌CSV并误称未挂载，另有真实agent错误（图注“RSD 0.941 exceeds SSA 0.943”、manifest缺逐格定位）；审阅者查看了同一2000×847图，认定所有计分视觉结论在该分辨率可辨，3.0可辩护。v3.4后judge已实际读tile并仍给3.0。EXP：科学实际运行（120条轨迹，stdout有H1–H3），配额超限归因被测harness（V3-7使128MiB只存在于未展示的resources，executor只见disk_mb 1024），直接原因是保留全部20000次迭代而中位收敛263–762；controller按T06处理正确，但收集遇首个超限文件即停致小的report.json也丢失，且无预注册的“harness致配额违规”计分规则→当前得不到测量。**待用户决定：** 配额违规规则（例如跳过并记录超限文件、收集其余、带违规标记评judge）。其他建议：大输出包在题面写明收集上限；WRITE_CONTENT字数口径或controller计数。
- **材料repair一轮：** root裁定`audit/material_claude_round1_adjudication.json`（接受FTCT F1–F6与Diffusion F1–F6，确认Alg.1 line10标签更正；**拒绝**构造者未测量的资源上调，FTCT保持600秒、Diffusion保持1200秒/512MB）。Claude constructor+reviewer一轮（`D:/mrhbench-local-pilot/material-claude-20260924-004-repair`）后两包均`pass_with_pending_runtime`；runtime构建/烟雾/泄漏字符串检查进行中（`audit/material_runtime_verification_round1.json`），Gaussian维护者包的独立审阅进行中（`audit/gaussian_exp_independent_review_v1.json`）。
- **材料runtime验证（0模型调用）：** `audit/material_runtime_verification_round1.json`：FTCT与Diffusion镜像按固定python:3.12-slim digest构建（`mrhbench-pilot/ftct-write-v2:e6e5d918b500` ID `61ba1829…`；`mrhbench-pilot/diffusion-exp-2d-v1:ac07e25c2e4c` ID `70114ade…`），全部依赖精确安装；烟雾在声明资源、无网络、只读根、非root下通过。controller填的hash全核对一致；私有文件不在镜像/公开挂载中（Diffusion私有review_notes位于assets/exp_2d/private/，挂载时须排除）。Diffusion在默认root-owned tmpfs下失败，但本项目ContainerSession已用`--user 10001`且/work、/tmp tmpfs `uid=10001`，属已满足条件。遗留：pip未hash锁、资源未经真实agent测量、rights/首披露/judge集成待定。
- **Gaussian独立审阅：** `audit/gaussian_exp_independent_review_v1.json`判revise：方法语义对照原文与notebook全部忠实；**R1重大**——固定C=1归一化下标签二阶矩随α约升52倍，H3（误差随α升）近乎自动成立（零预测也“支持”），须重述为作者真实主张且比较基准由solver论证公平；另R2公开NOTICE暴露论文/仓库身份、R3公开资源理由泄露“2400次拟合”规模等7项低/中问题。root全部接受，维护者repair进行中（新目录maintainer_candidates_v2，原包保留）。
- **judge v3.4：** Claude的WRITE_EVIDENCE提示词显式列出tile记录（Codex v2.8文本不变），重评WE时judge读了两块tile，分数仍3.0。
- **构造批次结果与控制器哈希：** 两个constructor（call234–235）均完成且stream admissible，但结构门拒绝：无shell的构造者无法算sha256，各自写了占位（`PENDING-run-tools/fill_asset_hashes.py`、`UNCOMPUTED-no-hash-tool`）——属我方profile缺口，非构造质量失败。新增受信控制器步骤`material_batch.fill_sentinel_hashes`：只替换哨兵值为实际字节hash、保留原package、逐项记录、绝不执行构造者写的代码；今后Claude批次提示写`CONTROLLER_FILL`并自动填。`resume_material_review.py`把已完成构造复制到新批次（原批次不动）、填hash、过门、起独立reviewer（不重跑constructor）；dry-run两包过门（30/13处填充）。首次resume（-002）因目录未建失败、未花调用；-003运行中。
- **Git：** 按内部研究代码库标准初始化跟踪（commit `7acae41`起）。`.gitattributes`设`* -text`（审计按字节hash，全局core.autocrlf=true会改写换行）；`research/source_cache/`只跟踪manifest（第三方原件留本地，凭URL/version/sha256复核）；原始session rollout留本地不提交（两份旧Codex rollout含sk-形字符串，需用户本人检查，root未读取其内容）；修正旧规则误忽略整个`runtime/`（接口与worker代码现已跟踪），仅忽略`runtime/codex/`。提交前对待跟踪集做密钥形/邮箱扫描为零命中。D盘试产目录不在仓库内。
- **用户新授权（2026-09-24）：** 新增100次Claude开发调用（失败计入），账本上限268→368（授权时已用233，已记入ledger authorization_events）；三角色确认claude-opus-5-5/medium；新论文材料构造改用`ClaudeNativeRunner`作为账本记录的`constructor`角色（维护者subagent起草的Gaussian包仍标维护者构造，不冒充constructor产物）。

### 0.2.14 暂停与交接（2026-09-24，用户要求暂停）

- **用户纠正（最高优先，下一步先做）：** executor的“反代API”应使用GitHub项目 **claude-code-openai-wrapper** 做反向代理（把Claude Code订阅包装成OpenAI兼容API），而不是本轮实现的`ClaudeJSONTransport`（`claude -p`关工具+结构化输出）。因此§0.2.13中所有**executor**侧结果（集成v1/v2、IDEA重跑、reasoning拒绝/键别名/结构化输出等transport结论）只是**未获批transport下的开发证据**，不得作为executor基线、H0能力或演化信号；builder/judge走Claude Code原生agent的部分不受此纠正影响（仍按用户§0.2.13决定）。下一步：取得并审阅该wrapper（固定版本/commit、许可、本地启动方式、是否关闭其自身工具、是否支持图像与结构化/JSON输出、如何计次入账），实现`OpenAIWrapperTransport`（与`complete(request, output_schema, role, images, ...)`同签名，凭据留controller、不进容器），真实探针后按§7.2/T01重新验收，再重跑H0集成。未审阅前不要假设其行为（例如是否同样触发reasoning_extraction拒绝、键长限制、图像缩放）。
- **暂停时刻状态：** 账本311/368，无reserved。新论文集成`D:/mrhbench-local-pilot/claude-integration-20260924-005-newpapers`被root按用户要求中止：diffusion-exp阶段已完成7次executor调用（305–311），未采集、未评judge、无结果，不计测量；FTCT两包未开始。已杀控制器进程树，并删除带本项目session-owner标签的遗留容器`mrh-session-7b7136…`（镜像为Diffusion镜像）；无其他本项目容器。Gaussian v2独立复审subagent被用户停止，未产出审计文件（`audit/gaussian_exp_independent_review_v2.json`不存在）。
- **已完成待用的产物：** 冻结H0 v3（`D:/mrhbench-local-pilot/h0-claude-frozen-v3`，在接口v4/typed错误平台上development_admissible）；judge v3.4（Claude原生，精确schema、图像缩放核验+tile）；接口v4（typed broker错误，消息冻结测试）；Claude constructor/reviewer流水线（material_workspace档、controller填hash、resume/repair）；新包`materials/pilot_v3/claude_candidates_v1/{ftct-write-content,ftct-write-evidence,diffusion-exp}`（已编译、镜像已建并烟雾通过、全部gate pending）与`maintainer_candidates_v2/gaussian-exp`（R1–R8已修，待独立复审）。
- **仍待用户决定：** ①配额违规计分规则（建议：跳过并记录超限文件、收集其余、带违规标记评judge；实现需改沙箱导出助手，未做）；②正式split/样本量/轮次/重复（T14）；③原生OS级隔离环境（Windows提权sandbox或独立Linux；Claude builder/judge已做到启动即无宿主工具，但CLI宿主进程本身未OS隔离）；④Gaussian复用IV镜像是否可接受；⑤Diffusion许可（CC BY-NC-SA论文+代码非商业附加条款）下本项目是否算非商业用途。**⑤已答（2026-09-24）：本项目为学术论文项目、非商业用途**；仍按NC/ShareAlike与Tufts附加条款逐资产记录，不向solver发布作者代码/原文的既定裁定不变，公开发布时再做rights gate。
- **已知小问题待修：** `run_claude_integration.py`计划文件中`judge_version_expected`常量仍写v3.1（实际judge版本以各result的`judge_version`为准，应改为导入`CLAUDE_VERSION`）；编辑脚本须用`write_bytes`/`newline=''`保留原换行（Windows下`write_text`会把LF改CRLF，影响按字节hash）。
- **交接入口：** 本节+§0.2.13为最新工作记忆；git已跟踪（见§0.2.13 Git条，最近提交见`git log`）；D盘`D:/mrhbench-local-pilot/`存放全部运行目录与原始转录（不入git）。最新离线测试：`controller-venv`下325项；交接时第一次运行出现1个error、立即重跑全部通过，疑为时序相关的偶发测试，尚未定位（日志`D:/mrhbench-local-pilot/tests-handoff.log`为通过的那次）。

### 0.2.15 executor反代：claude-code-openai-wrapper faithful模式（2026-09-24，历史；executor现状见§0.2.20/0.2.23）

- **账号：** 用户`/login`后CLI登录到新的claude.ai组织；账本延续（上限368），新调用在新账号下。
- **wrapper与固定版本：** RichardAtCT/claude-code-openai-wrapper commit `aaad0b96a4cd…`（MIT），checkout在`D:/mrhbench-local-pilot/proxy/`（不入git），claude-agent-sdk 0.2.159（内置CLI 2.1.281）。lock不一致：去掉mcp固定（解析为1.30.0）与Windows不可装的uvloop；freeze见`research/benchmark/runtime/wrapper/wrapper-venv.freeze.txt`。
- **原版不等于API（代码审查+实测）：** 客户端system消息被静默丢弃（`{"type":"text"}`不被SDK识别→CLI用默认Claude Code系统提示；call328问名字答成“能在工作区运行命令的Claude agent”）；不传setting-sources（加载用户设置/hook/技能）；工具只用过时denylist；`filter_content`改写提示与回答（删`<args>`/`<thinking>`等、替换base64文本；call329模型看到被删改的提示，回答里的`<args>ok</args>`被删）；图片丢弃；usage按len/4伪造；无response_format；启动时自带一次“Hello”付费调用（312/327已补记账本）；CLI在safeguard拒绝后**静默换用claude-opus-4-8回答**（call317，model_refusal_fallback），并启用服务端advisor工具。
- **faithful补丁：** `runtime/wrapper/faithful_mode.patch`（sha `355b83b3…`，`WRAPPER_FAITHFUL_API=1`才生效，原行为可复现）：只用客户端system消息；`--tools ""`、无setting sources、strict MCP、禁slash命令、不持久化session；CLI环境关闭refusal/model fallback、advisor、attachments、memory、CLAUDE.md、git说明、内置/策略技能、后台与非必要流量、遥测；用户内容原样（data-URL图片作真实图像块）；json_schema走结构化输出；reasoning_effort→--effort；真实usage；拒绝→200+`finish_reason: content_filter`；上游4xx原样；出现非请求模型或任何工具即502；不支持的参数（temperature/tools/多轮/远程图片/stream）返回400而不模拟；启动零调用。启动入口`research/benchmark/start_executor_wrapper.py`（校验commit、补丁字节、SDK版本，仅127.0.0.1，剥离CLAUDE*/ANTHROPIC*）。
- **一致性验证（官方openai SDK 1.109.1，仅base_url不同）：** 零成本拒绝5项全对；C1 system提示生效、C2提示/回答不被改写、C3 json_schema、C4 data-URL图像、C5拒绝以content_filter如实返回且无换模型——全部通过；中性算术只服务claude-opus-5-5、1轮、无工具；executor transport端到端（动作schema+图像）通过。313–316早于关闭fallback、321/324早于ResultError映射修复，均作废。**两条经错误transport得到的平台结论在正确路径复核仍成立**：`reasoning`字段被拒（331）、属性键≤64字符（332）。
- **残余差异（如实）：** 订阅OAuth必经Claude Code，CLI前置身份/归因system块与oauth beta头，每请求约多400输入token，无法在受支持路径内去除；temperature等采样参数不可设（拒绝而非模拟）；每请求单轮；CLI对长边>2000px图像降采样（executor侧tile未做）；Opus 5.5 safeguard对部分良性写法会拒绝（模型级，托管API同样存在）。
- **实验分类：** `audit/experiment_transport_classification_v1.json`。受影响（executor走错transport，不得作H0基线/演化信号，须经wrapper重跑）：A1探针196/205/231/232/295；A2集成v1（211–230）；A3集成v2与IDEA重跑（239–302中的executor/judge）；A4中止的新论文集成305–311。仍有效：Codex时代1–195（独立历史配置）；judge合成fixture重验证及探针197–198/200–210/236–237；builder H0 v1/v3（199、233）及其审阅；材料构造/审核（234–304中构造与reviewer）；全部零调用工作与平台修复。A3中judge行为证据与读H0请求得到的H0缺陷仍有效。模型纯度扫描：切换前116份Claude转录全部由claude-opus-5-5作答，仅探针232发生过静默fallback且已被拒收。
- **补充核查（call333–336，`audit/executor_wrapper_conformance_v2.json`）：** 用本地只记录请求体、不记录认证头的直通代理（`runtime/wrapper/capture/body_capture_proxy.py`，经`ANTHROPIC_BASE_URL`）拿到CLI附加内容原文：system前两块`x-anthropic-billing-header: …`与`You are a Claude agent, built on Anthropic's Claude Agent SDK.`；最新user消息前插入含**账号邮箱**的`<system-reminder>`；末尾追加`# Environment`系统消息（工作目录、平台、Shell、OS、模型名、知识截止、日期）；另有metadata.user_id（设备/账号/会话ID）。CLI源码闭源（anthropics/claude-code仓库仅文档/插件，All rights reserved），邮箱仅在`ANTHROPIC_UNIX_SOCKET`时跳过（非开关），`CLAUDE_CODE_HIDE_CWD`实测无效；root不采用在代理里改写CLI请求的做法（会把订阅变成任意API隧道，疑违条款），交用户决定。原始捕获含邮箱/ID，只留D盘。再探开关（call337）：`CLAUDE_CODE_SIMPLE=1`（即`--bare`）会关闭OAuth登录（“Not logged in”、0次API请求），订阅下不可用；`CLAUDE_CODE_USER_EMAIL`仅在无账号记录时与账号/组织UUID一起填充账号，不是屏蔽开关。结论：受支持路径内无法去掉邮箱提醒与Environment块，剩余只有代理改写（未做，待用户决定）。
- **采样参数：** 经Claude API参考核实，claude-opus-5-5等当前模型的Messages API本就移除temperature/top_p/top_k（400），faithful模式同样400，**不算差异**（更正v1页面说法）。
- **多轮已修复：** stream-json输入路径不忠实（call333：assistant被提前、两条user被合并）；改用CLI自身`--resume`读取临时会话转录，历史以真实user/assistant角色按序到达API、历史中的图片为图像块，调用后删除转录（call335/336捕获核验，336答“Blue”、单请求、仅claude-opus-5-5）。faithful模式现接受[system?]+user/assistant交替历史并以user结尾；assistant历史仅文本。
- **审计与展示：** `audit/executor_wrapper_conformance_v1.json`；给用户的说明页 https://claude.ai/artifact/RSWUk7ZumdXQMhu3CBdnvo （源文件`D:/mrhbench-local-pilot/proxy/report/executor-proxy.html`）。**用户决定（2026-09-24）：不做代理改写；该wrapper反代仅作初步实验，正式实验将由用户向导师申请官方API额度，届时executor改接官方API（wrapper结果不与官方API结果混算）。**账本337/368；capture代理已停；wrapper当前在127.0.0.1:8765运行（faithful模式），重启用`start_executor_wrapper.py`。下一步：经wrapper重跑冻结H0 v3五类集成（上限55次），此前的executor侧分数不再引用。**【后续：2026-09-30 executor改为Sonnet 4.6/low（§0.2.20）；2026-10-06用户决定正式运行也用此反代executor，不再改接官方API（§0.2.23）。】**

### 0.2.16 规模与材料构造分工改定（2026-09-24，用户决定）

- **规模暂定70篇论文**（小而精，质量优先；实测Claude构造+审阅+返修一轮约28–30分钟模型时间、按官方价折算约11美元/篇，另有大量未计量的维护者裁定工作）。不是冻结的正式样本量，T14仍需确认。**【2026-10-06：先以已构造的25篇作为search set v1并冻结名单（§0.2.23）；test set另选论文，规模待定；70篇不再是近期目标。】**
- **构造须走标准pipeline：** 由固定版本prompt驱动的独立模型会话（`ClaudeNativeRunner`各角色，入账本、独立workspace、不继承本对话/AGENTS.md）完成选源、源审计、歧义裁定、构造、审阅、意见裁定与返修；controller只做确定性步骤（取源/hash/结构门/镜像构建与烟雾/泄漏检查/编译/试跑调度）。**root与用户只做最终质量验收**，不再由root亲手写scope/裁定/构造包。此前root手写的FTCT/Diffusion job scope与裁定、维护者起草的Gaussian包均记为pipeline前的手工产物。pipeline阶段设计已获用户确认（2026-09-24，全部按root建议）：P0候选池(controller)→P1 scout初筛(约10篇/次)→controller按固定规则选约140篇进全文→**用户看一次选中名单**→P2取源(controller)→P3源审计→P4歧义裁定(独立会话，产出构造任务单)→P5构造/P6结构门/P7审阅→P8意见裁定→P9至多1轮返修→P10运行验证+编译(controller)→P11每题试跑一次(冻结H0+executor+judge)→P12验收档案。终验：前10篇逐篇细看，之后全部被标记包+其余随机20%。裁定会话用opus-5-5/medium全新会话。真实运行待额度。
- **factory已实现（2026-09-24，0模型调用）：** 编排`mrhbench/factory.py`（阶段状态机、每阶段全新workspace、输入hash保护、jsonschema校验输出、每次调用`CallBudget`+账本双重上限、prompt/policy在init时冻结hash、变更须新factory根、终态dropped/blocked_source/failed_needs_attribution不自动重试、第2轮裁定只能pass/drop）；取源`mrhbench/factory_sources.py`（候选池+README/许可、arXiv精确标题匹配与版本史、≤会议结束日的最新版、git blobless克隆定位会议结束前commit并按优先级抽取≤300文件/10MiB、背景论文严格早于cutoff）；运行/编译/档案`mrhbench/factory_runtime.py`（每包独立镜像`mrhbench-factory/<slug>:<ctx hash>`、FROM只许python:3.12-slim并由controller锁digest、声明资源下无网络只读非root烟雾、公开资产挂`/inputs/public`、≥40字符/5词字符串泄漏检查、编译为TaskView且gate全pending、dossier与终验抽样）；固定prompt与规则`prompts/factory/`（policy.md A–H规则、scout/source_auditor/adjudicator_source/adjudicator_review及schema、constructor_addendum运行契约）；CLI`run_material_factory.py`（init/pool/triage/select/approve-selection/run/status/review-queue；P11试跑用`--harness`冻结H0+`run_container_stage_development.run_stage`）。新增角色scout/source_auditor/adjudicator入账本。离线测试：factory 7+sources 11+runtime 19，全量370项通过（`D:/mrhbench-local-pilot/tests-factory.log`）。真实Docker零调用核查：旧FTCT/Diffusion包镜像重建ID与此前一致、泄漏0，但烟雾按旧相对路径找资产而失败——预期，因factory新挂载约定已写入constructor_addendum，旧包不迁移。factory根`D:/mrhbench-local-pilot/factory-v1`已init，P0候选池README/许可抓取进行中（仅网络）。**尚未做**：任何模型阶段真实运行（triage约40次、每篇构造阶段约6–8次、试跑每题约10–20次，待官方API额度）；R2共享库并入新背景论文（编译阶段仍未接）；试跑前需确认executor走wrapper或官方API。
- **常设规则：全部模型调用的成本与结果必须完整留存（用户2026-09-24再次强调）。** 用途有二：debug/审计，以及benchmark最终的performance–cost帕累托曲线。任何涉及模型的调用（executor/judge/builder/evolver/constructor/reviewer/scout/source_auditor/adjudicator/探针）都要：入共享账本（失败、429、超时也入账，缺usage记null不记0）；token分拆为未缓存输入/缓存写/缓存读/输出，另存墙钟；保存完整轨迹（原生Claude=`events.jsonl`全流；executor=每次HTTP请求体与响应体+`result.json`，含wrapper `raw_usage`）与模型产出文件，不删不覆盖（失败尝试改名`.failed-N`保留）。`report_run_costs.py --run <dir>`按角色/任务汇总并给出按官方列表价的估算美元（订阅不按次计费，估算须标明）。帕累托所需的每题成本=executor+judge（外层演化另计C_build/C_edit/C_feedback/C_test，见§9.2）。
- **429限额事故（2026-09-24）：** scout首轮40次调用全部撞订阅session limit（HTTP 429、0 token、各<1秒），账本计为调用338–377（失败入账），不是初筛结果。已修：两transport把429归类`ProviderRateLimit`；factory首个429后即停机（后续调用在入账前拒绝），状态`platform_rate_limited`，`--retry-platform`显式重跑并把失败尝试改名保留。
- **全文来源优先级（用户2026-09-25决定，待实现）：** 今后取源应**优先从OpenReview取全文**（会议camera-ready PDF），arXiv作备用/版本史与最早公开日期证据；首批已按arXiv取得的论文不改。factory_sources尚未实现OpenReview取文，下次改取源代码时实现（首批2篇`arxiv_not_found`即可由此补救）。
- **factory首批运行与v2（2026-09-25/26）：** 用户批准140篇名单（`selection_approval.json`绑定选单hash）并追加1100次（上限1668）。前10篇：2篇`arxiv_not_found`；取源曾因arXiv对Python urllib返回406失败（改用requests，临时失败改为可重试`platform_fetch_failed`）；订阅session limit约每5–8次重调用触发一次，已加“构造完成仅审阅被429打断时只重跑审阅”的复用路径，并修复“限额后仍继续下一阶段”的bug。Physiome-ODE完整出包（4题）。Matcha在v1第二轮裁定被整篇drop（论文推论3.2在所用设定下给出约52%上限而表1报告61–93%，EXP研究对象与论文自身理论矛盾），但LIT/IDEA/两类WRITE被审阅判为健全；Disentanglement构造完成但缺五类覆盖表被结构门判死。**用户批准v2两处改动：**①审阅意见裁定可`pass_partial`剔除部分题、其余通过；②结构门失败时由controller把门错误作为唯一一轮返修意见（不调模型）。实现：prompt目录可配置，v2 prompt在`prompts/factory_v2/`（v1的`prompts/factory/`保持原字节，运行中的v1继续有效），新根`D:/mrhbench-local-pilot/factory-v2`（复制pool/triage/选单/批准；Matcha只重做第二轮裁定、Disentanglement复用原构造回执进入返修，旧记录留在各state的history）。42项factory测试通过。其余5篇仍在v1规则下完成，之后剩余130篇用v2。
- **按题设资源与factory-v3（2026-09-26，用户批准）：** ①同一包内每题可声明不超过整包环境的资源限额，编译按题使用（`material_adapter.task_container`，v1/v2/v3配置`per_task_resources=true`），Matcha（v2，剔除EXP后4题）、Disentanglement（v2，剔除EXP/IDEA/WE后2题）、扑翼机器人（v1，4题）因此零调用重新编译成功；前10篇当时已出14题但EXP为0。②v3：歧义裁定可在`repo_file_requests`列出仓库文件（数据/小checkpoint），controller新阶段`repo_files`在锁定commit用git blob取回（每篇≤200MB，LFS指针只报告不取），预置到构造者`output/assets/repo_data/`（构造者无法复制二进制）；git克隆超时600→1800秒；prompt在`prompts/factory_v3/`，新根`D:/mrhbench-local-pilot/factory-v3`（选单/批准沿用），剩余130篇在v3跑。扑翼机器人论文（v1因缺`.pt`数据推迟EXP）搬到v3从歧义裁定重跑作为验证。382项离线测试通过。
- **构造成本与EXP复盘（2026-09-26）→ factory-v4（用户批准a/b/c/e/g/h，否决d换官方API作为本次方案、否决f用合成替代研究对象）：** 前10篇名单批准后59次调用（源审计8/裁定19/构造19/审阅13），构造者中位98轮、800万输入/10万输出/18分钟，19次构造有9次被session limit截断（浪费约4530万输入/37万输出）；返修率100%且整包重写；LIT/IDEA每篇11–30篇背景（5–18MB）。EXP为0的原因：数据不可得3篇（Physiome数据集、扑翼`.pt`未取、D10y CLIP特征）、第二轮过严2篇（Matcha真实理论矛盾、Disentanglement小泄漏不能再修），v3验证又发现第4类：仓库无许可证→按G3放弃。**用户决定：未注明许可的仓库/外部数据可作内部学术benchmark输入**（逐文件记录许可状态，公开发布前再核；仅明确禁止研究使用或需签DUA者不用）。v4内容：a按题拆分构造单元（每题独立构造/审阅/裁定/返修/镜像、只带所需材料）；b只返修有问题的单元；c截断后从已写部分续写；e歧义裁定可列白名单数据站外部数据（与仓库文件共用200MB/篇，压缩包安全解压）；g EXP单元允许第二次针对性返修；h scout加“数据能否离线获取”（仅影响以后选题）；另加按论文/单元/阶段的token消耗审计以验证是否降本。
  - **v4实现（0模型调用，397项离线测试通过）：** prompt在`prompts/factory_v4/`（policy-4：G3放宽、新增I节构造单元、EXP两轮返修；裁定schema加`task_scopes`与`external_data_requests`、仓库/外部数据逐项`licence_terms`；scout/triage加`data_availability`）。`factory.py`：配置`unit_split`时论文级阶段为fetch→source_audit→adjudication→background→repo_files→external_data→units，每个请求题型在`papers/<pid>/units/<TYPE>/`独立跑construct…compile（job_id `<pid>__<TYPE>`、独立镜像slug、独立state）；按题型过滤来源（LIT/IDEA=论文+背景，EXP/WE=论文+代码+数据，WC=论文+代码）；`continue_truncated`：构造被429截断且已写出非预置文件时，重试以其部分产出为previous_candidate续写（记`continuations`，不算返修轮）；`exp_second_repair`：EXP单元有repair2/repair2_adjudication；`--units`只跑指定单元。外部数据`factory_sources.fetch_external_data`（子任务实现）：仅https白名单站点及其CDN跳转、逐跳校验、与仓库文件共用200MB、zip/tar安全解压（拒绝绝对路径/..、链接、超量），不执行内容。token审计`mrhbench/factory_costs.py`+`scripts/active/factory_cost_audit.py`：按每次调用request.json的workspace归属论文/单元/阶段（含失败与被搁置的尝试），主测量为总输入token与输出token，另计浪费（失败或被丢弃且未被续用的调用）。**v1–v3基线**（`D:/mrhbench-local-pilot/cost-audit/baseline-v1-v3/`）：7篇、59次构造期调用、输入2.64亿/输出279万token、18道编译题→每题约1470万输入/15.5万输出，浪费占输入27%，构造者中位790万输入/9.8万输出/96轮。
  - **v4验证运行（已中断，见下条）：** 根`D:/mrhbench-local-pilot/factory-v4`（沿用140篇批准名单，selection hash一致）；扑翼论文沿用v3的fetch+源审计、只跑EXP单元（数据现可用）；GETS与树RL论文沿用v1的fetch后完整跑。预计约45–55次调用，完成后用审计脚本与基线对比。
  - **v4验证中断状态（2026-09-26，账本587/1668，无reserved）：** 扑翼论文v4裁定（call583）请求五类并取回两份`.pt`（forces 16.5MB、kinematics 12.4MB，fetched）；EXP单元construct（584）+reviewer（585）完成，review_adjudication（586）判repair（三条：删H1效应量泄漏句；隐藏SRL检查改为接口无关；**.pt须由受信controller转换为.npz作为solver输入**）；repair构造者（587）第10轮撞429，状态`platform_rate_limited`，其output只有预置文件→重试将是全新repair而非续写（符合c规则）。GETS、树RL两篇只有沿用的fetch，未开始。其他四个单元（WE/WC/LIT/IDEA）未跑（只跑了`--units EXP`）。
  - **初步成本（仅5次调用，不足以下结论）：** v4 EXP构造者单次2.84M输入/5.7万输出/42轮/11分钟，对比v1–v3构造者中位7.92M/9.8万/96轮（输入约-64%）；但reviewer仍4.98M输入、裁定3.06M，按题拆分后调用次数增多，**每道编译题的总token对比尚无数据**（v4尚无编译题）。审计`D:/mrhbench-local-pilot/cost-audit/v4-partial-20260926/`。
- **交接给Codex（2026-09-26，用户要求收尾）：**
  - **继续v4验证：** 在`research/benchmark`下，`PY=D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe`，阶段`S=fetch,source_audit,adjudication,background,repo_files,external_data,units,construct,review_adjudication,repair,repair_adjudication,repair2,repair2_adjudication,runtime,compile`：①`$PY -X utf8 scripts/active/run_material_factory.py --root D:/mrhbench-local-pilot/factory-v4 run --workers 1 --stages $S --retry-platform --max-calls 12 --papers iclr2025-254NJe9JEw --units EXP`；②成功后`... --max-calls 50 --papers iclr2025-qgsXsqahMq,iclr2025-qpXctF2aLZ`（不加`--units`即全部单元）。撞429会自动停机，限额恢复后加`--retry-platform`重跑同一命令。模型调用仍经Claude CLI订阅（`config/role_transport_claude_v2.json`的ClaudeNativeRunner），无论谁操作控制器。跑完用`scripts/active/factory_cost_audit.py --root v1=… --root v2=… --root v3=… --root v4=… --out <新目录>`与基线对比（看“Combined per paper”的每编译题输入/输出与浪费占比），向用户报告。
  - **已知缺口：** ①EXP单元中`.pt`等二进制数据构造者（无shell）无法加载/转换，review裁定要求controller受信转换→需新增确定性controller步骤（例如repo_files后按裁定把`.pt`转`.npz`并记录hash/dtype；不执行作者代码、不用pickle不安全加载，torch `weights_only=True`），否则EXP修复可能再卡住；②reviewer与源审计单次仍约3–5M输入，是下一个降本点；③OpenReview优先取全文（用户2026-09-25决定）未实现；④`run_claude_integration.py`的`judge_version_expected`常量仍写v3.1。
  - **仍待用户：** 配额违规计分规则、T14正式配置、OS级隔离环境、P11试跑的executor走wrapper还是官方API。
  - **协作约定：** 提交由用户所在的git管理会话负责（AGENTS.md提交需用户同意）；给用户的页面写本地HTML（用户在两个账号间切换）；启动任何模型运行前先说清要跑什么、多少次调用；每次模型调用的token与轨迹须完整留存（常设规则）。
- **镜像不得跨包共用（用户确认）：** Gaussian不再复用IV镜像，已建独立镜像`mrhbench-pilot/gaussian-exp-v2:2a0e5db72726`（ID `2947d2db…`，仅numpy==2.3.3，定义在包内`environment/`），声明资源下starter验证通过，`audit/gaussian_exp_image_v1.json`；0模型调用。

### 0.2.17 Codex重新接手：controller数据转换与v4恢复（2026-09-26）

- **接手核对（非重新验收历史科学结果）：** 已阅读协议、Claude时期主要变更、factory v1–v4状态与wrapper运行汇总。当前候选池3705（1369有直接仓库链接），scout已筛400、325符合初筛规则、用户批准140篇；最终70篇仅暂定目标。去掉失败目录备份并按论文/任务ID去重，实际启动10篇，130篇尚未启动。5篇已有18道编译开发题：LIT5/IDEA4/EXP0/WRITE_CONTENT5/WRITE_EVIDENCE4；其他为2篇全文未取到、3篇模型阶段因限额中断。v4仍无编译题，不能声称EXP或新pipeline验收完成。结构快照`audit/factory_progress_snapshot_20260926_v1.json`（记录时间点，运行可能随后推进）。
- **零模型实现及真实转换：** 新增`mrhbench/tensor_conversion.py`、`factory_data.py`、`scripts/active/convert_factory_data.py`。显式转换计划绑定原始来源及原模型裁定hash，使用独立受信controller镜像（不是solver镜像），Torch2.6.0+cpu/numpy1.26.4，严格weights_only CPU加载、拒自定义/嵌套/不支持dtype或旧Torch，无不安全回退。每文件全新无网络/非root/只读根/1CPU/1GiB/64PID/120秒容器，只挂单一输入、受信脚本及独立输出目录；不执行作者或constructor代码。原始文件不修改。
- **扑翼实际数据结果：** forces/kinematics各153个float64数组，事件顺序与对应长度保留，无非有限值；306数组从npz按allow_pickle=False重新读取，dtype/shape/内容hash全部匹配转换回执。分别14,072,242B及10,563,826B。新job仅预置npz与neutral metadata，原.pt不预置；历史candidate保持原样，由constructor按原裁定返修loader与公开契约。`data_conversion/publication.json`与原裁定/计划/来源/输出绑定；后续job发现变化或不完整即拒绝。新能力不自动猜测所有二进制转换需求；其他论文仍需显式受信计划。证据`audit/controller_tensor_conversion_acceptance_v1.json`，真实工作目录在`D:/mrhbench-local-pilot/factory-v4/papers/iclr2025-254NJe9JEw/data_conversion`。
- **独立复核与测试：** 协作者新增转换与接线测试，指出重复目标/改名绕过/执行中plan变更三处缺口，root修复后15项factory_data测试通过；23项factory测试通过；全量427项（415通过、12因controller venv缺numpy跳过），跳过相关转换测试另在bundled NumPy环境完整14项通过。日志`D:/mrhbench-local-pilot/tests-codex-handoff-20260926-002.log`、`tests-converter-20260926-001.log`。旧397项日志与提交说明398项不能混作同一次测试。
- **本次明确告知后启动的模型范围：** 仅扑翼EXP的repair/reviewer/adjudication、必要时第二轮repair及runtime/compile；最多6次新Claude调用、单worker、不P11、不其他论文、不正式评测。2026-09-26 15:03 CDT快照：call588 constructor运行中（reserved，不能当成功）；旧call587失败保存为repair.failed-1，新日志`D:/mrhbench-local-pilot/factory-v4/resume-codex-20260926-001.log`。账本588/1668包含该在途预留；最终以ledger/state为准。遇429立即停，不自动重试。
- **未改决定与待办：** 模型仍Claude opus-5-5/medium，不因Codex回来而自动换回；wrapper仅初步实验、正式executor待官方API；1100次授权是材料构造，P11另需授权。OpenReview优先取源、R2并库、v4总成本/质量验收及T14仍未完成。未提交Git；提交仍由用户git管理会话负责。历史源/失败/分数不覆盖。

- **上述有界恢复已结束，用户随后要求优先降本（2026-09-26）：** call588–593六次均结束，账本593/1668、reserved0；扑翼EXP经过两次返修，最后独立reviewer pass_with_pending_runtime、裁定pass、Docker smoke/runtime passed、编译1题。合计现19道开发编译题（LIT5/IDEA4/EXP1/WC5/WE4），仍未P11/正式验收。此前0.2.17中的588在途及18题为当时快照，保留不覆盖。
- **降本诊断（零新增模型）：** `audit/factory_cost_bottleneck_20260926_v1.json`核call583–593：11次、累计输入23,768,416/输出342,875 token、模型会话时长总和约60.5分钟（不含继承源审计/早期版本，也不是含暂停的端到端时长）。末轮裁定仅要求身份文字/定位修复；call591仍Write整套12文件，最终10文件字节与上轮相同，591–593合计约15分钟。主要可证开销是整包重写和重复全审，不应把所有成本归为必要科学质量。新论文/新模型调用暂不启动；优先讨论增量返修、基于hash/diff的修复核验、确定性门前移与controller模板，保留独立科学审阅；尚未启用新prompt/新流水线或改定模型。总输入含缓存重复上下文，不等于独立文本量或订阅配额线性换算。

### 0.2.18 材料构造降本goal与真实模型验证计划（2026-09-26）

- **用户要求：** 先规划并设置goal；零调用回放后必须实际调模型，测量是否真的降低耗时和成本，不能把工程测试作为降本结论。当前重心由扩大材料量转为有界降本验证；本节取代上节暂不启动模型的临时安排，仅放行下述验证，不放行批量扩产/P11/正式评测。
- **目标与完成条件：** 实现可审计的增量返修、差异导航/风险驱动独立复核和确定性检查前移；通过真实新旧流程对照以及未参与调试的构造单元试产，给出成本/耗时/质量的证据与采用、修改或否决结论。收益未出现也如实报告，不以追调样例制造通过。仅代码/单测/回放成功不算goal完成；小样本成功不等于70篇规模效果或正式材料准入。
- **边界：** 保持claude-opus-5-5/medium及原生constructor/reviewer/adjudicator；不同时换模型或取消独立科学审阅。新配置/prompt另存新版本并在新运行根冻结，不修改v1–v4冻结prompt或历史材料/失败/成绩。controller复制与应用增量不替模型改科学内容。每次真实调用保留完整轨迹/token缓存分拆/墙钟/失败；维护者复核另记工作量，不冒充全系统零成本。
- **阶段A：基线与工程（0开发模型调用）。** 冻结历史成本证据；选两类真实开发返修案例：一类局部文字/定位问题，一类涉及科学语义或代码的较复杂修改（尽可能来自不同论文）。冻结原候选、原始来源、裁定意见、检查点与输入hash；预先选择第三个未参与调prompt的真实构造单元。实现在新output复制原候选后只改必要文件、before/after hash与完整diff、结构/路径/资源/身份检查。科学变更扩展复核范围，无法可靠判影响时退回完整审核，回退成本照记。独立reviewer可查完整来源和产物，不仅看constructor自述。机械模拟历史diff只验机制，不计模型能力/质量/降本成功。
- **阶段B：两案例真实配对对照（最多12次）。** 每案例原流程与新流程各一次，分别constructor→独立reviewer→adjudicator，共2×2×3次；第一对完成并审核后才放行第二对。两臂使用相同起始材料、修订要求、模型/effort及运行限额，全新会话和工作区；不传另一臂产物或分数。提前固定执行次序并记录时间/cache/provider状态，承认单次配对无法估计总体方差。历史数据只作辅助基线，不代替此次旧流程对照。工作流差异作为整体改造评估，不声称单个组件的因果贡献。某臂未修好保留失败，不凭便宜判胜、不临场加修直至过关。发现重大漏检或明显回归即止损，不机械用满12次。
- **阶段C：未参与调试单元试产（最多8次，B有可接受结果才放行）。** 按预选范围跑新流程到运行门/编译；如需源审计与范围裁定最多2次，初构/审阅/裁定3次，最多一轮返修/审阅/裁定3次。第二轮EXP返修不在本次成本上限内；到限未完成如实记不足，不加额度、不拿无输出样例替换成更容易的。不是P11，不调用benchmark executor/judge，不宣称正式验收。C若暴露需改prompt/机制，则该案例转为开发证据，不能改后仍称留出验证。
- **总调用预算与停止规则：** 当前ledger593/1668，本goal开发transport新增最多20次（B12+C8，失败/429计入），全局1668不变；本阶段不得因此超过ledger613。这是工作上限，不要求用尽。每次启动先告知具体范围及当批上限；不另做收费/耗配额探针。首个429立即停，不忙重试，不因goal自动续调；待恢复后才显式续跑。根会话/协作agent消耗不在该transport账本内，不声称20次覆盖全部订阅用量。
- **观测与采用标准（工程目标，不改benchmark主分）：** 同时报告总输入token（含缓存重复）、未缓存/缓存写/缓存读、输出token、模型会话秒数、端到端活跃/等待墙钟、工具轮次、重写字节、返修/回退次数；费用仅有冻结可信价格快照时另作估算，订阅不虚构逐次美元。每案例及两例汇总都报告，不能只挑constructor或获胜例。预算阶段目标为配对流程总输出token和模型会话耗时相对旧流程均减少至少30%，总输入不增加；这是待测目标不是承诺。质量门为既有真实缺陷修复、无新增重大科学/泄漏/契约错误、变更影响得到独立复核且运行门适用时通过。开放科学质量不声称以两例证明非劣；审计不确定性照报。未达目标或质量退化则不扩量，先报告收益/缺口与是否值得继续；不静默追加实验。
- **交付与顺序：** 所有进度写本文，数据/对照方案及结果写结构化audit，代码与测试保留；不另建PLAN/STATUS。先A→首对B→审核→第二对B→审核→C→质量成本综合结论。只有达到上述证据型完成条件才关闭goal；当前仅已规划，真实新旧对照尚未开始。

- **阶段A实际进度（零开发模型调用）：** 新增`mrhbench/incremental_repair.py`和显式`run_batch(... incremental_repair=True)`接线，默认旧行为不变；controller按原字节seed新output、保留预填数据并记录冲突，完整hash/diff与紧凑JSON Pointer导航分开保存；独立reviewer可读完整来源/当前与旧候选/旧审阅、原裁定，缺旧审阅或影响不明时要求完整复核，不据unchanged自动通过。新增prompt在`prompts/material_efficiency_v1/`，旧冻结prompt未改。新模式和prompt hash进入receipt，恢复不允许静默换模式；review_context也受输入完整性门保护。仍待真实试跑，当前不宣称降本或科学非劣。
- **预冻结案例（在付费对照前选定）：** `audit/factory_efficiency_cases_v1.json`绑定两例共83个输入文件hash：扑翼文字/来源定位返修（old→incremental）；Diffusion科学/代码契约返修（incremental→old）。C预选GETS，在范围裁定后按冻结EXP/WE/WC/LIT/IDEA次序选首个支持单元，不根据成绩换论文。工作根`D:/mrhbench-local-pilot/factory-efficiency-20260926-001`，代码/prompt最终执行hash和真实对照driver尚待冻结，不能直接启动无记录调用。
- **回放结果：** 两真实历史返修候选均可由seed+实际变化重建最终产物（排除旧controller生成package.constructor_original副本），结构检查通过；`audit/factory_efficiency_replay_v1.json`明确model_calls=0、未测试模型质量/成本。历史最终内容只用于机械回放，不得传入真实对照构造会话。19项incremental单测/接线测试及23项材料回归通过；全量446项无失败（434通过、12因controller venv缺NumPy跳过，转换模块此前bundled NumPy下14项通过且本轮未改），日志`D:/mrhbench-local-pilot/efficiency-full-tests-20260926-001.log`。账本仍593/1668，goal保持active。

- **预算防线增补（仍零开发模型调用）：** 新增`BoundedCallLedger`，在共享账本同一锁事务内校验实验绝对上限、单臂次数、audit目录边界、未结束调用及首次provider_rate_limit；失败计数且控制器重启不重置。7项针对性测试通过，含并发争抢只能启动一次、429后其他臂拒启及旧CallLedger行为保持。该限制只作用于采用新类的运行器，不声称控制其他独立进程；真实对照driver接线/执行hash冻结仍待完成，全量453项回归无失败（441通过、12 NumPy跳过），日志`D:/mrhbench-local-pilot/efficiency-budget-tests-20260926-001.log`。账本593/1668未变。

- **首次真实对照已启动（旧臂，2026-09-27 UTC / 本地09-26）：** 运行器`factory_efficiency.py`完成并经7项fake调用/冻结/裁定/顺序测试；另3项成本解析测试通过，历史591–593复算为输入4,397,758、输出91,460、900.36秒，只是计量校准。执行冻结`D:/mrhbench-local-pilot/factory-efficiency-20260926-001/execution/manifest.json`绑定103个代码/prompt/config及binary和实际输入目录成员；旧v4 prompt hash再次匹配。两臂使用相同v4 base+addendum，Diffusion对照是新受控比较而非复现其历史旧prompt。已告知首组最多6次，先启动wing old臂（单臂最多3，B账本止于605）；调用594 constructor已reserved，宿主执行session69462，日志`wing-old.log`，尚未获得质量或降本结果。完整单臂计时从publication开始，不含先前预检/hash；人工/等待另记。首次定向测试曾因测试入口缺sys.path失败（无模型调用），仅修test后独立7项通过，不改已冻结引擎。不得因观察超时重启该运行。

- **首对B进度：** wing旧臂594–596三次实际结束，裁定pass，输出87,443 tokens，总输入5,391,490（含cache）、模型会话902.921秒、从publication起完整臂908.75秒；这是本次受控旧臂，不代用历史基线。新增minor cutoff/gate/split来源定位缺口被记录为非阻塞，尚待维护者独立核查。原始变更机械核查为3文件变化/14未变，科学代码/环境未变；公开文字身份扫描零命中，不当全面科学验收。已再次告知后启动incremental臂（最多3次，session25341，wing-incremental.log）；勿重复启动。独立维护审核正在审旧臂完整证据，尚未通过首对放行门。运行器加入后的全量463项无失败（451通过、12 NumPy跳过），日志`D:/mrhbench-local-pilot/efficiency-driver-full-tests-20260926-001.log`。

- **首对B已审核并放行第二对：** 增量597–599三次结束且原生裁定pass；总输入1,435,858（较旧臂-73.37%）、输出24,636（-71.83%）、模型会话334.797秒（-62.92%）、完整臂342.141秒。两臂另实跑全新CPU smoke均passed，同image ID e9c8eb2e…、torch2.4.1+cpu，153事件/438552样本检查ok、容器已清理；加runtime墙钟旧918.375/新350.047秒。维护独立审阅两臂的修复/完整动作路径与相关原文后均通过有界质量门，未声称逐字语义阅读所有原始工具回包；增量没有重新发现旧fresh review发现的既有minor cutoff/gate/rounding定位缺口，保留为覆盖差异，不称总体质量非劣。独立维护审核墙钟217.833+208.633秒，维护token/根探索时间未独立计量，不记0、不混作开发transport成本。权威门`audit/factory_efficiency_wing_pair_v1.json`及D盘`audits/wing_text_repair.json`绑定results/审阅/runtime哈希。已告知第二对最多6次，按预定incremental→old启动Diffusion增量臂（session84222，diffusion-incremental.log）；当前不扩量、不启动C、未关闭goal。

- **第二对B真实接口失败与显式调度修订：** Diffusion增量600–602三个transport会话结束（总输入2,634,498、输出48,446、模型535.329秒），但602裁定project_id错误拼接paper_id/job_id；controller记`failed_needs_attribution`，不改原文件、不计完整成功、不重试。裁定文本pass与运行门成功必须分开。为仍执行已计划旧臂，新独立脚本`continue_efficiency_terminal_pair.py`仅对这一次已结束的已知identity失败放行调度，原103文件执行冻结/prompt/候选不变；3负测/保真测试通过，脚本及失败result哈希保存在D盘`execution_amendments/terminal_pair_v1.py`和`audits/diffusion_terminal_continuation_v1.json`。已告知用户并启动原计划old臂（最多3，session80288，diffusion-old.log），不是新增/重试增量。独立科学审核进行中：原有EXP fact已公开sigma_m=.1信息，F4新增非可比性警告确在私有侧；不能夸称所有协议数值已私有化，但原要求并未明确删除该既有fact，暂未定为新增重大泄漏。C新独立控制器已离线实现且6项测试含2+6 fake会话/单次修复/runtime-compile，但尚未freeze/调用，等待第二对完整成本与科学/接口失败归因裁定。

- **本goal终局（2026-09-27 UTC / 本地09-26）：** 两组真实配对594–605已结束，共12/20次；账本605/1668，全部transport completed、无重试/429，剩余条件额度8次未用。Diffusion旧臂也因project_id拼接错误而pipeline失败，原始裁定drop；增量原始pass但同样pipeline失败，均保留，不回填修正。两臂CPU runtime另行通过并清理，不替代科学/泄漏验收。全量474测试462过/12 NumPy跳过、0失败。
- **成本实测但不能宣布质量保持：** 两例合计旧/新总输入8,390,208/4,070,356（-51.49%），输出180,695/73,082（-59.56%），模型会话1,804.905/870.126秒（-51.79%）。两例各自数值目标也达到，但Diffusion不属于等价成功流程。维护独立审核合计863.910秒（含纠错复核），根工程/复核时间及maintenance tokens未完整计量；订阅美元未知，不把上述下降称为整个系统净成本下降。
- **重大漏检触发止损，C不启动：** 公开题面/方法说明/必交文件名保留源论文特有“Diffusion Evolution”方法名，违反两裁定器实际读到的同一v4 E1规则；旧605识别并drop，增量602漏检并pass，两reviewer亦漏检。既有缺陷不豁免当前门，另保留作者80×80网格及sigma信息公开的审计风险。一对不能证明增量机制导致漏检，但已足以否决当前组合方案推广。早期独立审核只覆盖F1–F7而漏掉这项全包规则，旧报告原样保留；新增diffusion_pair_quality_v1.json明确纠正，不冒称旧审核已完整。此前与当前reviewer base prompt逐字相同，不能断言已证实协议版本错配。
- **结论与完成边界：** 权威audit/factory_efficiency_final_v1.json和D盘audits/diffusion_science_code_repair.json明确modify_before_adopt / allow_prospective=false，C门只读拒启已验证。保持生产incremental默认关闭，不扩大材料、不跑P11、不追加调用；方向是保留原字节增量编辑，但每轮强制完整当前政策关键检查、跨角色覆盖与精确identity契约，再用新案例验证，尚未获真实模型质量背书。C控制器仅离线8项测试，未freeze/执行。按预声明重大漏检停止规则完成此次有界验证并交付否定/修改结论，**不是优化验收通过或全benchmark完成**。103执行文件、83初始输入及关联冻结重新核对通过；历史输出/失败/裁定未改。

### 0.2.19 质量修复与降本验证第二轮（2026-09-26用户续授权）

- 用户要求继续修复pipeline并保持接近上一轮降幅；新goal active。上一轮结论与失败原样保留，不能改称通过。目标为可靠的有界材料构造/返修流程，不承诺数学意义的“完美”或用无限重试制造成功。
- 先零开发模型调用修复三项：所有角色绑定同一完整当前政策；每轮都审全部公开面的身份/作者实验规模/目标实现泄漏及核心科学与IO契约，不因文件未改或旧review通过而豁免；裁定精确project_id/round输出约束，非法结果拒绝而非事后normalize。完整diff仅为导航，保留独立科学reviewer。旧Diffusion仅回归，不再当留出。
- 预算预设：当前605/1668，本轮最多20次新开发transport调用、绝对止于625；不与上一goal剩余8次叠加，不改全局1668。两组新冻结返修配对最多12次，质量/成本通过后预选未调试单元最多8次；每组启动前报告，首次429即停止、不自动重试。若重大漏检或质量门失败则停止后续调用，先改工程并记清版本，不追调同例凑达标。进一步真实迭代另设明确批次上限，不能把“直到完善”解释为无限耗额度。
- 降幅目标：全流程新/旧总输入与模型会话耗时各减少至少45%、输出至少50%，接近上轮51.5%/51.8%/59.6%；同时逐例报告，不藏负例或只计constructor。两臂同源/同任务/同资源/同模型effort，并都落实必要质量规则；差异为整包重写与增量编辑导航，不以旧流程弱检查博取优势。模型tokens不是订阅美元；维护审核及工程成本另列，未知不记0。
- 准入条件：明确修复全部既有必要问题、无阻塞科学/泄漏/契约缺陷、独立审核与适用CPU runtime/编译通过；控制器只核覆盖凭证与证据身份，不把填写清单当科学正确证明。新例在任何真实生成前冻结选择、输入、顺序、prompt/代码及检查范围；不根据结果换简单例。未达目标/新缺陷如实报告并保持goal active，不启动正式benchmark/P11或批量扩产。
- 当前开始实现，尚无本轮新模型调用；默认生产增量仍关闭。根维护AGENTS/集成，独立协作者仅新增质量合同模块与离线测试，旧103文件执行冻结不覆盖。

- **本轮零调用修复进度：** 新增material_public_surface.py（公共事实只投影fact_id/statement/kind，不把私有source locator错当公开）、material_quality_contract.py和opt-in material_quality_runner.py；构造/独立review/裁定同政策字节，review/裁定sidecar绑定当前包与全公共面；identity/author_scale/target implementation每项全表检查，缺失/unknown/issue不得pass；精确paper_id/project_id/round本地schema拒绝，不改模型结果。新policy/prompts位于prompts/material_efficiency_v2，按已定WRITE协议明确合法作者结果输入例外，旧v4不改。构造器自身不写科学验收凭证。27新增定向测试通过，全量501项489过/12 NumPy跳过、0失败（efficiency-v2-engineering-tests-20260926-001.log）；尚未接入新的真实对照driver，覆盖凭证不是语义证明。
- **新例候选而非已冻结：** audit/factory_efficiency_v2_case_candidates.json预选D10yarGQNk的IDEA文字/来源返修、6ouZaBzeNO的WRITE_CONTENT可见性与per-task smoke返修；源自未读后续修好结果的v1多任务原候选，必须显式单任务投影后同样供两臂，不冒称现成v4单元。第二例不覆盖EXP数值算法，C及最终准入仍需考虑该覆盖缺口。原Diffusion两臂仅作公共面库存离线回归，旧103文件冻结重新核对通过；本轮ledger仍605/1668、0新调用，goal active。独立代码审阅与新单任务投影准备进行中，下一步先完成接线/预算/输入冻结，再告知启动真实配对；不得跳过质量门。

- **独立复核纠错（仍0调用）：** 新覆盖validator曾让review附加action=drop覆盖真实decision=pass_with_pending_runtime，从而放过unknown；独立fake复现后已修为角色唯一决定字段（paper_id→decision，project_id→action），caller不能弱化，新增负测；quality系列25项通过，public_surface另6项。此前501测试快照不能替代这项安全语义修复。正在把三类全公共面检查的重复长ID列表压缩为绑定contract hash的明确全表scope，保留具体证据引用与检查要求；仅减少冗余JSON，未测真实token收益，完成后须重跑测试。尚未执行真实v2模型调用，不能声称完善pipeline已达成。

- **续轮工程与选例实证（0新调用）：** 压缩后的coverage用绑定contract的全表scope常量，三项关键审查范围不减；32项质量/公共面测试通过。单任务投影脚本原先绝对source路径与validate_job不兼容，已修为新workspace内原字节副本+相对路径，8项测试实际走prepare_material_job。两真实单元已在D:/mrhbench-local-pilot/factory-efficiency-v2-20260926-001/inputs投影，52/24来源、validate_job/package与真实publication预检通过；smoke未手改，明确两臂都承担投影诱发的跨任务资产适配。audit/factory_efficiency_v2_cases_v1.json预冻结71/45输入身份，C仍预选GETS，不按成绩换题。
- **新driver离线通过但尚未调用：** factory_efficiency_v2.py/CLI新增12测试，包括真实run_batch+三QualityBoundRunner+adjudicate的old/incremental各3次fake-native整臂、缺sidecar/篡改policy拒绝与null notes；同政策两臂、B上限617、总上限625。新snapshot会明示v2 prompts到兼容目录的overlay，不改原v4/v1。全量回归和独立driver复核正在进行，真正execution freeze与首臂调用须在其后；上轮属于实质进展，不是等待或已完成科学验证。

- **v2首臂已实际启动：** 全量525项无失败（513通过/12 NumPy跳过，efficiency-v2-pretrial-tests-20260926-001.log），最新driver12及budget7独立复核通过；新增incremental整链测试在全量扫描后完成，另有针对性通过证据。execution/manifest.json已冻结132代码/prompt/config及3个明示overlay、binary39be063c…、两例输入/投影/原来源身份，verify_execution通过。已告知首组最多6次，启动idea_background_repair旧臂（session72558，idea-old.log，单臂最多3，B总止617），不得因观察超时重启。尚无质量或降本结果；源/代码执行冻结之后不再修改其绑定文件，新修改须另版本且保留本运行。

- **v2首臂终局与止损：** 606 constructor480.219秒、607 reviewer408.109秒、608 adjudicator145.578秒均原生completed；合计总输入8,576,213、输出94,360、模型1033.906秒，完整臂1040.922秒，账本608/1668。reviewer抓到公开fact MS-NEUTRAL明示目标方法家族、日期/输入合同矛盾；adjud原始drop有据，材料未通过。维护初审漏掉fact语义，另存idea_old_review_correction.json透明纠正，原初审不改；终局独立737事件/161动作与回执匹配、无观察跨角色/跨臂行为，审计116.646秒，补审65.345秒，初审起时缺失记null不记0。CPU runtime另在新容器passed/清理（5.094秒，与review并行，不可直接相加称端到端），不清除语义泄漏。
- **真实平台缺陷：** 新政策J2/J3被旧adjud schema的A-I正则拒绝，故pipeline为failed_needs_attribution；既非模型未完成调用也不把合法规则引用算科学错误。原失败与raw drop保留，未跑incremental、未重试。audit/factory_efficiency_v2_schema_failure_v1.json及D盘审计绑定归因。新增material_policy_schema.py从完整policy生成精确有效citation枚举，含实际规则、无编号的政策节，6项测试通过；原608只在新schema做零调用诊断，不回填成功。v2的132冻结文件重新核对未变。
- **v3准备（仍未追加调用）：** 新prompts/material_efficiency_v3另存，F4明确资源review检查proposal/预算一致性，坦诚runtime pending本身不当科学unknown；真实runtime门仍独立必需。首例IDEA已经用于调试，不再冒称新留出。保留未运行的WRITE_CONTENT单元，另找真实EXP返修候选补科学代码覆盖；不读取未来已修好结果挑赢家。保持本goal20次/625上限：已用3，下一批拟608起两新配对最多12到620，条件新单元最多5到625（源2+初构/审阅/裁定3，无额外返修余量；需要返修则如实未完成而非超限）。新driver/schema/方案冻结与独立复核完成前不调用；audit/factory_efficiency_v3_preparation_v1.json为准备记录而非启动许可。goal active，质量与类似降幅尚未被新对照证明。

- **v3入口与回归续进（0新调用）：** 新adjudicator提示明确decision与quality_coverage双产物，policy显式H1/F4，独立复核确认动态规则schema及608→620/625限额；补真实overlay与缺裁定sidecar终止负测，driver16+schema6通过。全量547项535过/12 NumPy跳过、0失败（70.110秒；扫描早于新增负测，后者另测），见audit/factory_efficiency_v3_preflight_v1.json。新WC输入40文件逐字节复制，EXP投影84文件，job/package结构及实际prepare_material_job发布检查通过（来源64/24）；均未冻结/未跑模型/runtime。
- **EXP科学入口纠正而非手修材料：** 独立复核及root核原文S3.SS2/A4后，不能将作者N5000/D2000/S1–S8以scoped名义强制为solver配方；新job/notes明确保留弱信号均值、单位噪声、方法/公平比较和定性偏移问题，数值规模/网格/实验分配交solver，假设明确为参数族内限定检验、不冒称复现原八点命题。取消旧near-chance自动defer，低分/未复现作者分数不是材料失败；原笔记全保留并标明新入口优先。源码/科学资产仍原字节，由两臂模型实施同样修订；2400秒恢复指令显式优先于投影keep-resources说明。audit/factory_efficiency_v3_exp_autonomy_review.json与新projection绑定；独立入口冲突复核进行中。账本仍608/1668，本goal用3余17，goal active，尚未证实新版本质量与降幅。

- **v3真实冻结与启动：** 独立入口复核确认EXP/WC全部相对来源/库存匹配、科学资产原字节、旧notes完整后缀、新override优先且无task_scopes残留。cases_v1/authorization及execution已冻结139代码/prompt/config与5overlay（含动态schema绑定），verify_execution通过。开始exp_autonomy_repair/old单臂最多3次，exp-old.log；B止620，goal止625，无自动重试。运行尚未验收，不宣称质量或节省。

- **v3 call609真实429终止（新失败保留）：** 首臂仅constructor一调用，27.344秒，累计输入121,013（8普通+58,751 cache-write+62,254 cache-read）、输出2,479；provider明示session limit/00:40 America/Chicago，terminal api_error_status429且is_error=true，不能因subtype=success冒称成功。臂30.265秒后failed_needs_attribution，PTY18419已exit0（controller退出≠材料成功），没有review/adjud调用；账本609/1668、无reserved，本goal用4余16、止625。未产完整候选，质量未评、两臂未配对、无降幅结论。
- **首次429止损已实证：** 139冻结文件复核未变，直接对真实账本调用只读reservation预检，old/incremental下一调用均被provider-rate-limit门拒绝，账本字节未变。证据D:/mrhbench-local-pilot/factory-efficiency-v3-20260926-001/audits/call609_controller_stop.json；独立完整轨迹审计进行中。已询问额度恢复后是否另开有记录的续跑批次、仍守625总上限；本批不自动重试/换arm绕过，重启构造也须另计调用。上一goal turn属实际修复/冻结/启动的进展，本轮属已确认终局故障取证与止损进展，非第三次阻塞，不标goal完成或blocked。

- **609独立终局审计完成：** call609_independent_rate_limit.json（SHA07a17bfb…）全读46事件、19动作/回执（Glob1/Read18），18份完整读回与发布文件匹配、路径均在constructor范围；无Write/Edit、无output或partial候选，review/adjud未启动。冻结139及constructor输入hash复核通过；审计起始未计时故耗时null，不记0。限流为provider终局而非科学材料失败，未追加模型调用。

- **429阻塞复核第2个连续goal turn：** 权威账本仍609、reserved0、首臂终局未变，尚无用户有界续跑答复；上一turn完成故障取证属进展，本turn仅重核、不冒称新进展或活进程等待。所需真实配对/科学质量/成本与条件新单元验收均缺失，不能完成goal；不能用付费探针或换arm绕过首次429停止。记录continuation_blocker_check_2.json，goal保持active（未达3次阈值）。

- **429阻塞第3次复核：** 当前账本609/无reserved、首臂terminal429未变；上一turn只有状态重核无进展，当前无新有界续跑答复。离线修复/测试/完整失败审计已完成，缺少真实配对质量/runtime/成本及条件新单元证据，不能以离线结果代替。达到连续3次同一阻塞阈值，goal改blocked而非complete；待用户确认恢复后以新有记录批次继续，仍受625总上限约束，不自动重试。记录continuation_blocker_check_3.json。

- **2026-09-27用户告知限额应恢复：** 按继续有界工作的语境准备新批，不以时间推断provider已恢复。原139冻结与ledger609/无reserved重核通过；用户恢复消息及新边界绑定在audit/factory_efficiency_v3_resume_authorization_v1.json。独立新调度adapter开发中，旧engine/prompt/案例/失败不改；新root为factory-efficiency-v3-resume-20260927-001，baseline609、配对最多12止621、总仍止625，再429再停，不额外付费探针。原goal本批已用4，完整配对后只余4不足原C源2+初构审阅裁定3，届时不得超额或冒称完成；新的恢复阻塞计数从零开始。尚未追加真实调用，goal工具当前仍blocked（工具不支持主动置active），不把调度准备称实际恢复成功。

- **显式恢复新批已启动：** 新resume adapter未改139原冻结文件，7离线测试通过，含原engine/run_batch/三QualityBoundRunner/fake-native真实整链610–612（仅临时账本非真实调用）、缺授权/篡改/新429/预算/重复arm拒绝。独立只读预检通过；真实prepare新root后逐相对路径核139新旧snapshot完全一致，证据新root/audits/snapshot_copy_acceptance.json。启动exp_autonomy_repair/old正常调用，不另探针；使用新adapter一次一臂，上限621/625、旧609失败成本保留。实际provider恢复及材料结果须看该运行，不由reset时间或离线测试推定。

- **用户询问状态后的真实复核：** 恢复首臂610–612三个transport均completed（600.843/535.656/274.719秒），没有新429；总输入9,179,170、输出128,330、模型1411.218秒、完整臂1419.297秒。臂质量门failed_needs_attribution：裁定coverage.identity为issue（controller task_id含iclr2025/OpenReview身份），不能同时pass；原结果保留、尚未独立科学/runtime验收，不启动下一臂。账本612，本goal用7余13止625。PTY11982已terminal；应用goal仍blocked并非paused，先前实际手动续跑未恢复自动goal，工具没有active/resume入口，需用户在goal界面恢复；此前未说明这个状态区别是沟通遗漏。

- **Goal现已真实active；身份缺口复现（零新增调用）：** get_goal确认用户恢复成功。独立初审指出reviewer其实已读到task_id的OpenReview标识却按controller责任写identity.clear；adjud写issue仍pass，质量wrapper正确挡下，不能简单称reviewer未看见。root以实际612候选走compile_package→export_task零调用诊断，确认公开task.json.task_id保留源标识；顶层paper_id/private reference并未直接export，不扩大为已发生solver运行泄漏。diagnostics/identity-original-release使用明确虚拟image与诊断预算、未执行solver/runtime，证据audits/identity_export_reproduction.json，原候选未改。
- **修复方向：** 新opt-in material_public_identity模块开发中，controller持久化随机opaque ID私有映射，必须在canonical候选阶段统一使用，贯穿公共面review、编译outer/public ID、预算/collection及后续builder registry；不能只在最后export遮一个字段。映射不挂solver，同一任务各臂复用ID；原scientific资产不自动替换，公共facts/contracts/路径/bytes残留须拒绝/语义审阅，最终release包括controller新增字段还需审核。改包hash后旧review/runtime不得继承，旧610–612保留不修分；账本仍612、余13/止625，不启动新模型追调。

- **身份foundation实际诊断（0新模型）：** 新material_public_identity.py/9测试通过；持久随机128bit opaque map与私有回执、仅task_id新副本、严格预算/collection remap、candidate/实际release扫描已实现但未接生产driver。root对612原候选另存diagnostics/identity-projection-v1，7公共资产字节不变，经实际compile/export后task_id为opaque、已知源ID无匹配；原package未改，无runtime/solver，旧review/runtime不继承，证据audits/identity_projection_diagnostic_v1.json。独立审计identity_release_attribution.json确认平台ID缺陷及两角色的责任归属豁免错误，质量门正确挡下。
- **独立负测继续修复：** reviewer在新scanner发现有效JSON资产（不限后缀）Unicode转义能藏已知源ID，原raw UTF8检查漏过；不是语义匿名性保证的问题，而是已知JSON键值应解析检查的工程缺口。新模块正在修并补负测；9测试/实际612诊断仅先前证据，不冒称覆盖此编码。完整离线回归已启动（identity_foundation_full_tests_20260927.log），完成后与修复后定向测试分别记录。goal active，仍612/625，未开下一真实臂。

- **JSON扫描修复与回归：** 新模块现对UTF8有效JSON资产递归检查全部键/值，object_pairs_hook保留重复键全部值，避免覆盖隐藏标识；逐资产明确strict_json_keys_values_scanned，非法/非JSON不冒称解析。11定向测试通过，v2审计保留v1负例；root用新版重扫实际诊断candidate/export，另存identity_projection_scan_v2.json不覆盖旧receipt。全量564项552通过/12 NumPy跳过、0失败（124.652秒）；该扫描开始早于新增2个JSON测试，后者由11定向单独覆盖。仍0新模型、无科学验收转移，下一步独立复核后将ID分配接入构造前控制器及最终发布门，不能凭foundation关闭goal。

- **身份接线继续（0新模型）：** 新material_identity_release.py实际串联factory_runtime.compile_tasks→export_task→最终全view/资产扫描；强制全部opaque预算与收集key/显式wall，无默认预算回退，不压掉facts，不继承review，旧runtime package hash/digest拒绝；全部产物为私有待审staging，不自动solver准入。4新测试及独立额外6负测通过，audit/material_identity_release_offline_v1.json。新IdentityBoundRunner已写但root发现真实顺序问题：constructor原生允许CONTROLLER_FILL，batch在其返回后才填hash；过早scan会误拒真实输出。正在修为ctor只核ID/type、记pending；batch原顺序fill后review开始前严格扫描，known泄漏在第二次付费前拦下，并将fake整链改为真实sentinel。未改139冻结或旧run、未追加调用，ledger612/余13止625；代码接线与真实验证仍分开。

- **IdentityBoundRunner顺序修复完成：** 6定向测试root与独立复核通过；old/incremental实际run_batch+三QualityBoundRunner fake链使用合法CONTROLLER_FILL，package.constructor_original保留sentinel、原batch唯一填hash。ctor receipt明确pending，known public泄漏在review原生调用前拒绝；三角色assignment一致、map只controller读不复制，quality unknown仍不能pass，binary unknown未机械清除。v2审计保留v1假fixture预hash盲区。新runner+release组件尚待新driver显式冻结接线及真实模型/CPU/最终公开面验收；没有把新组件通过追认为610–612成功。ledger612不变，goal active。

- **真实身份runtime→发布整链诊断（0模型）：** root先读完Dockerfile/smoke与5个starter文件，再对另存匿名候选运行verify_runtime；fresh非root无网络容器smoke7.375秒通过、清理verified_absent，真实image sha256:2bd45e9f…，原declared2400秒/2CPU/4GiB/256PIDs/2GiB写配额，smoke900秒上限不等于任务时限或完整科研可行性。随后新compile_identity_release用该新package hash/digest/runtime真实record编译/export7公共资产，最终known-ID无匹配、全部语义门pending；模型/工具1及1MiB收集为明确诊断设置，未跑solver、不当正式配置。audits/identity_runtime_release_integration_v1.json；Epgo只作development_regression不冒称新留出。
- **用户条件预算更新：** 用户明确“允许条件追加4次，最高629”；baseline612配对最多12止624，只有两组新对照科学/runtime/最终发布质量和冻结降幅通过，才可新单元最多5止629；未通过不动用额外4，全球1668未改。audit/factory_efficiency_v4_conditional_authorization_v1.json记录，当前ledger仍612。v4driver正在独立新增接IdentityBoundRunner与release gate；private prior不强制手工匿名化（它是模型要修的输入），构造前assignment规定opaque输出。
- **新鲜选例限制透明保留：** audit/factory_efficiency_v4_case_selection.json先报告无现成带旧独立review的新EXP，3n4RY25UWP仅原结构失败/缺review的条件候选，WC仍未跑。工具本已支持missing_prior_review，缺review本身不强迫另花调用；正在独立读3n原科学任务/来源判断真实返修价值，不看返修后结果、不伪造review/缺陷、不把Epgo换名冒充新留出。尚未冻结v4或启动真实调用。

- **runtime发布整链独立复核通过：** identity_runtime_release_independent_recheck.json逐项核candidate rawhash/digest→runtime→compiled/release绑定，7公共资产三处hash一致、export恰8文件无private/map、所有gates pending/reviewer None，重扫controller notes吻合；stdout自报6.2秒、controller记录7.375秒口径分开。root另查同名daemon容器无残留。v4真实runner接线离线实现中，尚未execution freeze；新候选选择需保留missing priorreview事实，但工具原就支持缺失review，不以额外预审模型调用补造历史。核心真实性及两臂新的独立审核要求不减。

- **v4新输入与门禁已冻结（2026-09-27）：** 3n4RY25UWP EXP真实原候选缺review、coverage重复8行，单任务投影保留缺陷供模型修，不伪造旧review；72来源与8科学/环境文件字节未改，4投影测试和独立审计通过。6ouZaBzeNO WRITE_CONTENT未跑输入40文件与v3冻结副本一致；新两例均fresh_validation，Epgo旧修复仅development_regression。audit/factory_efficiency_v4_3n4_entry_addendum.json及projection_independent.json明示绝对/比例下降的科学表述矛盾、strict JSON等静态风险、投影诱发smoke工作，不冒称已观察数值算法失败。
- **v4工程验收与新调用：** 第二pair准入从任意独立review/空export漏洞修为本arm candidate/runtime/完整compiled public资产/actual export/独立全公开面报告逐项hash绑定；9独立gate测试通过，整体589测试577过/12依赖跳过，语义真值仍须人工独立阅读。D:/mrhbench-local-pilot/factory-efficiency-v4-20260927-001/execution/manifest.json冻结146文件，verify通过；原103/132/139历史snapshot全部hash未变。用户已被告知先EXP旧臂最多3次，call613 constructor已reserved，session96072及exp-old.log为在途证据，尚无质量/降幅结果，不重启未确认终止的进程。当前baseline612、paired硬止624，条件额外4至629仍须两组质量/降幅全部通过；本轮未启动正式评测。

- **v4旧臂613–615已真实结束并止损：** constructor590.281秒、reviewer344.344秒、adjudicator162.469秒，3次调用均transport completed；reviewer revise、adjudicator drop，非schema/调用失败。三角色合计输入6,223,522、输出98,329、模型1097.094秒；pipeline1113.391秒，维护者/独立审阅另计，不推订阅美元。公开F-S-H1末句直接引用作者“all accuracies decrease”观察，root核原paper S3.SS1.p3，独立科学审阅亦阻塞；本轮质量门正确抓到，而非放行。test-selection helper与task优先规则不一致另记需澄清，不把合法待验假设误判为结果泄漏。audits/exp_old_stop_and_cost.json与exp_old_independent_science.json保存全部失败；无增量臂或WC新调用，不能计算等质量降幅。
- **v4真实runtime及发布审查：** 613候选新依赖镜像构建1.203秒（缓存层）、4CPU/4GiB/256PID/2GiB可写容器smoke8.766秒通过、stdout7.4秒，UID10001/none网络/只读/白名单2公开文件，容器已清理。不是目标vMF sweep或2400秒预算充分性验证。actual release私有审查staging包含task.json+2资产，opaque任务ID/公开资源键及controller notes无known identity匹配，仍完整包含上述作者趋势因此不得发布。显式沿用已冻结factory EXP开发候选16模型/120工具/128MiB/2000项，物理资源不变，不冒称正式预算；无solver调用。当前ledger615/1668、0reserved，原625还剩10，条件追加4未解锁。已询问用户是否调整为625内最多6次明确回归验证；回复前无新模型调用，完整native轨迹独立审阅进行中。当前goal active，既未完整准入也未证明目标降幅。

- **v4轨迹审计已完成：** exp_old_native_trace_review.json完整解析525事件、108工具/108回包及13输出文件重建匹配；三角色同政策、sidecar保留issue，正确revise→drop，未发现阻塞工程缺陷。两role单行source_navigation回包截断，另一次cwd外Grep只读本session工具回包、已原源复算吻合，不声称完整原文呈现或OS隔离。exp_old_root_closeout.json绑定最终审计、146文件冻结重验；root再次核smoke容器无残留。ledger仍615，下一paid步骤待用户对有界回归调整的答复。

- **来源导航截断的零调用改进（待新协议接线）：** 新增独立opt-in paged_source_navigation.py，不改146冻结文件/原导航/source或任何模型材料。对真实单行导航的233个unit保序无损分为13个JSON页+索引，每文件≤16000 bytes，重组与原JSON深度相等、source hash绑定；超大不可拆unit/索引显式拒绝，绝不截断后称完整。5测试通过（首轮fixture不足一页而错误期望多页，已改8KB测试界限），audit/paged_navigation_diagnostic_v1.json。尚未接native runner、未验证模型实际读完或节省token/耗时；页头会增加总字节，不能当压缩或已降本。独立轻量复核进行中，ledger仍615，用户回归计划答复前不再启动paid步骤。

- **分页独立复核完成：** paged_navigation_independent_review_v1.json复核5测试及真实233unit重组、13页最大15876B，另核oversize metadata/index拒绝无部分输出；未发现阻塞。可供后续新freeze显式接线，仍无native读回或降本证据、无新模型调用。

- **v4实测角色成本诊断（零新调用）：** factory_efficiency_v4_role_cost_sensitivity_v1.json按613–615拆分：constructor输入2,111,016、reviewer3,201,955、adjudicator910,551；后两角色占输入66.08%。若保持审核成本不变，即使constructor输入归零，总输入最多降33.92%，达不到冻结45%目标；仅优化写文件不够。时间目标45%要求constructor590.281秒压至≤96.589秒（尾部审核成本假定不变）；输出50%要求constructor57950降至≤8785.5。这是失败旧臂的条件代数诊断，不是成功基线/预测，也不据此削弱独立审核。后续须同时验证增量证据导航是否降低review/adjud成本；无实测不得宣称分页/缓存已实现目标。ledger615、0reserved，下一paid方案仍待用户选择。

- **Goal阻塞审计（待工具返回状态）：** 原旧臂drop后，后续分页与角色成本两轮虽有零调用实质进展，但同一paid验证方案/预算阻塞持续；当前再核615、0reserved、无incremental启动。替换两组完整新对照需12次而原额度余10，条件4次不能提前挪用；已询问625内最多6次回归调整，尚无答复。factory_efficiency_v4_blocked_audit_v1.json明确未完成项与恢复条件，不以回归/离线/正确拒收冒充新鲜等质量降本验收；停止重复轮询和边缘开发，等待用户决定。

- **用户新额度与Goal恢复：** 用户明确“额度可以增加，增加到700”，当前账本615、0reserved，因此本goal余85；全球1668不改，旧冻结625/624/629记录不覆盖。工具已核Goal active。audit/factory_efficiency_goal_authorization_700_v1.json记录新绝对上限700；先最多6次、止621做明确修复回归（非新留出），同全政策/独立review+adjudication、同输入与公共identity；再依据结果冻结新鲜验证对照及有条件prospective。不把85用尽当目标、不自动重试，429仍停。此前预算/方案阻塞已由本授权解除，旧drop不改判，不用回归成功替代goal最终新案例降本验收。

- **700额度下的新回归准备在推进（未调用模型）：** root新增PagedNavigationRunner外层wrapper，两臂三角色共同获相同lossless分页导航，原nav/source不改；仅明确size超限回退原文件，hash/结构不符拒调用，角色结束校验导航不可变。5测试及独立三角色真实输入临时副本检查通过，未宣称实际模型读取/降本。driver协作者正实现新regression module/CLI（baseline615、phase max6/stop621、round3、class development_regression），不改146冻结source或绕v4固定预算；selection协作者新目录复制613候选/614review/615accepted notes，科学字节不手改，正常旧opaque→新opaque map，两臂共用。root尚未freeze或授权启动；整链fake与独立review通过后才调首臂。

- **新regression已冻结并启动（2026-09-27）：** 603项全离线测试591过/12依赖跳过；独立driver四层wrapper整链4测试及source分页复核通过，root逐项核94复制binding原/新字节一致。factory-efficiency-regression-20260927-001/execution/manifest.json冻结150文件并verify通过，case为exp_author_trend_regression、round3、development_regression，旧drop永久不改。已告知先旧臂最多3calls，启动session8949、exp-old.log；以实时ledger为准，尚无本轮科学/成本结论。phase硬止621/goal700，首臂drop/429拒继续；第二臂前root另核完整科学/runtime/actualrelease，不把native pass当全部准入。历史146冻结代码未改。

- **regression616–617新终态与付费证据恢复诊断：** 616constructor488.688秒、617reviewer404.625秒均native completed，模型共893.313秒/pipeline902.734秒，输入5,941,716/输出90,667；尚未调用adjudicator。617 rawdecision pass_with_pending_runtime但coverage.core_science=issue，指出R3-F1零设置headroom/floor效应（自称minor/nonblocking），被严格门以Cannot pass unresolved full-package checks: core_science拒绝；原result=failed_needs_attribution永久保留。独立科学actualrelease审阅未发现本次阻塞（未看617），泄漏真实移除、统计边界一致；真实新runtime passed，公共release另存pending，绝不以此消掉617意见。
- **不重跑已付费构造/审核：** 正独立核完整616/617证据及异常后未写的外层receipt，准备若可核实则另存显式continuation只调用原定第三adjudication（最多1新call、621phase帽内），带原review+coverage+失败诊断、同冻结policy/identity/paging，adjud可以裁定科学争议；不规范化原decision、不把issue改clear、不把旧failed改completed。只有独立完整性审计后root allow_adjudication_only批准才能启动，当前ledger617/0reserved。该恢复能力与任何后续调度均新文件，不改150冻结代码；不是自动retry或已完成配对。

- **显式单步裁定已冻结启动：** 独立完整性审计233绑定/386events/85tools通过，结论仅eligible_for_explicit_adjudication_only；root另存allow_adjudication_only授权，不是科学准入。新material_adjudication_continuation适配器6项fake/负测全部通过（root25.203秒），冻结SHA282bef1b…，原150文件不改；continuations/exp-old-adjudication-001只允许1新call，phase仍621/goal700。已启动session95825，仅送原617 review+coverage+冲突诊断交原定adjudicator，同完整policy/identity/paging；最终pass仍不得带issue，原failed保留，paid总成本含616–617。尚无新裁定结果，不启动增量臂。

- **call618裁定drop（原失败保留）：** 单步continuation完成，原arm逐文件未变；native拒R3-F1 headroom意见，但把R3-F2“绝对下降量可能将相同比例削弱判支持”升major并drop，最终core_science仍issue。独立科学/完整165events与工具审阅进行中，未启动增量臂；不改round3/drop、不把另存诊断当原pipeline成功。618耗279.765秒、输入1,594,999/输出25,821；616–618模型1173.078秒、输入7,536,715/输出116,488，原pipeline+诊断活动墙钟1186.125秒（不含人工审查暂停）。账本618/0reserved，goal余82；transport failed_calls=0不表示材料通过。终态审计exp_old_adjudication_terminal_attribution.json。

- **618独立审计闭环：** exp_old_adjudication_diagnostic_audit.json确认drop_supported_by_binding_H2_contract_conflict；165events/34tools、24Reads逐行、2writes字节及原arm/各层receipt一致。raw准确率比例及chance-margin比例两种独立反例均可骗过absolute-only判据，故不归schema/identity故障。仅读分页catalog而非pages，不冒称全源。C1允许relative/normalised/comparator，不唯一指定归一化；adjud建议双判据、扩大H1及近chance分母处理需另科学设计，不自动照抄。下一步先零调用限定最小修复范围，停止本候选增量臂；goal保持active，尚无新鲜配对降本验收。

- **本goal续轮零调用进展：** 前轮分类为progress（真实618裁定与独立反例改变下一步）。新factory-scope-preflight-20260927-001提出并独立复核H2选择性去共享的新操作化，9例18数值Decimal核对；root_scope_decision.json仅批准未来独立版本development_regression使用，不将616/618改判或称新鲜验证。保留方法/数据/资源与H1原范围，不强制特定归一化双条件；未来request/public/private必须统一替代旧absolute-only解释，预声明null仍需科学审核。当前无新candidate应用。
- **决策一致性与成本证据：** 新opt-in material_decision_guidance.py仅提示既有issue/unknown不兼容任何pass，4tests及独立复核通过，原17quality-contract测试通过；不改模型输出/不自动清issue/不重试，未真实调用验证。evidence_repetition_cost_review.json与material_evidence_read_cost_diagnostic_v1.json确认各role通常未重复整读package，主开销包含必需独立证据与多工具回合上下文重播；616–618审核+裁定占75.71%总输入，与613–615的66.08%不是同一批。原生已支持并实际批量Read，617为51tools/29tool-bearing messages、618为34/14，不能把批读建议冒称已节省成本。另存小evidence_read_batching.py只给增量臂可选读取调度提示，完整科学证据与三角色不削减，4fake tests通过。
- **下一真实对照准备（尚未freeze/调用）：** 为停止同例盲修，先取原v4预选但未跑的6ouZaBzeNO WRITE_CONTENT，顺序仍incremental→old；新v5目录40输入文件与原逐字节一致、新opaque map绑定新private prior。audit/factory_efficiency_v5_cases_v1.json与phase_authorization_v1.json另设baseline618/max6/stop624，累计仍700，不重置已花618、不追认原失败成功。新driver正在离线实现/独立预检，第二臂必须首臂actual科学+runtime+release全门通过；drop/429停。两臂同全policy/identity/paging/decision提示，仅增量启用seed/navigation与批读提示，比较流程组合而非纯constructor因果。WC只是一组新鲜对照，完整goal仍需第二新例及通过后prospective；当前ledger618/0reserved。

- **v5已冻结并真实启动首臂：** 40输入/24来源独立预检通过，无类似3n的显性scope冲突；fresh仅指未用于efficiency比较，非未构造。622全离线测试610过/12依赖跳过（219.069秒），新driver5整链/负测与batching4另经独立复核。execution/manifest.json冻结156文件并verify通过，root_start_preflight绑定输入/代码审计/全测试；原v4的146与regression150仍完整。已启动write_content_repair/incremental，session41267、write-content-incremental.log，第一臂至多3calls；第二臂不会自动启动，须新候选独立science/runtime/actualrelease全通过。本phase止624、goal700；不得因观察超时重启，须同handle核状态。尚无质量或降本结果。

- **v5首臂中途实测（619完成、620仍在途）：** 上一goal turn为progress，本turn复核同session41267确live、不重启。619稳定候选经root先读Dockerfile/requirements/smoke后，真实新CPU容器smoke3.14秒通过（1CPU/1GiB/64PIDs/512MiB/600秒，非root/无网络/只读三资产，清理verified_absent），仅环境验证不是完整solver预算证明。root首次compile误传source_manifest为字符串，TypeError属维护者调用错误，失败staging与invocation_error.json保留；改用constructor request sources后新incremental-002 staging成功，不改模型candidate/不耗调用。最终公开task+3资产known-ID0/binary0，待独立语义门。
- **619盲审初步结果：** write_content_incremental_preliminary_science.json在未读620前完成（168.315秒），核全部33publicfacts、三资产、私有reference/必要源锚点及actualrelease，未确认阻塞，F1/F2/F5修复成立；WRITE方法数值合法。MF08“scales linearly”可合法理解固定T高频尺度，并未要求所有有限窗精确比例，不能用更强命题反例误判；明确非finalgate。root预固定两臂相同WRITE开发release预算4模型/60工具/600秒、16MiB/500entries，不是正式或solver已测配置。完整620/621轨迹与最终独立门仍未完成，旧臂未启动。

- **结局（2026-10-06补记）：** v5降本对照（WRITE_CONTENT单例）完成：增量臂619–621通过，旧臂622–624审阅revise/裁定drop；增量比旧臂省26–31%（输入/输出/模型时间），未达45%/50%预注册目标（`factory-efficiency-v5-20260927-001/audits/pair_result_v1.json`）。第二组新鲜对照与prospective未做；随后转入v5生产工厂（含增量返修与质量/身份/分页组合），降本goal未作为验收通过关闭。

### 0.2.20 P11 batch2复盘修复与executor改定（2026-09-30，Claude Code）

- **修复（均零调用验证；repo未改，D盘进程内补丁+`D:/mrhbench-local-pilot/factory-v5-driver/repo_merge_v3/PATCHES.txt`第5–8项待git会话合并）：** ①单次工具超时只停该命令不再杀容器（容器内`timeout`，结果标`tool_timeout`，Docker实测；遗留僵尸进程占PID）；②`io.write_json`在Windows替换冲突时重试（#1139丢失原因）；③broker接受`/work/<p>`绝对路径（冻结H0自身拒绝绝对路径，故对H0靠④）；④release-v4零调用重编译13单元：改正发布说明第1条（旧文仍称`assets/assets/`双前缀，与补丁后实际单前缀不符）并写明`/work/<p>`→`<p>`路径约定，LIT加工具映射说明；资产/预算/资源/task_id逐项断言不变；⑤共享库页文本保留arXiv锚点`[§S2.p3]`（182篇HTML中179篇有），声明页码为控制器分页；⑥检查：合同字数上限（flag）、提交声称路径须已收集（`claimed_paths`）；⑦judge **v3.5**（`judge_v35.py`，v3.4原文后追加6条：缺失须先搜证、判错须引两侧原文、失败类型以平台记录为准、任务/平台不一致单列不归solver、确定性检查逐条确认、私有参考不入反馈）+公开证据`controller-platform-failure-summary`。v3.5尚待§7.2逐轨迹验收。H0按协议未改。
- **executor改定（用户2026-09-30）：** opus-5-5过强（旧均分约3.4）、haiku-4-5过弱（约1.2，且退役不早于2026-10-15）会压缩builder区分度。校准：Sonnet 4.6/medium三题3.75/3.5/2.8（偏高）；**Sonnet 4.6/low** WC2.75/WE2.75/IDEA3.0/KST EXP2.0。用户**固定executor=claude-sonnet-4-6 / effort low**（`factory-v5-driver/config/role_transport_sonnet46low_executor.json`，同一faithful wrapper；judge仍opus-5-5/medium v3.5；H0冻结v3）。单次运行波动约±0.5，未作多次重复；LIT尚未在此配置测。旧opus/haiku分数为release-v3/judge v3.4条件，只作参考不混比。
- **重测结果（10题，Sonnet4.6/low，release-v4，judge v3.5）：** tree-RL WC2.75/WE2.75/IDEA3.0/EXP0.5/LIT1.75；KST WC3.75/WE2.75/IDEA2.6/EXP2.0/LIT0.5；均分2.24。首轮tlit/klit/texp撞429（1347–1349）未评，保留，`-r2`新目录重跑。账本1417/1668。
- **逐轨迹审阅（3个独立subagent，零调用，`D:/mrhbench-local-pilot/p11-sonnet46low-review-{A,B,C}.json`）：** 审阅者分与judge差≤0.25（10题中9题完全一致或±0.25）；无私有泄漏；v3.5规则1/2/3/5/6基本遵守，规则4（任务/平台不一致单列）最弱。**归因更正：** texp与klit的0.5主要不是收尾预留，而是H0的4条观察窗口致executor遗忘（texp编造starter中不存在的import三次崩溃；klit把bibliography.json重写18次、其余交付物未写），预留仅占1步。新发现H0缺陷（冻结不改，仅记录）：写回执只含路径/hash、模型看不到自己写的内容（IDEA两题hypotheses与proposal不一致、WC覆盖映射错位）；run_python忽略args.text；不向模型展示其历史动作。**root自身引入的bug：** 库页说明与LIT提示中的示例锚点`[§S2.p3]`被模型照抄成不存在的引用；锚点在部分节内稀疏。其他待修：失败摘要把ProtocolError一律描述为代理/schema问题且未含H0 stop_reason；broker工具错误无原因码（改需升接口版本）；检查漏读task.md/`requirements`中的字数范围、复合required-files键未按路径检查、WE manifest无schema检查、LIT引用可解析性检查未实现；材料层面task.json合同与task.md措辞不一致（tree-RL WE manifest字段）。judge另有：未读harness_notes、部分事实表只读一半、个别单缺陷多维重复扣分。
- **第二轮修复（2026-09-30，用户要求修框架与材料bug；executor确认固定Sonnet4.6/low）：** v3.5重评旧opus KST WC：3.75→4.0（v3.4误判事实错误的traceability扣分消失）。框架（零调用）：release-v5去掉示例锚点（LIT提示与库页说明改为“抄最近的锚点、不得自造”；锚点并不稀疏，S2正文在S2.SS1.*下）；失败摘要中性描述ProtocolError并列出失败工具路径是否存在及H0自报stop_reason；检查新增task.md/requirements中字数/token上限、复合文件键拆分、同名schema（WE manifest）、LIT锚点可解析检查（tree-RL LIT唯一不可解析的就是照抄的S2.p3；KST EXP缺config.json现被检出）；judge **v3.6**（`judge_v36.py`，+规则7–10：任务/平台不一致核对、如何结束、关键输入读完、一缺陷一处扣分），待§7.2验收。broker原因码未做（worker/broker hash绑定在冻结H0 freeze.json且H0读不到新字段，留接口v5）。材料（经标准pipeline的维护返修，`maintenance_repair.py`，controller写返修请求→增量构造→独立审阅→裁定pass/drop→runtime→release-v5）：tree-RL WE（合同写明manifest字段+新增`manifest.schema.json`，数据/起始代码字节不变）与tree-RL LIT（task.md改为实际三个文献工具与锚点规则）均审阅pass、裁定pass、runtime passed；调用1418–1424（LIT裁定撞429一次，`--resume-adjudication`续跑，失败目录保留）。合并说明`repo_merge_v3/PATCHES.txt`第9–13项。下一版factory prompt应加“合同与task.md字段/文件一致、任务文本描述实际工具”规则（改prompt须新factory根）。账本1425/1668。
- **统一条件下的10题成绩（Sonnet4.6/low，release-v4/v5，judge v3.6，新检查；2026-09-30）：** 重跑3题（新目录`p11-v5-sonnet46low-{twe,tlit,klit}-v36`）+其余7题v3.6重评（`<run>/rejudge-v36/`，原评分保留），调用1426–1478全部completed、无429。tree-RL WC3.0/WE2.5/IDEA2.8/EXP0.75/LIT1.75；KST WC3.75/WE2.75/IDEA2.8/EXP2.0/LIT1.25；均分2.34（模块：WC3.38/WE2.63/IDEA2.8/EXP1.38/LIT1.5）。tree-RL LIT锚点引用全部可解析（示例锚点问题消失），claims.json schema仍失败（executor）；KST LIT交付齐全（0.5→1.25）。控制台已改为读取重评结果并标judge版本与executor effort。账本1478/1668。
- **judge v3.6逐轨迹验收（3个独立subagent，零调用，`D:/mrhbench-local-pilot/p11-v36-acceptance-{A,B,C}.json`）：三组均“带保留通过”。** 审阅者分与v3.6：10题中7题完全一致，其余差0.25（EXP两题judge各高0.25）；无私有泄漏；规则3/8（失败归因、如何结束）全部到位，规则10消除了v3.5的重复扣分，KST WC事实表本次读全、v3.4误判未复现；7题v3.5→v3.6分数变化均值+0.07、无单向漂移；judge成本约+19%（列表价估算）、墙钟持平。保留意见：规则9对长文件仍只读首尾（均自行声明，结论经核对成立）；规则7漏判数处（KST EXP schema检查缺失、KST WE数据说明“随w增长”与任务事实“w²”不一致被算给solver、KST LIT task.md的工具描述与平台不符）；tree-RL EXP结论分2偏宽（审阅者给1）；个别事实错误（称solver未看图/未读定理段，实际都有）。单次运行，规则效应与噪声未分离，不等于全局可靠性证明。
- **第三轮修复（零调用，PATCHES第14–16项）：** 第二轮复合键拆分引入的回归——KST EXP的results.json schema检查被丢——已修（按文件自身合同条目绑定schema，兼容`_schema.json`；补跑该提交schema通过，judge当时依赖solver自报结论无误，不重评）；多文件schema（`files`映射）可逐文件检查，KST LIT claims.json的schema失败（confidence用了数值）现可检出；锚点检查对未读摘要的“abstract”与“§1”类伪锚点判不可解析（tree-RL LIT 29处中20处不可解析）；库read说明不再写“PDF page”。
- **pipeline漏洞与材料第二轮维护返修（2026-09-30/10-01，用户批准）：** 根因确认：factory v4 constructor addendum从未告知平台实际工具（文献三工具、锚点格式、CPU只能跑/work下脚本），两篇LIT都编造了接口。新增零调用确定性检查`task_platform_lint.py`（未授予的工具调用描述、LIT未提literature.*、要求运行公开根目录脚本），回看可抓到全部已知问题并新查出KST WC同类问题；下一版factory constructor“平台契约”草案在`factory-v5-driver/prompts_next/constructor_platform_addendum.txt`（改prompt须新factory根，仅影响以后批次）。维护返修KST LIT（task.md改为实际工具/锚点、check_output.py先复制到/work再跑，release-v6）、KST WE（“随w增长”统一为w²，release-v5）、KST WC（check_output.py运行说明，release-v5），均审阅pass、裁定pass、runtime passed、各只改一个文件、lint清零。重跑首次三题均首请求429（1488–1490，保留），`-m2`重跑：KST LIT 2.0（1.25→）、KST WE 3.25（2.75→）、KST WC 3.0（3.75→，judge扣的是局部缺口，属单次运行差异，非材料问题）。
- **当前10题成绩（Sonnet4.6/low，judge v3.6，最新材料与检查）：** tree-RL WC3.0/WE2.5/IDEA2.8/EXP0.75/LIT1.75；KST WC3.0/WE3.25/IDEA2.8/EXP2.0/LIT2.0；均分2.39（模块：WC3.0/WE2.88/IDEA2.8/EXP1.38/LIT1.88）。每题单次运行，波动约±0.5。账本1524/1668。

### 0.2.21 factory-v6：平台契约、OpenReview取源、并行与7篇新论文（2026-10-01/02，Claude Code）

- **factory-v6驱动**（`scripts/factory_v5_driver/factory_v6.py`，进程内组合，不改仓库核心文件）：v5基础上①constructor/审阅者提示词追加平台契约（v6.1：精确授予工具名`artifact_read_write`/`cpu_python_execution`/`artifact_image_view`，LIT加`literature.*`；审阅者检查内嵌同一权威描述——v6漏列看图工具与文献签名，造成2处误判，已修）；②编译用冻结executor预算（`executor_budget_freeze_v1.json`：EXP16/WE12/WC10/IDEA10/LIT30）并跑`task_platform_lint`；③**OpenReview优先取全文**：用户账号经官方API（openreview-py）取会议终稿PDF，凭据在仓库外`C:/Users/li_ha/.openreview/credentials.json`，只在控制器取源步骤内读取、token不落盘、不入任何模型会话；CLI Read把正常PDF误报"有密码"，控制器另用pypdf抽取带页码文本作派生来源；④背景文献截止日改为min(arXiv v1, OpenReview公开日odate)——旧规则只用arXiv v1，审计发现Microcanonical(2412.03312仅有截止后版本)与Root Cause(2406.05014取了v2)混入截止后文献，已重取；⑤`--workers N`并行（v5的`self._ctx`改线程本地，修复跨论文上下文串用）；⑥两条用户批准的接受规则：CLI自行拒绝且未执行的工具调用记警告；引用控制器发布的元数据文件(source_manifest/candidate/source_audit.json)合法；⑦泄漏规则A：私有核查计划/评分细则逐字复述公开要求的命中降为审阅标记，其余仍拦截。
- **7篇新论文**（批准名单第12–18名，factory-v6根）：构造184次（#1585–1768）+三轮维护返修约75次（含429失败）。截至2026-10-04有效编译题：v6七篇25道（Root Cause 5、Variational Search 4、Microcanonical 4、Leave-One-Out/Gyrogroup/Sensitivity/Integral各3）+v5三篇14道，共39道；Microcanonical IDEA撤回未恢复。维护脚本`maintenance_repair_v6.py`/`maintenance_group_v6.py`：返修说明逐字取自上一轮独立审阅/裁定已接受问题+控制器说明，支持多轮、v5根与已编译单元重建；控制器文件复制步骤（`controller_asset_materialization`，哈希核验）。
- **事故**：计划任务`/SC ONCE /ST 23:59`占位触发在9-30与10-01的23:59自动重跑旧脚本（多2次调用#1491/#1752，第二个factory进程与run008并发），已杀进程、补记账本、删除46个任务、改为过去日期触发；`audit/incident-scheduler-autofire-20261002.json`。
- **独立公开面泄漏审计**（零账本调用）：38道已编译题中5道确认泄漏（多为公开justification字段以否定句列出目标贡献/缺口结论），已撤回并返修通过（泄漏原文核对已删；tree-RL LIT与GETS LIT旧P11分数因此作废）；15道存疑待用户/导师判定。教训：下一版构造/审阅提示词须明文禁止公开字段以任何形式（含否定句）陈述目标方法/贡献/结论/日期，平台lint补相应检查；私有核查计划不得增加公开合同之外的要求（3个单元因此drop）。
- 账本上限1668→1818→1868（用户2026-10-01/02授权）。
- **factory v7（草稿，用户2026-10-04同意方向）**：`prompts_next/constructor_platform_contract_v7.txt`与`reviewer_platform_check_v7.txt`在v6.1上加公开面规则R1–R5（任何公开字段含否定句不得陈述目标方法/贡献/结论/术语/日期/会议；截止日不写来源；私有核查只能检查公开合同所写；LIT/IDEA问题不写目标角度；控制器复制映射）；`task_platform_lint.py`新增`public_field_disclosure`（含题面内嵌JSON），对4个撤回旧版全部标出、返修版0、现有39题标6处（多为WRITE_CONTENT合法披露，作审阅标记）。待新根factory-v7冻结后用1–2篇小规模验证返修率/泄漏率。
- **下一步**：27道新/返修题P11试跑（Sonnet4.6/low executor+judge v3.6，共享文献库v5纳入v6背景并用修正截止日）；v7驱动与小规模验证；15道存疑题待判定。git：0f3e9fd/8433fb0/e43ca03（核心PATCH 1因Codex冻结门绑定旧双层前缀，保持驱动进程内补丁）。

### 0.2.22 factory-v7：扩充到25篇、泄漏审计与控制器修复（2026-10-05/06，Claude Code）

- **v7驱动**（`factory_v7.py`=v6+公开面规则R1–R5提示词+控制器复制`controller_asset_materialization`）与夜间监督进程`supervisor_v7.py`（用户2026-10-05批准：追加额度至2918、429后自动续跑、目标25篇；保持3篇并行，429等待20→90分钟，达标/余额<30/连续429>12/3轮无进展即停）。2026-10-06 11:55达标：**25篇有≥1道编译题**（v5 3篇、v6 7篇、v7 15篇），账本2671/2918。
- **v7 vs v6（单元层调用，不含论文级源审计/裁定）：** 不靠维护返修即编译 v6 13/26（50%）→ v7 59/70（84%）；首轮即过1→17；平均构造轮2.04→1.77；每道编译题调用8.9→6.2。v7分题型编译：EXP13/14、WE14/15、WC12/15、LIT10/13、IDEA10/13。
- **独立公开面泄漏审计（零账本调用，`D:/mrhbench-local-pilot/audit-v7-public-surface-20261006.json`+`-addendum.json`）：** 56道中36无问题、9存疑、11确认泄漏。身份泄漏0；EXP/WC/WE除5qg6JPSgCj EXP存疑外全部无问题。**问题全部是R4型且集中在LIT/IDEA**：题面/必选主题/背景报告复述目标论文的问题清单、动机缺口或方法要素组合（IDEA 13道中10道、LIT 11道中9道为泄漏或存疑）。结论：v7的R4提示词规则与审阅者未能阻止该模式，LIT/IDEA构造方式需改（候选：控制器仅按截止日前背景文献生成背景报告、或加可推导性对抗审查），待用户决定；泄漏题撤回与存疑题判定亦待用户。`collection_contract_provenance.json`含论文ID但不挂载给solver（只发布task.json与assets/），已核。
- **用户批准的规则/修复：** ①泄漏规则A扩展（2026-10-06）：公开检查/校验脚本（文件名含check/validat/verif的`.py`）中复述公开要求的命中同样降为审阅标记，私有来源条件不变；BdmVgLMvaf IDEA据此经`rerun_runtime_v7.py`零调用重跑runtime/compile通过，旧失败保留为runtime.failed-1。②控制器bug修复（无需新决定，执行既有min(arXiv v1, OpenReview公开日)规则）：`build_job`的`first_disclosure`原只取arXiv日期，arXiv未找到的论文为null，v1B4aet9ct LIT因此PENDING占位被drop；`factory_v6.FactoryV6.build_job`现用背景阶段同一截止日。已核同类论文已编译的LIT/IDEA自定了更保守日期，不受影响。
- **维护返修候选（未执行）：** EJfLvrzh2Q WC（WC-F17/Eq.63缺定义条件）、1qq1QJKM5q LIT（R4）、v1B4aet9ct LIT（截止日bug，重建即可）、IXyfbaGlps IDEA（私有定位节号错，一处）、msEr27EejF WC（隐藏自动判失败R3）与EXP、5qg6JPSgCj IDEA/WE、aXuWowhIYt WC/IDEA、KeRwLLwZaw LIT。
- **下一版提示词待改：** CPU工具`arguments`/`timeout_seconds`直接复制`runtime/interface_container_v4.json`（v7遗漏致5qg6JPSgCj IDEA drop）；LIT/IDEA构造改造（见上）；私有核查不得超出公开合同的确定性检查（R3）。
- **控制台：** 构建看板重构为论文×题型紧凑矩阵（状态色块+阶段点+试跑分、筛选/搜索、点行展开），`console/server.py`增加每篇`requested`题型。

### 0.2.23 search set v1 冻结与factory-v8（2026-10-06，Claude Code）

- **用户决定（2026-10-06）：** ①当前25篇论文（v5 3篇、v6 7篇、v7 15篇，即每篇≥1道有效编译题）为第一个固定版本 **search set v1**，builder演化harness在此集合上进行；按源论文划分，同篇所有派生任务同集合。**论文名单现在冻结**（`research/benchmark/audit/search_set_v1_membership.json`，membership_sha256 79f0663c…）；**题目清单待这些论文被撤回/放弃的LIT/IDEA用factory-v8重建并审计后再冻结**。冻结清单须含题目ID、发布包hash、预算/资源、**文献库版本**（同一集合内所有harness版本共用同一冻结库；不同库版本下的LIT分数不可比，用户2026-10-06提出）、judge版本、executor配置、H0 hash。②**正式运行executor=经faithful反代的claude-sonnet-4-6/low**（取代§0.2.15“正式实验改官方API”的计划）。③演化轮数R与重复次数等跑完第一轮演化后再定。test set另选不同源论文，用v8流程构建并单独冻结库。
- **冻结时有效题84道：** EXP21/WC25/WE24/LIT8/IDEA6；已撤回IDEA13/LIT8/EXP1（泄漏）。LIT/IDEA偏少，故先用v8补齐再冻结题目清单。
- **v7泄漏处理结果：** 独立审计（首轮52题+补充4题）、9道存疑独立复审（盲预测+L1–L4判据，先独立结论后看前次疑点）、返修后3道IDEA复审，共撤回21道（20道LIT/IDEA）；维护返修12次调用：WC 3道与5qg6JPSgCj WE成功，IDEA 3道返修后仍泄漏被撤回，LIT 3道与msEr27EejF EXP放弃。结论：读过目标论文的构造者写公开面在结构上会泄漏，返修不能解决。
- **factory-v8（用户批准方案，`scripts`待合并：D盘`factory-v5-driver/factory_v8.py`、`prompts_next/v8/`、`constructor_platform_contract_v8.txt`/`reviewer_platform_check_v8.txt`、`tests_v8/`）：** 仅LIT/IDEA改流程，EXP/WC/WE不变。论文级`area_brief`（裁定角色只读标题+摘要：≤60词中性问题领域+私有禁用词）；单元级`frame`（构造角色、**不见目标论文**，只用截止日前背景论文+中性领域+控制器截止日写全部公开面；LIT不再有必选主题清单；确定性检查禁用词与截止日一致，失败重试一次再放弃）→`construct`（公开文件预置并锁定，控制器逐字节比对、禁止新增公开文件、公开事实须等于frame事实）→`probe`（盲推者只看公开面预测目标贡献）→`leak_judge`（读论文+公开面+预测，L1–L4，控制器逐字核验引文）→裁定（泄漏/不确定：第1轮强制重写公开面+返修，重写依据剔除论文内容；最终轮放弃；裁定只能被收紧）。另：任务单写入截止日依据（arXiv查询结果、OpenReview公开日、文献库排除方式）；控制器复制后自动把复制源移出资产清单；v8平台契约补`cpu.run(script, arguments, timeout_seconds)`签名。16项离线测试通过，真实数据零调用干跑确认框架工作区无目标论文、盲推工作区无私有材料。试点：新根`D:/mrhbench-local-pilot/factory-v8`重建n8h1z588eu LIT、YOc5t8PHf2 LIT、BdmVgLMvaf IDEA、5qg6JPSgCj IDEA（预计28–52次调用），完成后用同一复审prompt独立审计并与v7比较。
- **其他决定/修复：** 泄漏规则A扩展到公开检查脚本（用户2026-10-06）；v6/v7 build_job截止日改用min(arXiv v1, OpenReview公开日)（v1B4aet9ct LIT因空截止日被drop）；控制台构建看板改紧凑矩阵。账本2709/2918（v8试点前）。正式演化单轮完整search评测约1,200–1,500次调用，需届时另行授权额度。
- **v8试点结果（2026-10-06，调用2714–2755共42次）：** 4个v7撤回单元全部编译通过（n8h1z588eu LIT 12次、YOc5t8PHf2 LIT 7次、BdmVgLMvaf IDEA 13次、5qg6JPSgCj IDEA 14次，平均约11.5次/题，含每篇1次领域简报）；独立泄漏审计（同一复审prompt，`D:/mrhbench-local-pilot/audit-v8-pilot-20261006.json`）**4/4可接受**并与工厂关卡一致（v7中这4题均为泄漏）。关卡实际拦下2道IDEA第1轮泄漏（盲推未认出论文仍预测出核心方法），重写公开面后通过；5qg6JPSgCj的禁用词检查另拦下一次“score-based”。**两次泄漏同一根因：背景文献由读过论文的裁定者挑选，含对应方法要素的旁支文献，框架会话如实总结即泄漏**→待做“背景文献集中性化”补丁（已由v8.1 `bg_screen`实现，§0.2.24）。残余风险：BdmVgLMvaf被盲推/审计者凭记忆认出（题面无引导，记为memorisation risk）；截止日恰等于arXiv v1日期是弱线索。控制器修正：盲推/判定引文超长只警告（n8h1 probe2零调用恢复，`accept-stage`）。

### 0.2.24 统一标准S1–S5、factory-v8.1/v8.2与统一审计（2026-10-07—12，Claude Code）

- **用户决定：** v8.1（2026-10-06）：做背景筛选，公开截止日=披露截止日−14天（N=14），+250额度。统一规则（2026-10-09，“还是统一规则吧，确保所有题目最终产物标准一致”）：**S1** LIT/IDEA一律用v8.1+流程重建，EXP/WC/WE须满足v7 R1–R5与v8平台契约；**S2** 全部题目过同一份独立审计（U1身份、U2贡献/结果泄漏、U3私有检查不超出公开合同、U4平台描述、U5合同一致、U6平台lint复核）；**S3** 全部零调用重编译到最新发布格式；**S4** 当前镜像下runtime门；**S5** H0基线可解性。执行顺序（2026-10-09）：先A1、B、C，A2额度够再做。v8.2（2026-10-11）：“做8.2，有问题就立刻修”。
- **factory-v8.1**（`factory_v8_1.py`，根`factory-v8_1`）：论文级加`bg_screen`（在`area_brief`后，筛掉含目标方法要素的旁支背景）；公开截止日=披露截止日−14天，背景文献版本日期须严格早于它；LIT编译写`lit_corpus_configuration.json`；控制器规范化（零调用、逐条记录到`controller_frame_fact_evidence_normalized.json`）：非source_fact/source_result的事实去掉指向构造请求本身或未声明来源的自引用证据；source事实只在去掉后仍留有声明证据时去；对已声明来源，错误的`source_sha256`改为请求中的hash（来源ID与定位不动）。`rebuild_v81.py`跑14篇20单元，3篇并行，首个429即停；7篇未开始者经`v8_1_deferred_papers.json`移交v8.2。
- **factory-v8.2**（`factory_v8_2.py`，根`factory-v8_2`，提示词与v8.1逐字节相同，只改控制器）：①**审阅意见转给框架作者**：第1轮被接受的审阅意见若指向锁定公开文件，只取修改要求（adjudicator repair_note或reviewer repair_action，不传可能引用论文的observed_issue），且不含目标论文来源ID/范围请求/禁用词时，转交不见论文的re-framer；不满足的拦下并在返修说明中注明“论文特有覆盖要求不适用于v8公开面”；记录`reframe_review_routing.json`。泄漏或有可转意见时都重写，之后照常probe2+leak_judge2。②**结构门送返修时仍做第1轮盲推与泄漏判定**（公开面即锁定框架，不受结构门影响）；仅在公开面打包失败时跳过。根因：v8.1中1qq1/EJfL IDEA因锁定文件里的背景引文/检查器问题无法修而撤回，cyPM IDEA因第1轮泄漏检测被跳过而在最终轮撤回。
- **统一审计（S2，零账本调用）：** 5个独立subagent，71道（含5qg6 EXP返修版）：**55过、16小修、0大修**，身份泄漏0。结果`D:/mrhbench-local-pilot/unified-audit-v1-result{1..5}.json`，返修清单`unified-audit-v1-repair-list.json`与`unified-audit-v1-repair-notes/`。其中qgsX WC/WE、SyVP EXP/WE只是旧发布说明（`assets/assets`双前缀），已有新release，留S3处理。
- **B维护返修**（`audit_repair_v1.py`：只把审计意见作返修说明，`maintenance_notes_audit_v1_<root>/`，每道3次；`--resume`在429后同批次重跑，v5系不支持只重跑审阅故构造会重做）：12道**9过**（l11D WC、1vrp WC、d1NW EXP、z21D WE、qpXc EXP/WC/WE、SyVP WC、BdmV WC，按当前格式重新编译）**3撤**（1vrp EXP：返修中裁定发现公开事实F-SRC-08与源码不符；QMtr EXP：隐藏检查3与公开合同不一致未修好；Bt1v WC：私有评分合同大小写规则自相矛盾）。3道编译lint发现均为误报。
- **A1结果（截至2026-10-12）：** 已编译 v8.1：1qq1 LIT、BdmV LIT、EJfL LIT、IXyf LIT、KeRw LIT；v8.2：YOc5 IDEA、v1B4 LIT。撤回：IXyf IDEA（两轮盲推都猜中，合理）、5qg6 LIT（私有参考写错两处背景细节，可维护返修）、QMtr IDEA（结构门bug耗掉第1轮）、1qq1 IDEA、EJfL IDEA、cyPM IDEA（均为v8.2已修缺口）；v8.2：v1B4 IDEA（第1轮泄漏重写公开面后第2轮仍判L1/L2泄漏，按规则撤回，合理）。C：5qg6 EXP maint2裁定pass、编译release-maint2，统一审计复核通过。
- **这几天修掉的平台问题（均零调用恢复、失败目录保留）：** Docker Desktop重启后未自启致runtime失败（`rerun_runtime_platform_v81.py`）；Windows下账本锁文件删除中`os.open`抛PermissionError未等待（`platform_patches.py`第9节，4线程800次压测通过）；`--retry-platform`未挪开`frame_ws_retry`（`factory_v8.py` STAGE_PATHS）；v8.2中glob字符串传给`read_json`（修复前启动的进程撞到5个单元，均在调用前出错，已重置）；pdF8 IDEA返修构造者抄错`bg018_abs_page`的hash被结构门拦下（控制器改写声明hash后重置返修，构造多花1次）。v8系离线测试`tests_v8/`共39项通过。
- **控制台更新（2026-10-11）：** 工厂根每次刷新重新扫描（v8_2可见）；论文显示最新根并可悬停看全部根；v8阶段中文名与排序；“已编译·返修放弃”标记；试跑结果按账本目录汇总executor/judge的调用数、输入/输出token；修正executor输入token重复计算（反代usage的`input_tokens`已含缓存）。

### 0.2.25 2026-10-12：search set v1.1/v1.2、Oral替换试点、factory-v8.3/v8.4与IDEA撤回分析（Claude Code）

以下为2026-10-12当日“当前断点”原文（晚间整理时原样移入；其中“正在运行”“下一步”等为当时快照，现状以文件开头“当前断点”为准）。

- **search set改为v1.1（22篇，用户2026-10-12）：** 审稿分审计（`research/benchmark/audit/search_set_v1_review_scores_audit.json`，25篇=4 Spotlight/21 Poster/0 Oral，均分6.56≈ICLR 2025录用中位）后，把有审稿人最终打3分的3篇移出search set：**QMtrW8Ej98（Microcanonical Langevin）、1qq1QJKM5q（More Experts Than Galaxies）、IXyfbaGlps（Color Equivariant）**，放入`audit/held_out_pool_v1.json`（不删，以后可能作held-out）。新名单`audit/search_set_v1_1_membership.json`（membership_sha256 `7da426d6…`）；v1名单文件原样保留作历史。各自工厂目录（factory-v6/v7/v8_1）下加了标记`SPLIT_HELD_OUT.json`，未改任何state/单元。**search set相关工作不再在这3篇上花调用**（含下面③中的1qq1/QMtr IDEA、④中的QMtr EXP）。
- **search set v1.2（用户2026-10-12选方案B、分步执行；第1步）：** 把剩余修复量最大的3篇Poster（l11D、1vrp、cyPM）换成3篇Oral：**Xo0Q1N7CGk（grid cell共形等距）、GMwRl2e9Y1（VQ旋转技巧）、kbjJ9ZOakb（单神经元不变流形；代码CC BY-NC、猕猴数据受限，只能做仿真分支）**。名单`audit/search_set_v1_2_membership.json`（22篇，membership_sha256 `a89d4a8a…`，新3篇status in_construction）；被换3篇进`audit/held_out_pool_v2.json`（6篇，含v1的3篇）并在工厂目录放`SPLIT_HELD_OUT.json`；v1/v1.1名单与held_out_pool_v1原样保留。**正在运行**计划任务`mrh-newpapers-v82`（`factory-v5-driver/newpapers_v82.py`，factory-v8_2根从fetch到compile全流程，3篇并行、单篇上限55次，首个429后不开新论文），日志`factory-v8_2/newpapers-v82.log`；撞429后恢复时手动`schtasks /Run /TN mrh-newpapers-v82`。预计约135–165次（账本余约240）。进度（2026-10-12）：3篇论文级阶段全部完成；裁定请求题型Xo0Q、GMwR为五类全做，kbjJ只做EXP+WC（数据受限，不出LIT/IDEA/WE），分题构造中撞429（2026-10-12，kbjJ与GMwR已停，Xo0Q在途调用结束后也会停），额度恢复后已手动`/Run`续跑（第2次运行，**在跑**；注意单篇55次上限按每次运行计，不累计）。**第1步运行已结束（`NEWPAPERS DONE`，账本3188，共约113次）**：已编译10道——Xo0Q EXP/LIT/WC/WE、GMwR五类全部（IDEA第1轮判L1/L4泄漏、重写后通过）、kbjJ WC；撤回Xo0Q IDEA（两轮均判泄漏，控制器关卡drop）。kbjJ EXP的runtime门`failed_needs_attribution`：字符串泄漏检查唯一命中是通用代码行`with open(path, encoding="utf-8") as fh:`（私有`population_draw.py`与公开`starter/evaluation.py`都有，恰好40字符），属误报；拟加规则“纯通用代码样板行不算泄漏”并零调用重跑runtime/compile——**待用户批准**（泄漏规则改动历来需用户同意）。kbjJ EXP：用户2026-10-12批准**泄漏规则B**（单行通用Python样板——open/import/`__main__`——同时出现在私有.py与公开.py中，降为审阅标记；`leak_rule_v6.py`，备份`*.pre-ruleB.20261012`），零调用`rerun_runtime_v82.py`重跑runtime+compile已编译（lint 4条同一处误报：“target”指目标神经元）。**试跑验证（用户：先验证这3篇质量，额度保守、串行）：**计划任务`mrh-p11-v82-oral`（pilot_v5.py，冻结H0 v3+Sonnet4.6/low+judge v3.6），9道按预算从低到高串行：3 WC→GMwR IDEA→2 WE→3 EXP，最坏约121次；撞429不开新题；两道LIT因新论文背景未并入共享库v5，留到T17后再测。日志`p11-v82-oral-s46low.log`，输出`p11-v82-oral-s46low/`。executor反代用计划任务`mrh-wrapper`启动（`run_wrapper.cmd`，127.0.0.1:8765）。**事故与修复（2026-10-12）：**新v8.2单元缺控制器`checks.json`（旧单元由`checks/gen_generic_checks.py`补生成），前4题（3 WC+GMwR IDEA）executor跑完后在评分前FileNotFoundError；已零调用为11个新单元生成checks.json，后续题正常（Xo0Q WE已评2.5）；4题不重跑executor，计划任务`mrh-p11-v82-finish`在试跑`.done`后串行补评（`finish_pilot_judge.py`加可选原因参数，备份`*.pre-reason.20261012`；日志`p11-v82-oral-finish.log`）。pilot_v5无`-u`致试跑日志缓冲为空，看`p11-v82-oral-s46low/pilot_summary.json`。控制台：试跑结果扫描加`p11-v8*`；5小时额度统计改为只读最近400次账本调用的events.jsonl（原整盘递归约60秒致页面卡住），备份`server.py.pre-fasth.20261012`。试跑页每格加executor/judge入出token（E/J），论文名旁加factory版本标签（题在更新根重建时格内另标），备份`index.html.pre-pilottok.20261012`。试跑页再按划分分组（search set计入平均／held-out／名单外各自小计），组内按论文factory版本降序。所有论文名旁加录用类型+OpenReview最终均分标签（Oral绿/Spotlight蓝/Poster灰，悬停看各审稿人分；数据来自候选池decision与`review-score-audit-20261011/iclr2025_accepted_ratings.json`），备份`*.pre-decision.20261012`。**试跑结果（2026-10-12完成，9道，单次运行，开发证据）：**Xo0Q WC3.25/WE2.5/EXP2.25；GMwR WC3.25/WE1.75/EXP2.25/IDEA2.2；kbjJ WC3.0/EXP0.5（executor把整个实验做成一次3110秒运行、只在最后写结果，超时无产出，judge归因solver）。均分2.32，旧search论文同配置均分2.31（WC3.2/WE2.11/EXP1.64/IDEA2.68）。硬检查失败：GMwR WE files+schema、Xo0Q WE schema、GMwR EXP schema、kbjJ EXP files+schema（归因2026-10-12：GMwR WE与kbjJ EXP为solver未交文件；Xo0Q WE为solver漏填一处source_record_ids；GMwR EXP为双方：schema要求`experiments`为字符串、`key_numbers`为对象，而task.md只写“what you ran”“each with key_numbers”不标类型，solver写成列表/文本，且9次调用从未打开过schema文件——题面与schema类型说明不一致属材料小问题（U5），可在维护返修时让task.md写明类型或放宽schema）。试跑共72次（账本3188→3260/3318）。这3篇做完、核查后再决定第2步替换哪几篇。控制台已改为读版本最高的held_out_pool并显示尚未开始的论文数。
- **LIT/IDEA产出排查（2026-10-12，零调用）：** ①**系统性控制器缺陷：**取源阶段只在`sources/manifest.json`记arXiv日期，OpenReview公开日（odate）要到背景阶段`factory_v6.background_cutoff`才取；无arXiv版本的论文在裁定时看不到任何公开日期，裁定者按E2推迟LIT/IDEA（h0vC、oANk、spDU、kbjJ），v6早期背景阶段也因“no cutoff date”撤LIT/IDEA（z21D、d1NW）——共6篇因此没有LIT/IDEA。修法（待用户同意）：取源时把OpenReview公开日写进manifest并在裁定请求里给出截止日。②Bt1v：21篇背景只取到2篇（<5撤）。③v8.x LIT 13道编译12（健康）；IDEA 15道编译7、撤8，第1轮盲推被判泄漏10/15，撤回多为两轮都泄漏（控制器关卡）或最终轮补不上——IDEA是主要瓶颈，可能混有模型对已发表论文的记忆（盲推者能猜出），待定是否调整IDEA判据或流程。用户2026-10-12：①现在修、②先分析解释，均交给新会话；交接prompt在`D:/mrhbench-local-pilot/handoff-prompts-20261012/`（`1-fix-openreview-cutoff.md`、`2-idea-leak-analysis.md`）。
- **①已修（2026-10-12，Claude Code，零调用）：factory-v8.3**（`factory-v5-driver/factory_v8_3.py`，继承v8.2，只改控制器、提示词快照与v8.2逐字节相同）：取源阶段在`sources/manifest.json`写`first_disclosure`（arxiv_v1、OpenReview公开日odate、disclosure_cutoff=两者较早、public_cutoff=−14天、basis、查询状态）；裁定/源审计工作区的source_manifest.json随之可见；背景阶段、bg_screen、frame、build_job一律读这条记录、不再二次在线查询（缺记录即报错，controller_cutoff与记录不符即报错）。新命令`carry-dated`从旧根复制fetch（可选source_audit/area_brief）并只在**副本**上写记录。**另建根理由：**沿v8.2惯例便于追溯，且重裁定需要新state，旧根state/产物不得改。新根`D:/mrhbench-local-pilot/factory-v8_3`已init（from v8_2，24个提示词hash与v8_2相同）并carry-dated kbjJ（fetch+source_audit；source_audit的A17正是“无公开日期”，交新裁定处理）。测试：`tests_v8/test_factory_v8_3.py`新增8项，连同原39项共47项两种顺序均通过。零调用核验（`D:/mrhbench-local-pilot/first-disclosure-check-20261012.json`）：kbjJ、h0vC、oANk、spDU、z21D、d1NW均无arXiv，OpenReview公开日均为2024-10-04→披露截止2024-10-04、公开截止2024-09-20；v8_2的kbjJ manifest未改，账本仍3260。Bt1v为另一原因（背景只取到2/21），不在此修复范围。除kbjJ外5篇为Poster，按方针不补LIT/IDEA。用户2026-10-12批准在v8.3跑kbjJ：计划任务`mrh-kbjj-v83`已结束（日志`factory-v8_3/kbjj-v83.log`，**共3次调用3261–3263**，账本3263）。**日期修复生效：**新裁定请求LIT,IDEA,EXP,WC（不再按E2推迟）；但背景文献只取到7/23（arXiv标题检索：12篇not_found——多为期刊/bioRxiv神经科学论文；4篇fetch_failed无细节，可能是临时错误），bg_screen保留3/7（NeRF/SimCLR/SRN/Fourier features判为旁支），少于5篇，控制器规则让LIT/IDEA在frame前撤回（0调用）。kbjJ仍无LIT/IDEA；EXP/WC留在v8_2。**用户2026-10-12决定：放弃kbjJ的LIT/IDEA**（交叉学科、太特殊）；不扩充背景取源渠道。kbjJ在search set中保留EXP（v8_2）+WC（v8_2）。背景只从arXiv取、神经科学等非arXiv领域背景天然不足——记为已知限制（零调用探查备查：16篇缺失中bg001/bg005其实在arXiv，arXiv标题检索失败但OpenAlex可解析出id；Europe PMC对bg002/bg010/bg018/bg022有开放全文；其余为付费期刊仅摘要）。factory-v8.3的公开日修复保留，今后新论文用v8.3根。**下一步（用户）：**等IDEA撤回率分析/修复会话完成后，再选一篇Oral在v8.3构造材料包。驱动文件清单已发git管理会话。
- **IDEA撤回原因分析（2026-10-12，分析会话，只读、零调用；待用户决定，未实施）：** 结论与证据`D:/mrhbench-local-pilot/idea-leak-analysis-20261012/analysis.json`，说明页`report.html`（同目录）。**更正：**v8根IDEA共15单元（编译7：5qg6、BdmV、GMwR、YOc5、aXuW、msEr、n8h1；KeRw无v8 IDEA）；第1轮只在13单元运行，泄漏10/13；cyPM只判了最终一轮、从未重写（v8.2修复的起因，修后未重跑）。**8撤的构成：**重写后仍泄漏4（IXyf、Xo0Q、v1B4、pdF8；pdF8另因重写删掉前作保证前提而被裁定者判“误述前作”）、第1轮被结构门路径跳过而无重写机会2（QMtr、cyPM）、非泄漏2（1qq1、EJfL最终判可接受，因锁定公开面事实错误在v8.1不能返修而撤）。**原因：**①盲推者“认出论文”几乎普遍（12/15单元，含6道已编译），判定者在4道重写后通过的题里已把匹配归因于记忆，故记忆不是撤回主因；②持续泄漏的题多为“目标贡献=直接前作自述的局限/未来工作”（IXyf、Xo0Q、cyPM、pdF8）或领域简报本身即主打缺口（v1B4，第2轮未认出的盲推者仍猜中）；③重写只删句子：10次重写把第1轮泄漏原句全部删掉（0残留），失败的4道第2轮被找到同内容新段落；pdF8中去泄漏与准确性正面冲突。**判据问题：**D1 协议§3.2规定IDEA输入含“局限和候选缺口”，但泄漏判据只对LIT豁免发现缺口；D2 认出论文的盲推者事后挑的“引导段落”无法区分记忆与公开面引导；D3 无严重程度、uncertain=leak、partial与specific同罚、单样本；D5 缺第1轮判定被当作可接受（`stage_reframe`中`_leaky(None)`为假，备注写“round 1: acceptable”）。**方案（待用户选）：**O1维持判据只修流程（EJfL重跑≈10–14，修D5）；O2新根v8.3按§3.2允许“截止日前来源自述、如实标注的缺口”不算L1，按解决机制判匹配（重判Xo0Q/v1B4/pdF8终版3次，前两道裁定已pass可零调用编译，pdF8重建≈12–15；已编译题不必重审；改泄漏规则需用户同意）；O3把认出论文记为记忆风险标记并做含/不含敏感性分析，可加“避开所认论文”的反事实盲推（每单元+≈2次；无知识早于ICLR 2025的可用模型，真正无记忆对照做不到）；O4只用较新论文出IDEA（每篇≈45次，对前作自述缺口类无效）。严格方案“认出即泄漏”会只剩5qg6、n8h1，不可行。建议O1+O2并采用O3的标记部分。
- **factory-v8.4（用户2026-10-12批准O1+O2，零调用实现完成；模型运行待用户确认额度）：** `factory-v5-driver/factory_v8_4.py`（继承v8.3；v8.3已被OpenReview截止日修复占用，故另建版本）。**O2（提示词，`prompts_next/v8_4/`，与`prompts_next/v8`相比只改`leak_judge.txt`、`framer.txt`）：**泄漏判定仅对IDEA新增“来源自述缺口”规则——截止日前背景来源对自身工作所写的局限/条件/开放问题/未来工作，如实且标注出处，单独不算L1/L2；只有公开面超出来源（点名为THE gap、配上补救、拼成配方、框架作者自造缺口）才算；L3/L4不变；预测匹配按解决机制判，只猜中缺口或前作至多partial。框架作者（IDEA背景报告）：准确优先，如实标注来源自述局限，不得为显得不引导而删掉真实前提；重写时保留并去掉编辑性强调。**O1（控制器）：**第1轮盲推+泄漏判定一律运行，结构门/锁定框架检查送返修时用锁定框架（frame/assets+frame事实）作公开面；`stage_reframe`缺第1轮判定即报错，不再记“acceptable”。零调用命令：`carry-paper`（复制论文级阶段、可选`--with-unit`，在副本写v8.3公开日记录，公开截止日与已有frame不一致即拒绝）、`rejudge-final`（每单元1次判定调用：用v8.4判定重判终版公开面+原probe2预测，对**原有**修复裁定重新套关卡，不重调裁定者；v8.2记录改名`*.v82`保留）。测试`tests_v8/test_factory_v8_4.py`新增10项，连同v8–v8.3共57项两种顺序均通过。新根`D:/mrhbench-local-pilot/factory-v8_4`已init（from v8_3，24个提示词hash中只有`v8_framer.txt`、`v8_leak_judge.txt`不同）；已零调用carry：Xo0Q、v1B4（含IDEA单元，供重判）、pdF8、EJfL（不含单元，供IDEA重建）；四篇公开截止日与原frame一致（2024-05-13/09-20/07-05/02-02），旧根manifest未改。**待跑（需用户确认）：**①`rejudge-final` Xo0Q、v1B4（2次；通过则零调用runtime/compile）；②pdF8、EJfL IDEA在v8.4重建（各≈10–15次）。用户2026-10-12批准先跑①，**①已完成**：`rejudge-final` 2次调用（日志`factory-v8_4/rejudge-final-20261012.log`），Xo0Q判acceptable（match specific，判定者归因于盲推者认出论文、公开面只如实标注前作）、v1B4判acceptable（match partial，盲推者未认出、机制不同）；随后零调用runtime+compile均通过（`runtime-compile-20261012.log`，calls_taken 0），**search set新增编译2道IDEA（factory-v8_4）**；v1B4 lint 2条为误报（“What they leave open (as stated in the sources)”被当作函数调用）。注意：①两题尚无控制器`checks.json`，试跑前须用`checks/gen_generic_checks.py`零调用生成（v8.2试跑事故同因）；②Xo0Q为“认出论文”题，记忆风险标记（O3）尚未实现。②用户2026-10-12决定先只做EJfL，**已完成并编译**（7次调用3266–3272：frame 2〔首次撞禁用词“100% population accuracy”〕、construct+审阅2、probe 1〔认出论文〕、leak_judge 1〔acceptable，match specific，归因记忆〕、裁定1〔pass，无返修〕；runtime通过、lint 0）。EJfL、Xo0Q、v1B4三个v8.4单元的checks.json已零调用生成（各4项）。**v8.4至此search set新增编译IDEA 3道。**用户2026-10-12批准pdF8，**已完成并编译**（7次调用3273–3279：frame 2〔首次撞禁用词“strongly concave”〕、construct+审阅2、probe 1〔认出论文〕、leak_judge 1〔acceptable，match specific，归因记忆〕、裁定1〔pass〕；runtime通过；lint 1条误报“open (a gap…”；背景报告如实保留LSVRG“smoothed objective”前提——上次正因删掉而被判误述）；checks.json已生成。**v8.4共新增编译IDEA 4道（Xo0Q、v1B4、EJfL、pdF8），共用16次调用，账本3279/3318。**原记录：计划任务`mrh-pdf8-v84`（`run_pdf8_v84.cmd`，v8.4仅pdF8 IDEA frame→compile，`--max-calls 15 --retry-platform`，启动时账本3272），日志`factory-v8_4/pdf8-v84.log`，结束写`pdf8-v84.done`；撞429后手动`schtasks /Run /TN mrh-pdf8-v84`。原记录：计划任务`mrh-ejfl-v84`（`factory-v5-driver/run_ejfl_v84.cmd`，v8.4根仅EJfL IDEA单元frame→compile，`--max-calls 15 --retry-platform`，启动时账本3265），日志`factory-v8_4/ejfl-v84.log`，结束写`ejfl-v84.done`；撞429后恢复时手动`schtasks /Run /TN mrh-ejfl-v84`；编译后需零调用生成checks.json。pdF8暂不做。合计≈22–32次；账本3261/3318，kbjJ（v8.3，旧判据）在跑预计还用15–35次，额度大概率不够。kbjJ IDEA若因泄漏撤回，可用`rejudge-final`（1次）按新判据重判。驱动文件（`factory_v8_4.py`、`prompts_next/v8_4/`、`tests_v8/test_factory_v8_4.py`）待并入仓库，清单已发git管理会话。
- **方向调整（用户2026-10-12）：** A2暂缓；与其花额度把旧Poster题修到统一标准，不如直接用ICLR 2025 Oral/Spotlight论文新建题目、替换进新版search set，先提升源头质量。候选：140篇批准名单中未开始的Oral 7+Spotlight 8篇；候选池另有带仓库的Oral/Spotlight约140篇未经scout初筛（池内共Oral 213/Spotlight 380，带直接仓库69/124）。现search set中Spotlight仅4篇（SyVP、qgsX、qpXc、msEr），其余18篇为Poster。规模、额度与现Poster论文去留待用户定。2026-10-12统计（给用户取舍）：仍需花调用的Poster论文8篇——5qg6（LIT维护≈3）、EJfL（IDEA挽救≈14）、cyPM（IDEA挽救+LIT A2≈24）、l11D/1vrp（LIT+IDEA A2各≈26）、KeRw（IDEA A2≈14）、aXuW（LIT A2≈10）、pdF8（LIT/IDEA在跑）；修完共≈120次。新建一篇按v7/v8.2实测≈45次（35–55，平均出≈3.8道）；替换8篇≈360+初筛；Spotlight 3篇（qpXc/qgsX/SyVP）的A2≈80次无论哪种方案都要做。
- **v1.1构成（2026-10-12快照，控制台口径）：** 22篇、已编译82道（2026-10-12撤回1vrp EXP、Bt1v WC后）：LIT 13（另2在建、1撤：5qg6）、IDEA 11（n8h1、aXuW于第三轮编译；另2在建：msEr/pdF8，3撤：EJfL/v1B4/cyPM）、EXP 18（2撤：msEr、1vrp）、WC 21（1撤：Bt1v）、WE 21；6篇按裁定不出LIT/IDEA（z21D、h0vC、Bt1v、d1NW、oANk、spDU），2篇无EXP（qgsX、oANk）。v5/v6旧LIT/IDEA待A2按S1重建。**控制台**构建看板已加划分筛选（默认search set，可切held-out池/全部）、“search set构成”表与held-out标记；`server.py`从`audit/`中版本最高的`search_set_v*_membership.json`与`held_out_pool_v1.json`读名单（备份`*.pre-split.20261012`）。
- **阶段：** search set v1论文名单（25篇）已冻结，**题目清单未冻结**（现按v1.1的22篇执行）。按用户2026-10-09的统一标准S1–S5（§0.2.24）补齐与清理全部题目：A1=v8.1/v8.2重建撤回的LIT/IDEA；B=统一审计71道并维护返修；C=5qg6 EXP返修（已完成）；A2=18道旧LIT/IDEA（排队，额度够再做）。
- **正在运行（勿重复启动；查状态看日志/state，不看进程名）：**
  - 计划任务`mrh-rebuild-v82`：factory-v8_2重建7篇（YOc5、aXuW、cyPM、msEr、n8h1、pdF8、v1B4），日志`factory-v8_2/rebuild-v82.log`（追加写）。2026-10-12快照：已编译YOc5 IDEA、v1B4 LIT、n8h1 IDEA、aXuW IDEA、msEr LIT/IDEA、pdF8 LIT（第三轮；msEr IDEA第1轮判泄漏、重写公开面后通过）；撤回pdF8 IDEA（两轮均泄漏）；撤回cyPM IDEA、v1B4 IDEA（两轮泄漏判定均L1/L2泄漏，控制器关卡把裁定pass改drop）。第一轮已`REBUILD DONE`，已自动再`/Run`第二轮（已结束单元0调用跳过），**第二轮在跑**：aXuW IDEA、msEr LIT/IDEA、n8h1 IDEA、pdF8 LIT（均从reframe起）、pdF8 IDEA（从repair起）。第二轮撞429停（调用3053–3055三次构造失败入账）；2026-10-12第三轮跑完（`REBUILD DONE`），**v8.2重建已全部结束**：第三轮编译n8h1 IDEA、aXuW IDEA、msEr LIT/IDEA、pdF8 LIT；撤回pdF8 IDEA（第2轮仍判L1/L2泄漏，最终轮drop）。
  - 续跑惯例：每撞429后等额度恢复，手动`schtasks /Run`对应任务；重建驱动自带`--retry-platform`，被429打断的单元从断点续跑；同一轮内已结束为`failed_needs_attribution`的单元不会自动重跑，需按§0.2.24的方式先核因再挪开阶段（`<stage>.failed-N`留存）并写history。
  - 计划任务`mrh-console`：控制台 http://127.0.0.1:8770/ （`schtasks /End`杀不掉其python子进程，重启须先按8770端口找PID结束）。
  - 已结束：`mrh-rebuild-v81`（REBUILD DONE；7篇未开始者经`factory-v5-driver/v8_1_deferred_papers.json`跳过、移交v8.2）、`mrh-audit-repair-v1`（B返修12道全部跑完，日志`audit-repair-v1-r{2..7}.log`）。
  - git交接已备好未提交：`D:/mrhbench-local-pilot/git-handoff-20261012.md`（75个驱动文件清单+仓库文件），git管理会话为`meta-research-harness-bench-ad`（会话d6750f36，即2026-09-24被任命者；2026-10-12核实），交接说明已发给它。
- **最新结果：** 详见§0.2.24。A1已编译7道（v8.1 5道+v8.2 2道），撤回6道；B返修9过3撤；统一审计71道55过16小修0大修。
- **固定配置：** builder/judge/构造各角色=Claude Code原生claude-opus-5-5/medium；executor=经faithful反代的claude-sonnet-4-6/low（正式运行也用它）；judge=Claude原生v3.6；H0=冻结v3（`D:/mrhbench-local-pilot/h0-claude-frozen-v3`，sha `619dc724…`）。模型调用走当前登录的Claude CLI账号（用户在多个账号间切换，2026-10-11起为另一账号）。
- **额度：** 共享账本`research/benchmark/audit/development_call_ledger.json`上限**3318**（2026-10-06 +250用于v8.1重建；2026-10-12 +150用于A2，用户“A2入账ok”，已记authorization_events），2026-10-12记入时已用3063。失败和429都计入。订阅5小时窗口很紧，约每4–5小时撞一次429，各运行逐个手动续跑。
- **代码位置：** 仓库核心`research/benchmark/mrhbench/`；工厂驱动在`D:/mrhbench-local-pilot/factory-v5-driver/`（v8.1/v8.2：`factory_v8_1.py`、`factory_v8_2.py`、`rebuild_v81.py`、`rebuild_v82.py`、`audit_repair_v1.py`、`rerun_runtime_platform_v81.py`、`maintenance_repair_v6.py`、`platform_patches.py`第9节、`tests_v8/`；均未合并入仓库，需通知git管理会话）；运行目录与审计副本在`D:/mrhbench-local-pilot/`（不入git，勿清理）。
- **下一步：** ①v8.2剩余单元跑完；②5qg6 LIT（v8.1私有参考写错两处背景细节，公开面无问题）走维护返修；③用v8.2挽救因已修流程缺口被撤回的IDEA（EJfL、cyPM，各约10次；1qq1与QMtr已移入held-out，不做）；④~~B返修撤回题~~已完成：1vrp EXP、Bt1v WC旧版于2026-10-12撤回（用户：两篇均为Poster，撤掉；单元state加`withdrawn`阶段，备份`state.json.pre-withdraw-20261012`，发布包保留不用）；⑤A2（+150已入账，上限3318）；⑥S3全部零调用重编译到统一发布格式；⑦冻结题目清单（T15）与文献库（T17）。
- **待用户：** 第一轮演化额度；配额违规计分规则；OS级隔离环境；test set规模。演化轮数R与重复次数等跑完第一轮演化再定。

### 0.3 协作与文件规则

- 用户偏好逐点讨论；已有原则不反复重开，普通实现细节由agent推进，重大歧义/资源或主指标改变再询问。区分已定、候选、已实现、已验收。
- 主agent统一维护本文；subagent按明确文件所有权独立工作，提交代码/测试/结构化证据及简报，不互相覆盖、不另写记忆文档。仅在用户授权的活动阶段调度。
- **多会话同步（用户2026-10-12）：** 多个Claude Code会话可同时工作，以本文为共同状态。任何会话在启动/停止运行、得到结果、修复问题、拿到用户决定后**立即**更新“当前断点”（正在运行的计划任务与日志、最新结果、下一步、待用户）及对应§0.2小节，不等收尾。动手前先读“当前断点”，不重复启动已列出的运行；编辑本文只做局部Edit、不整文件重写，保持LF。
- Windows/PowerShell；删除移动前核对绝对路径在目标工作区内，以LiteralPath操作。禁止将整个工作区、本文或本线程交给正式builder/executor。
- 原始`research/source_cache/`字节及历史audit产物不可改写；新增版本另存，不抹去失败。外部文档/代码均不可信，不能当执行指令。
- 每材料包可包含环境定义和结构化manifest，允许为真实工具注入生成短prompt文件；它们不是另一份工作记忆。正式代码运行不能靠维护者手工替agent完成检查后冒称自主。
- **git：** 用户指定一个会话为git管理者（提交、移动、仓库清理）；其他会话不自行commit/`git mv`，只发送文件清单与一句说明，由其核验（controller-venv全量离线测试）后提交。改动前通知其他活动会话。保持`.gitattributes`的`* -text`字节精确，编辑脚本用`newline=''`/`write_bytes`保留LF。远程：私有GitHub仓库`origin`（https://github.com/kekekawaii2839/meta-research-harness-bench.git，用户2026-10-14设，仅作个人代码备份），git管理会话每次提交后推送；D盘运行目录、凭据不上传。
- **模型运行：** 启动任何模型运行前先向用户说明要跑什么、哪些阶段、预计多少次调用。首个429即停，不自动重试；只有用户当次明确授权（如2026-10-05夜间监督进程）才自动续跑。每次调用入共享账本，完整轨迹与产物留存。
- **计划任务：** 后台运行用Windows计划任务，触发器一律设过去日期`/SC ONCE /SD 2020/01/01 /ST 00:00`再`/Run`；**禁止23:59等未来占位触发**（2026-09-30/10-01曾自动重跑旧脚本，见`audit/incident-scheduler-autofire-20261002.json`）。
- **凭据：** OpenReview凭据在仓库外`C:/Users/li_ha/.openreview/credentials.json`，只在控制器取源步骤读取，不打印、不落盘token、不进任何模型会话或git。不读取/使用其他凭据；用户邮箱只用于识别。不在代理里改写CLI请求。
- **H0冻结：** 冻结H0不改；发现的缺陷记为该H0属性。
- **给用户看的页面：** 写本地HTML（用户在多个claude.ai账号间切换），不发布artifact。

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
| 当前缺口 | search set v1题目清单与文献库版本冻结（统一标准S1–S5清理与v8.1/v8.2重建进行中，§0.2.24）；test set构建；judge全局可靠性；OS级角色隔离；真实混合演化尚未运行；正式轮数/重复/样本量。CPU包级Docker、R2共享库、H0、材料工厂与P11试跑已有开发实测 |

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

**历史访问约束 [已定；LIT-R2为当前唯一方案]：** 各材料包收集强相关、弱相关及易混淆真实背景文献，去重后形成全局共享文献库；模型可自由查询该库，但不访问开放互联网，不限定每题专属书单。底层search/read对搜索返回、摘要及正文统一执行每任务cutoff、版本和目标排除规则，检查跨split答案暴露；仅纳入允许公开的背景文献，不混入题面、目标答案、阶段产物及私有评分材料。检索结果不公开材料包归属/相关性标签，保存实际检索与阅读证据以便重放。评测环境限制浏览器/终端/HTTP绕行。截止早于目标最早已知公开版本，核查arXiv v1、技术报告、项目/代码披露，未知标待核验，不能仅用会议日期；v8.1起公开截止日再取披露截止日−14天（§0.2.24）。当前共享库v5（`D:/mrhbench-local-pilot/shared-library-v5`）由factory v1–v6各论文的截止日前背景文献合成，271篇；按实际版本日期严格早于每题截止日过滤，并按目标arXiv id与OpenReview id/别名排除目标。**库随材料增加而变大，检索难度随之变化：同一评测集合内所有harness版本必须使用同一冻结库版本，不同库版本下的LIT分数不可比（用户2026-10-06）**；v7/v8新论文背景尚未并库。领域覆盖与近邻难度仍未验收。

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

确认规格 → 固定源材料与版本/权利 → 统一语义材料与来源定位 → 构造阶段输入及包级CPU Docker环境/资源契约（Claude原生工厂，§0.2.16起；LIT/IDEA用不见论文的v8.x公开面流程）→ 独立上下文对照原始来源审核 → 程序检查/时间与答案泄漏审计 → 真实运行及成本pilot → 返修或淘汰 → 覆盖矩阵验收 → 按源论文划分并冻结。先少量异质论文试产再批量，构造者不能自行宣布科学验收。

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

**H0 prompt来源 [方向已定；Claude builder已按接口v4构建并冻结H0 v3，§0.2.13]：** 可以参考一个或多个较完善的research harness，由独立subagent阅读并归纳成足够自包含的统一构建prompt，使全新agent能据此构建支持本benchmark整个评测过程的harness。多个参考可提供互补能力，不要求每个参考单独覆盖全部需求，也不因参考多个系统而为不同builder提供不同prompt。不是继续凭空手写完整需求，也不直接把参考代码作为各builder的H0。须检查固定阶段起点、统一接口与工具/预算边界的适配；“autonomous research”名称不等于满足全部任务。区分必要能力/接口与参考实现，不把复刻特定内部架构当唯一正确答案。参考归纳见`research/benchmark/reference_harnesses.json`及`prompts/builder_h0.txt`；全新agent构建曾因运行权限失败（Codex时期），后由Claude原生builder构建并冻结H0 v3；正式prompt与接口须审核冻结并统一提供。全新agent只拿发布输入，不继承本线程或维护者目录。H0阶段不看search任务及反馈已确认，见§6.2。

**Builder：** 交付一个能从给定阶段起点执行任务的统一 harness；使用注入的 executor/tool/budget 客户端；说明入口与依赖；内部结构自由；不得访问维护者材料、更改评分器或调用未授权模型。规范提供模块 IO、公开 rubric、资源边界和格式 smoke，不提供目标方法/gold。

**Evolver：** 基于上一版本完整混合search反馈改进共享代码，在限定轮次内提交冻结版本并接受同一search集合重评；记录成本、修改和回滚依据，不在轮内追加未登记的正式评分。外层费用记录而非硬预算停止。每轮版本均交隔离test，结果不回流；结束时仅依据search可见信息选择H_builder，维护者另行统计test-best，不给隐藏失败轨迹或暗示某种结构一定优越。

统一 prompt/工具权限跨 builder 保持一致；prompt 内容、提供哪些文献/反馈、是否允许额外检索、版本选择方式，均需在正式实验前固定。

**Search/test隔离 [用户再次明确]：** 演化/改进期间builder仅能看到给定的search任务部分，各轮冻结harness在其余隐藏test任务上评价。沿用研究家族隔离，不能把同论文派生任务随机分两边。隐藏test题面仅在冻结harness执行相应任务时提供，不向外层builder开放题目、轨迹或反馈。最终汇报H0、H_builder与事后test-best；后者不回流演化或影响builder选择。

**Search反馈范围与双产物 [已确认；实现待验收]：** Builder可见search任务和允许输入、自身运行轨迹/代码/产物、主分/维度分、失败或违规状态及成本；不可见隐藏test、其他被测builder解答、私有参考答案和评测材料。Judge体系生成两份明确分离的产物：①内部评分/审计记录，包含完整判分依据、证据、私有参考核对、问题与不确定性；②builder可见的改进feedback，定位公开证据中的行为问题、证据位置、受影响要求和可迁移的改进关注点。不能直接公开内部评语，不能把私有内容换种措辞当安全反馈；不泄漏标准答案，不规定必须采用某种agent架构或直接替builder写修复代码。单次执行缺陷不自动证明harness的具体根因，须区分已观察事实与可能原因，由builder决定如何修改。**[午间最新决定] 同一次原生judge评审（2026-09-24起为Claude原生judge，当前v3.6；此前为Codex）同时产出内部评分记录与可发布feedback，不另设feedback agent或独立反馈调用。** Prompt明确区分两份产物，benchmark发布层按字段白名单导出允许分数及feedback，完整judge轨迹/私有理由不回流builder。因judge读过私有材料，输出分离不等于上下文隔离；反馈须定位executor可见证据中的问题，不泄漏私有内容及答案，需专门进行来源/泄漏检查与逐轨迹验收。两份产物均纳入逐轨迹验收：评分是否有依据，反馈是否定位问题、瞎归因、泄漏答案或代做改进；相关费用计入账本并与对照对齐。同次评分+feedback已在Claude原生judge（v3.2起结构化输出judgment与feedback，现v3.6）实现；向builder发布的字段白名单导出与feedback泄漏检查待第一轮演化前验收，旧分开调用仅保留历史记录。

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

- 采用一次独立原生judge会话（当前Claude原生v3.6；历史为Codex）主动取证并同时产出内部评分和公开feedback；同次会话可有多次工具交互，不等于一次无工具文本补全。分任务类型编写prompt，薄层只管理发布/验证/成本，不自建推理循环；不默认多judge投票。
- 不复用上一任务的评价记忆，不给judge看模型身份、harness名、H0/H*标签或已有分数以免影响判断。所有对比对象用相同冻结协议；反射复核不等于独立验证。
- 验证候选包括：等价表达保持质量、已知证据缺陷被识别、有效负结果不因不支持假设扣科学质量、Faker式无执行但产物自洽、映射漏项、无关信息增加、证据检索遗漏。只对有可核查预期的案例算误接受/误拒绝；不要把开放主张强行贴成绝对真值。
- 除重复评分稳定性，检查后期演化产物及排名对judge选择/取证方式的敏感性；报告无法判断率与费用。通过这些检查不等于专家等价或覆盖所有科学错误。
- Search反馈按§6.3已定双产物协议：内部评分记录与builder改进feedback分离，分数/状态/成本及自身执行证据可见，不公开私有参考/隐藏检查。正确评分和有用的改进反馈分别验收，具体发布过滤与调用实现待定。不要求发明新judge训练法，也不把完整独立judge benchmark设为前置工程。

**当前状态：** 用户已认可五维、judge输入、事实判定与分档质量评分、0–4量表、前四维等权主分与资源单列，以及严重错误/负结果/故障处理原则。具体锚点和案例由主agent在后续开发样例及逐轨迹验收中落实，不逐条追问用户。judge现为Claude Code原生claude-opus-5-5/medium（v3.6，2026-09-24起；此前gpt-5.6-sol原生Codex为历史配置）；内部取证循环不再自建，评分和feedback同次输出。旧开发实现及审计已有；新版具体锚点、取证额度和失败处置仍须实现及验收。

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

**注（2026-10-06）：** 本表为2026-09-22前SSA/IV开发样例的历史审查，不代表当前材料。当前材料以工厂产出的search set v1为准（§0.2.20–0.2.23、§12 T13/T15–T16），各题审计在D盘运行目录与`audit/`。

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
| 材料工厂（v5–v8.2） | 仓库`mrhbench/factory*.py`；驱动`D:/mrhbench-local-pilot/factory-v5-driver/`（`factory_v5.py`…`factory_v8_2.py`、`supervisor_v7.py`、`rebuild_v81.py`/`rebuild_v82.py`、`maintenance_repair_v6.py`、`audit_repair_v1.py`、`leak_rule_v6.py`、`task_platform_lint.py`、`prompts_next/`、`tests_v8/`；部分仓库副本在`scripts/factory_v5_driver/`，v7之后的待合并）；运行根`D:/mrhbench-local-pilot/factory-v{5,6,7,8,8_1,8_2}` |
| search set与审计 | `audit/search_set_v1_membership.json`；v7公开面泄漏审计`D:/mrhbench-local-pilot/audit-v7-public-surface-20261006*.json`、存疑复审`audit-v7-uncertain-rereview-{A,B,C}.json`、返修IDEA审计`audit-v7-maint-idea-20261006.json`；统一审计S2`D:/mrhbench-local-pilot/unified-audit-v1-result{1..5}.json`与`unified-audit-v1-repair-list.json` |
| P11试跑与控制台 | 运行目录`D:/mrhbench-local-pilot/p11-*`（各题`judge_run_result.json`、`rejudge-*`）；judge验收`p11-v36-acceptance-{A,B,C}.json`；控制台`D:/mrhbench-local-pilot/console`（http://127.0.0.1:8770/） |
| 共享文献库 | `D:/mrhbench-local-pilot/shared-library-v5`（`corpus.json`，271篇；每LIT题`lit_corpus_configuration.json`记录corpus_sha256） |

上游采样历史：官方快照4040事件，处理后3705候选记录（不是官方录用总数断言），1369条直接GitHub链接；30项主题pilot，29仓库metadata/28README；OpenReview评分未取得，不能当低分。多数默认分支快照不是论文时commit；许可/完整性须逐资产审核。第三篇Fragmented知识论文仅取得源材料，未派生任务。

旧独立三轮模拟评审的核心建议已合并到§2、§7–9及TODO：research场景不自动构成充分创新；judge可靠性/可迎合、任务对harness敏感度、反向出题泄漏、低成本成功研究选择偏差、家族相关性、TTS归因都需证据。评审不是专家真值或录用承诺；不恢复已否决的人类专家评分、六碎片WRITE或跨论文强合并。

## 12. 唯一待办表与依赖调度

状态语义：待实施／离线实现／真实运行待验收／验收通过／等待用户或环境。**代码存在、单元测试通过、开发案例有效和正式准入是不同状态**。以下是执行计划，不将未执行项标完成。

### 12.1 全量主线待办

| ID | 工作包与实施要点 | 依赖与验收条件 | 当前状态 |
|---|---|---|---|
| T00 | **包级CPU Docker执行底座（新增显式前置项）**：EnvironmentSpec/ResourceSpec、每包环境定义/锁定依赖和镜像版本；每run独立容器/输入/输出。controller持有Docker权限；worker不得挂Docker socket、凭据或整工作区，禁特权/宿主网络，限制权限/CPU/内存/进程/存储和时限。模型与检索走受控broker，不把凭据交给任意研究代码。 | 先核可用宿主/daemon，再用两个包不同资源配置测试构建、启动、读写、超时、OOM/进程上限、清理、跨任务/宿主越界和残留状态。固定依赖不等于字节确定性重现。无可用daemon时可完成代码测试，但真实验收不能passed。 | 两包压力/边界诊断等开发验收保留；材料工厂runtime门对每个单元实际构建包级镜像（FROM锁digest）并在声明资源、无网络、只读、非root下跑烟雾；单次工具超时只停命令（§0.2.20）。正式角色隔离与跨宿主仍未验收 |
| T01 | **订阅调用层审计**：区分原生Codex与executor模型transport；核模型/medium、继承上下文、工具开关、文本/图像、权限/失败；优先官方订阅通道。旧codex exec JSON包装不是HTTP反代，也未证实裸API等价。 | 最小真实调用、参数与完整事件核查；与T00确定凭据留在可信controller的调用桥接。不能把高分直接归因于调用层。 | executor=faithful反代claude-sonnet-4-6/low（§0.2.15/0.2.20，正式运行沿用，§0.2.23）；builder/judge/构造=Claude原生ClaudeNativeRunner。残余差异见§0.2.15；CLI宿主进程非OS隔离 |
| T02 | **原生Codex judge**：五类prompt模板，原生主动查文件/图像；同次生成内部判分和公开feedback，薄层做发布/格式验证/固定汇总/成本记录。 | T01、T07；真实受限会话读到必要证据，评分/feedback分离。复核提交代码需独立隔离执行，不放宿主自由执行。 | Claude原生judge v3.6（v3.4精确schema/图像tile+规则1–10），同次评分+feedback；公开失败摘要证据；P11已用于39道题 |
| T03 | **judge区分度与行为审核**：补各维度0–4锚点；IDEA要素完整不等于研究价值；WRITE可交付性缺陷不能被平均分掩盖。正反例、自然错误、无硬伤不同质量、等义/顺序/重复、feedback泄漏；调prompt样例与留出验收例区分。 | T02及T05；逐条审完整被评/取证/判分轨迹。已知标题遮挡、事实定位、数字/方法错误、无实验和EXP归因漏检回归；不得强行压分、用作者论文作唯一gold。改变主汇总/门槛须另确认。 | v3.6十题逐轨迹验收带保留通过（7题与审阅者完全一致、余差0.25；无私有泄漏；§0.2.20）；规则7/9仍有漏判与只读首尾。全局可靠性/方差未证，T03未整体关闭 |
| T04 | **预算与计时**：题面、runner、模型/工具/CPU子进程读取同一份**当前包/任务**配置，无静默全局fallback；按剩余额度超时并杀进程树/容器，恢复不重置账本。 | T00；配置不一致拒启，边界耗尽/失败/恢复实测。总wall保留；开发人工暂停显式记事件，总时长和扣除时长均报告；正式计时规则冻结后执行。judge另计，外层演化仍限轮次不硬限研究费用。 | executor预算冻结`executor_budget_freeze_v1.json`（模型调用EXP16/WE12/WC10/IDEA10/LIT30）；同包按题资源（≤整包）；collection配额按任务公布。配额违规计分规则待用户 |
| T05 | **工具/环境预检**：按包声明真实读写、CPU、检索、渲染、模型视觉等能力；executor补图片回看，judge也接收真实像素；跨任务统一工具接口而非相同依赖。 | T00、T01、T04；真实读→写→运行、生成→回看、检索→原文；缺工具归平台，工具正常但agent不用归agent。 | 文献三工具、锚点、看图工具与cpu.run签名写入平台契约（v6.1–v8）并经平台lint检查；超大图tile；工具超时只停命令 |
| T06 | **失败分类与入账**：材料、平台/transport、judge、agent失败/部分完成、正常负结果分离；保留阶段/证据/状态/资源。非agent错误不自动零分，agent失败不静默丢样本。 | T04–T05；故障注入及轨迹审核。归因不明标待审；重试幂等但每次真实调用计费。正式分母与故障聚合在T14冻结。 | typed broker错误（接口v4）、provider拒绝/429分类、公开失败摘要（含H0 stop_reason）；工厂失败留存`.failed-N`。正式分母/故障聚合规则仍待T14 |
| T07 | **角色/阶段/split隔离**：包/任务白名单、H0零科研任务、evolver仅search、同篇同split、每题状态清空；judge私有轨迹不发布，feedback只引用公开证据。 | T00；静态导出检查+真实越界/网络/状态/私有canary测试。root可先做导出和发布代码；容器实测未通过不声称OS隔离完成。 | Claude judge/builder启动即移除宿主工具；构造会话无shell、限cwd；公开面泄漏另经独立审计与（v8）盲推关卡。OS级隔离未验证（Windows提权sandbox或独立Linux待用户） |
| T08 | **LIT-R2全局库**：强相关/背景/真实近邻去重；只索引允许背景原文，去掉定向digest及IDEA措辞；search/snippet/read统一cutoff/版本/目标排除，最早公开核查。 | 离线构造可先做；服务运行验收依T00/T07。跨包发现、拒绝未来/目标/跨split答案、原文保真/覆盖/近邻难度审核。8篇仅开发种子，不冒称正式覆盖。 | 共享库v5（271篇，版本日期过滤+目标排除，§3.1）；v7/v8背景未并库；**冻结版本见T17** |
| T09 | **LIT分层与检索指标**：按任务私有标签核心/背景/混淆，分别记录返回/阅读/采用，身份版本去重；合理引用近邻与名单外有效支持不罚。 | T08；机械匹配与语义核查对齐。公式/权重/是否进主分待pilot及确认，不擅改四维。 | 检索三阶段诊断已实现（SSA开发例）；工厂LIT题的私有覆盖要点由构造写入私有rubric；指标公式/是否进主分待定 |
| T10 | **统一材料模板与审核**：按篇规范化原始材料再派生阶段任务；事实/维护者限定/缺失/结论分开，关键公式假设与原文对应；补稳定ID、表格冲突记录、无目标实现的可运行起点、包级环境资源配置。 | 可与T00/T02并行离线；实际准入需环境与语义审核。独立上下文审核原文而非自评摘要；材料不足只淘汰相应模块，保留覆盖矩阵。 | 标准工厂流水线v5–v8已实际运行：25篇、84道有效编译题；v7公开面规则R1–R5与平台lint；v8为LIT/IDEA分离公开面构造+盲推泄漏关卡（试点4/4通过，§0.2.23）；v8.1背景筛选、v8.2审阅意见转框架作者（§0.2.24） |
| T11 | **低消耗模型并行构造**：每篇独立workspace，原生Codex构造→程序检查→独立审核→返修/淘汰；限并发、重试退避、幂等、断点续跑。 | T01/T10完成后小批试产，包的运行门依T00；T03相关judge验收前不批量正式入库。模型/并发/规模依据每份合格材料成本和返修质量选，不用尽额度为目标。 | Claude原生构造批量运行（夜间监督进程达成25篇，2026-10-06）；v7首轮不靠维护即编译84%（v6 50%），每编译题约6.2次单元调用（v6 8.9） |
| T12 | **H0修复**：公开ABI干净构建环境内核读写/CPU工具，再用gpt-5.6-sol/medium构建单一harness；不看search，不用手写baseline顶替。 | T01/T05/T07；实际harness+manifest+接口测试，H0版本hash冻结。可先做构建smoke，不必等完整数据池。 | 冻结H0 v3（`h0-claude-frozen-v3`，sha 619dc724…，接口v4下development_admissible）；P11复盘新增缺陷（4条观察窗口、写回执不含内容等）记为H0属性不改 |
| T13 | **冻结版本CPU集成复验**：一个冻结harness独立运行五类修复后任务，与原生judge配套；每题包级容器环境和资源。 | T00–T08/T10/T12相关门；T03进行中可用明确标注dev baseline辅助，正式builder结论必须用H0。逐轨迹审核，旧run不混算。 | P11：39道题统一条件（Sonnet4.6/low+judge v3.6）均分约2.3（WC3.2/IDEA2.7/WE2.1/LIT1.8/EXP1.6，单次运行），开发证据非正式分；撤回题的旧分作废 |
| T14 | **数据冻结与正式主评测**：完整合格池后按源论文划split，冻结样本量/内层配置/轮次/重复/异常与统计规则；H0、builder选版、test-oracle三版本与完整曲线/成本。 | T03/T09–T13及真实覆盖；正式配置须给用户确认，不用旧TB20/50或开发2篇充数，不在test上调judge/材料再称隐藏。 | search set v1论文名单已冻结（25篇）；题目清单、文献库版本、test set及正式轮数/重复未定——拆分为T15–T19 |
| T15 | **search set v1题目清单冻结**：补齐LIT/IDEA后冻结题目ID、发布包hash、预算/资源、文献库版本（T17）、judge版本、executor配置、H0 hash。 | T16、T17完成；v6的15道存疑题有结论（已由统一审计S2覆盖）；撤回EXP（5qg6JPSgCj）维护返修（已完成）；S3统一重编译；每道新题试跑一次（可解、预算够）。 | 论文名单已冻结（`audit/search_set_v1_membership.json`）；题目清单未冻结。按统一标准S1–S5清理中：统一审计71道55过16小修，B返修9过3撤，5qg6 EXP已修复（§0.2.24）；名单现为v1.2（22篇，88道已编译，§0.2.25） |
| T16 | **factory-v8 LIT/IDEA重建**：不见论文的公开面构造+锁定+盲推/泄漏判定关卡（§0.2.23）。 | 试点4单元→独立泄漏审计与v7对比→通过则重建其余约17道撤回/放弃的LIT/IDEA；未通过则先改流程。 | 试点4/4编译且独立审计4/4可接受（42次调用）。背景中性化=v8.1 bg_screen；v8.1/v8.2重建已结束；v8.3修OpenReview公开日、v8.4改IDEA判据，Xo0Q/v1B4 IDEA经重判编译；search set v1.2剩8道旧版LIT/IDEA待A2（§0.2.24–0.2.25） |
| T17 | **文献库版本冻结**：同一评测集合内所有harness版本共用一个冻结库；并入v7/v8论文背景后为search set构建并冻结，test set另建并冻结。 | T16完成后构建；报告每题可见文献数与相关/干扰比例。 | 未开始（原则已定，用户2026-10-06） |
| T18 | **第一轮演化**：演化适配器接工厂题目注册表与公开feedback发布；H0在完整search set评测→一轮反馈修改→冻结→完整重评。 | T15冻结；用户另授额度（单轮完整评测约1,200–1,500次调用）；轮数R/重复在本轮后定。 | 适配器仅软件测试（§0.2.6）；未运行 |
| T19 | **test set构建与冻结**：另选不同源论文，v8流程构建、审计、冻结库；H0…HR隐藏评测，报告H0/H_builder/H_test-best与成本曲线。 | T16验证通过的流程；规模由用户定。 | 未开始 |

### 12.2 依赖与并行安排

```text
环境线：T00 + T01 → T04/T05/T06/T07 → T12
Judge线：T01/T07最低可用 → T02 → T03（需真实工具与证据）
材料线：T08 + T10离线并行 → T09 + T11小批试产
汇合：环境/材料/judge就绪 + H0 → T13 → 合格材料扩展 → T14
当前（2026-10-12晚）：Poster→Oral替换（v8.4根）与A2 → S3统一重编译 → T17（冻结search库）→ T15（冻结search题目清单）→ T18（第一轮演化，需额度）；T19（test set）可在T16验证后并行构建
```

不是每项都严格串行：prompt/schema/静态测试/语料整理可先做；真实运行、发布/入库和正式排名不得跳过依赖。H0构建与离线judge开发不必等完整材料池，但正式混合演化必须等全池冻结。

| 协作者 | 主责任与文件范围 | 边界 |
|---|---|---|
| root | AGENTS、依赖/额度、包级隔离/发布与集成、验收及T14配置 | 唯一修改本文；最终检查agent声明与实际证据 |
| runtime_repairs | T01/T04/T05/T06/T12；provider/costs/sdk/CPU runner/原生Codex调用及对应测试 | 与root协作T00；不能把宿主Full access当隔离，不能自行追加模型预算 |
| native_judge | T02/T03；原生judge、分模块模板/锚点、校准fixtures及测试 | 不改runtime/materials；同次双产物、实际轨迹审核 |
| material_pipeline | T08/T09/T10/T11；R2、版本化材料、生成/审核模板与队列 | 不改原始缓存/旧run；每包环境配置纳入构造产物 |

上表为Codex时期的协作分工（历史）。当前做法：root（主Claude Code会话）维护本文、调度与验收；有界子任务交独立subagent（如泄漏审计、逐轨迹审阅、离线实现复核），只读或限定文件所有权，结果写结构化审计文件；git提交走git管理会话。不默认增加无限评审，subagent报告不等于用户批准。

### 12.3 暂不阻塞开发、但进入对应阶段前须明确

- **运行宿主：** 本机Docker Desktop/WSL2可用并已用于全部材料包runtime门与P11；正式规模是否迁移服务器、OS级隔离环境（Windows提权sandbox或独立Linux）待用户。不擅自安装/启用系统服务、虚拟化或收费云资源。
- **构造模型及批量规模：** 已定为Claude原生构造/审阅/裁定（opus-5-5/medium）经标准工厂；search set规模25篇已定，test set规模待用户。GPT-6 Luna等低价构造候选为历史调研，不再采用。
- **正式设置：** 演化轮数R、重复次数、故障汇总与正式分母、LIT检索指标权重、配额违规计分规则在第一轮演化后与用户确认；executor已定（§0.2.23）。不提前拍统一时间档位。

### 12.4 后续而非首版前置

GPU任务扩展；TTS及改进来源归因/跨executor敏感性；独立连续idea-to-paper use case；发布资产权利审核、开源与复现；论文新颖性对照及统计论证。保留数据/版本/成本，不能因后续未做就宣称相关结论已证实，也不让这些项目阻塞CPU首版工程。

## 13. 复核与运行注意

- 通用离线测试：`D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe -X utf8 -m unittest discover -s research/benchmark/tests -p 'test_*.py' -v`；默认宿主Python缺pypdf，不混用环境。
- 来源测试：`python -X utf8 -m unittest discover -s research/aiml -p 'test_*.py' -v`。
- 可用bundled Python：`C:/Users/li_ha/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`，含已有NumPy/PDF开发依赖；不等于宿主默认Python已具备依赖。今后真实任务以包内Docker环境为准。
- 历史已测Codex：`C:/Users/li_ha/AppData/Local/OpenAI/Codex/bin/d375f7df50d3b421/codex.exe`，当时0.155.0-alpha.16；PATH旧0.130.0失败。后续实际版本重新记录，不写死“当前最新”。不复制认证密钥。
- 任何新运行使用新audit目录，参数/输入/输出hash与账本绑定；历史失败、注错来源与真实solver错误区分。运行前核模型额度授权和goal/用户暂停状态。
- 新schema/单测通过只表示软件验证；容器运行、材料语义、judge轨迹及正式集合分别验收。工具看到某路径不等于模型读到文件/图片。
- 工厂驱动（D盘`factory-v5-driver`）需`PYTHONPATH=<repo>/research/benchmark;D:/mrhbench-local-pilot/factory-v5-driver`；v8系离线测试：`python -X utf8 -m unittest tests_v8.test_factory_v8 tests_v8.test_factory_v8_1 tests_v8.test_factory_v8_2`（在驱动目录，39项）。工厂运行：`factory_v8_2.py run --root <root> --papers <ids> [--units LIT] --stages <...> --max-calls N`；新根用`init --root --from-root`，沿用旧根论文级材料用`carry`。
- 工厂根冻结提示词快照：改提示词必须新建根（v5→v6→v7→v8→v8_1→v8_2；v8.2只改控制器也另建根以便追溯）；维护返修用`maintenance_repair_v6.py`（`MRH_FACTORY_ROOT`指定根，v7根自动加载v7组件），按审计意见返修用`audit_repair_v1.py`（429后`--resume`）。正在运行的子进程不会加载修改后的驱动代码，修bug后已启动的进程要等其结束再重置受影响单元。
- Codex二进制与bundled Python条目为历史环境；当前所有模型角色经Claude CLI（`config/role_transport_claude_v2.json`）与faithful反代（`start_executor_wrapper.py`，127.0.0.1:8765）。

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




