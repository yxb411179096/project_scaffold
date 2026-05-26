# CHANGELOG

## 0.22.0
- 新增知识库治理模块：新增 `/knowledge/governance`，支持资料元信息质量查看、整本教材识别、风险筛选与批量重索引入口。
- 新增资料覆盖页面：新增 `/knowledge/coverage`，按教材 / 册别 / Unit 展示 `教材 / Reading / Vocabulary / 教案 / Writing` 覆盖情况与缺失建议。
- 新增治理路由：
  - `GET /knowledge/governance`
  - `GET /knowledge/coverage`
  - `POST /knowledge/bulk-reindex`
  - `POST /knowledge/<doc_id>/mark-metadata-reviewed`
  - `POST /knowledge/<doc_id>/suggest-metadata`
  - `POST /knowledge/create-unit-placeholders`
- 新增 `services/knowledge_governance_service.py`：
  - 元信息质量评分 `evaluate_document_metadata`
  - 规则化元信息建议 `suggest_metadata`
  - 覆盖统计 `get_knowledge_coverage`
  - Unit 占位创建 `create_unit_placeholders`
  - 需重索引识别 `documents_need_reindex`
- 扩展 `knowledge_documents` 字段并保持 SQLite 兼容迁移：
  - `metadata_reviewed`
  - `metadata_quality_score`
  - `metadata_warnings`
  - `is_whole_book`
  - `suggested_*`
  - `source_unit_key`
  - `last_indexed_text_hash`
- 索引流程增强：`knowledge_index_service` 在索引成功时写入 `last_indexed_text_hash`，为“文本变化重索引”提供依据。
- 知识库列表与详情页增强：
  - 列表页增加“知识库治理 / 资料覆盖情况”入口与治理 badge（质量分、已确认、整本教材、需重索引）。
  - 详情页新增元信息质量卡片、整本教材拆分提示、重索引提示、元信息建议展示。
- 扩展教材目录映射：补全人教版必修三 Unit 1-5 主题，并保留必修一/必修二已建映射。
- 新增 `tests_round_022.py`，覆盖治理评分、整本教材识别、建议元信息、覆盖统计、占位去重、重索引识别与新页面可达性。

## 0.21.1
- 编辑页质量检查增强：新增“展开质量问题详情”，按页展示 `slide 编号 / title / severity / issue code / 建议修改方式`，便于快速定位严重问题。
- `ppt_quality_check_service.py` 为主要问题码补充修复建议（如内容过密、词汇卡过长、Summary 过空/截断、图形过密等），不再只给笼统“严重问题”提示。
- 知识库参考资料展示增强：结果卡片明确显示 `title / volume / unit / lesson_type`，当命中资料与当前任务 `volume / unit` 不一致时显示黄色提示并降权展示。
- 编辑页 `used_filters` 改为中文可读摘要（如：`高一 / 人教版 / 必修二 / Unit 3 / Reading`），不再显示 Unicode 转义 JSON。
- `knowledge_retrieval_service.py` 检索优化：
  - 保持 `textbook + volume + unit (+ lesson_type)` 优先过滤阶段；
  - `no_filters` 仍仅作为最后兜底；
  - 结果按 metadata 匹配度重排（同 volume+unit+lesson_type 优先，其次同 volume+unit）。
- `build_knowledge_query()` 对“人教版 必修二 Unit 3 Reading”自动注入核心关键词：`The Internet`、`Stronger Together`、`How We Have Been Changed by the Internet`、`Jan Tchamani`、`online community`、`digital divide`、`Reading and Thinking`。
- 新增 `tests_round_0211.py`，覆盖 Unit 3 查询词增强与质量详情字段完整性回归。

## 0.21.0
- 新增课件风格模板系统（Style Preset）：支持 `default`、`open_class`、`fresh_classroom`、`reading_focus`、`writing_focus`、`grammar_focus` 六套风格。
- 新增 `services/ppt_style_service.py`，统一管理风格配置、显示名称和按课型/生成风格的默认推荐逻辑。
- 新建课件 `/ppt/new` 与文案转 PPT `/ppt/from-manuscript` 页面新增 `ppt_style` 选择；支持根据 `lesson_type` 自动推荐风格，用户可手动覆盖。
- 数据库 `lesson_tasks` 新增 `ppt_style` 字段（SQLite 兼容迁移），旧任务为空时按规则自动回退默认风格。
- `ppt_render_service.py` 渲染接入风格预设：按任务或页面 `ppt_style` 读取视觉皮肤，不改变 `layout_template` 与 `visual_variant` 页面结构逻辑。
- `ppt_style_config.py` 改为兼容层，基于新风格服务输出渲染器所需颜色与字体配置。
- 编辑页新增“当前课件风格”显示；预览卡片支持 `style-*` 类名，体现不同风格的基础视觉差异。
- `ppt_quality_check_service.py` 增加风格信息检查：`style_missing`、`style_not_matching_lesson_type`，并在质量报告中返回 `style_applied`。
- 新增 `tests_round_021.py`，覆盖风格服务、默认推荐、旧任务回退、模板渲染接收风格、页面字段存在性等回归。

## 0.20.1
- 修复 0.20.0 后模板页视觉过于单一的问题：`layout_template` 新增 `visual_variant` 并在模板渲染入口按变体分发，恢复目标卡、问题卡、流程卡、词汇卡、讨论面板、总结卡、作业分层、板书结构等差异化页面。
- `ppt_render_service.py` 新增模板变体渲染分发表（`TEMPLATE_VARIANT_RENDERERS`）及对应渲染函数，模板渲染成功后直接结束，不再继续普通 body 渲染，避免“模板主体 + 普通主体”叠加。
- 保留模板系统的规则化约束（字号、信息块上限、溢出下沉到 teacher script），在不回退到 0.19 叠加问题的前提下恢复课件视觉层次。
- `ppt_quality_check_service.py` 增强模板差异化检查：新增 `template_visual_variant_missing`、`template_rendered_as_plain_bullets`、`slide_type_visual_repetition`、`summary_too_plain`、`vocabulary_not_card_like`。
- 新增 `tests_round_0201.py`，覆盖主要模板 `visual_variant` 映射、模板渲染分发、模板成功渲染不走 plain fallback、旧模板回退兼容路径。

## 0.17.0
- 优化 PPTX 多页面视觉布局与教学页面可用性，强化封面、目标、阅读任务、讨论、总结、作业、板书等页面的差异化呈现。
- `ppt_render_service.py` 强化 Reading 任务卡、词汇卡、讨论任务卡、作业清单等默认文案，移除空泛占位句（如 `Complete the classroom task.` / 空 `Step 1/2/3`）。
- `slide_content_agent.py` 增加输出约束：禁止空泛任务占位，要求 Reading / Writing / Grammar 分别输出更具体的课堂任务内容。
- `mock_ai_service.py` 规则兜底内容升级：减少空泛步骤句，改为可执行的课堂任务描述。
- 新增 `services/ppt_quality_check_service.py`，提供轻量级 PPT 质量检查（标题/内容长度/空页/占位句/课型结构覆盖/视觉风险提示）。
- 编辑页新增“PPT质量检查”区域：显示总体状态、问题数量、按页问题与导出前风险提示（仅提示，不阻止导出）。
- 网页预览样式增强：新增 `reading-task-preview`、`discussion-preview`、`writing-preview`、`summary-preview` 等视觉类，提升页面层级区分度。
- 新增 `tests_round_017.py`，覆盖：空泛句识别、Reading/Writing/Grammar 兜底结构、布局函数差异化映射等回归。

## 0.16.0
- 进行 Ollama/Qwen 稳定性专项优化，重点降低 `Model returned an empty response` 对主流程影响，保留 fallback_rule 作为兜底。
- `services/llm_service.py` 增强失败调试信息与 trace 字段：记录 `endpoint`、`prompt_length`、`prompt_preview`、`timeout`、`temperature`、`num_predict`、`response_length`、`raw_response_keys`、`retry_count`、`raw_empty`、`json_extract_failed`、`first_attempt_failed`、`retry_attempted`、`retry_success`。
- 增强 JSON 提取能力：支持纯 JSON、数组、```json 代码块、前后带说明文字的 JSON，并优先提取第一个合法对象/数组。
- 增强重试策略：首轮空响应或 JSON 失败自动 retry 一次；retry 使用更短 prompt，知识库上下文进一步压缩，失败后再走 fallback_rule。
- 新增 `trim_knowledge_context_for_prompt(context, max_chars=4000)`，默认控制知识库上下文长度；prompt 过长时自动压缩，retry 阶段进一步压到约 1500 字。
- Qwen 系列请求参数统一优化：`stream=false`、`top_p=0.9`、`repeat_penalty=1.05`，并按 Agent 应用 `num_predict` 下限（如 `slide_content_agent>=6000`）。
- 新增模型配置中心“测试 JSON 生成”按钮与接口 `/settings/ai-models/<id>/test-json`，可快速验证模型是否能稳定返回可解析 JSON。
- 优化 8 个核心 Agent 的 knowledge_context 注入长度控制，避免 prompt 过大导致空响应，且不影响原有 fallback 逻辑。
- 新增 `tests_round_016.py`，覆盖 Qwen JSON 指令、token 下限、context 截断、空响应 retry、JSON 提取兼容、模型 JSON 测试接口等回归。

## 0.15.5
- 新增 `services/textbook_catalog_service.py`，引入基础教材目录映射并优先覆盖人教版必修册别单元元信息；已内置：
  - 必修二 Unit 1 Cultural Heritage
  - 必修二 Unit 2 Wildlife Protection
  - 必修二 Unit 3 The Internet
  - 必修二 Unit 4 History and Traditions
  - 必修二 Unit 5 Music
- 对 `人教版 + 必修二 + Unit 3 + Reading` 增加明确映射：
  - `topic=The Internet`
  - `reading_title=Stronger Together: How We Have Been Changed by the Internet`
  - `reading_skill=Read headlines`
- `requirement_parser_agent` 增加 `volume` 字段并接入教材目录增强，避免 Unit 3 默认错配到必修一的 `Sports and Fitness`。
- 新建课件与文案转 PPT 路由新增 `volume` 入库与表单项，创建任务时会基于教材目录生成规范课题标题，用于导出文件名和后续流程一致化。
- 知识库检索 `build_knowledge_query()` 优化：当目录命中时优先注入 `reading_title`、主题关键词（如 `online community / internet / digital life / reading headlines`）和册别信息。
- 知识库过滤放宽顺序调整为：
  - `textbook + volume + unit + lesson_type`
  - `textbook + volume + unit`
  - `textbook + volume`
  - `textbook only`
  - `no_filters`（最后兜底）
- 编辑页知识库参考命中仍保留 `volume / unit` 展示，便于快速识别误命中册别与单元。
- 更新 `tests_round_015.py`：新增必修一/必修二 Unit 3 映射断言、`Stronger Together` 断言、检索 query 断言，以及“必修二 Unit 3 不应生成 Sports and Fitness”回归检查。

## 0.15.4
- 修复编辑页知识库参考资料中的“查看原资料”按钮 endpoint 错误，`knowledge.detail` 已改为真实存在的 `knowledge.knowledge_detail`，避免 `/ppt/task/<id>/edit` 再次触发 500。

## 0.15.3
- 修复新建课件后跳转编辑页时的 500 错误，`relaxed_level` 现在兼容字符串与旧数字格式，不再强制 `int()` 转换。
- 编辑页知识库参考资料区域现在直接显示 `relaxed_level_label`，可正确展示“精确匹配 / 已放宽单元 / 已放宽册别 / 仅按课型匹配 / 无筛选语义检索 / 未知”。
- 补充 `relaxed_level` 兼容回归测试，覆盖 `no_filters`、旧数字值与 `None` 三种情况。

## 0.15.2
- 修复 ChromaDB `where` 条件构造在单条件或单候选值时误包裹 `$and` / `$or` 的问题，避免出现 `Expected where value for $and or $or to be a list with at least two where expressions`。
- 优化知识库检索放宽策略，支持从完整过滤逐级降级到无 filters 搜索，并在编辑页展示 `relaxed_level` 与 `used_filters`，便于判断命中是否来自放宽检索。
- 增强 `qwen3:30b` 的空响应兜底逻辑：首次空响应自动 retry，一并提高本地推理的默认 timeout / `num_predict` / 低温参数，减少 Agent 回退到 rule 的概率。
- 更新默认 Agent 参数建议，提升 `lesson_design_agent`、`ppt_outline_agent`、`slide_content_agent`、`language_polish_agent` 等在本地 Ollama 下的稳定性。

## 0.15.1
- 优化知识库检索的放宽逻辑，`Unit 4` / `unit4` / `Unit4` 与 `Reading` / `reading` 等值会尽量标准化并兼容匹配。
- 知识库语义检索现在按多级策略逐步放宽筛选条件，支持从完整过滤回退到仅按语义查询，编辑页可查看 `used_filters` 和 `relaxed_level`。
- 优化 RAG 检索 query 构造，优先生成更自然的检索语句，提升命中率。
- 增加 Ollama 空响应 retry 机制，qwen3:30b 首次返回空内容时会自动重试一次，并增强 JSON 提取容错。
- 默认将 qwen3 相关 Agent 的超时建议提升到更适合本地推理的范围，减少空响应和超时 fallback。

## 0.15.0
- 新增知识库增强生成开关，支持在新建课件和文案转 PPT 时选择是否启用 RAG。
- 新增 `services/knowledge_retrieval_service.py`，用于构造知识库查询、metadata 筛选、语义检索与 prompt 格式化。
- 新建课件和文案转 PPT 现在可以把知识库检索结果作为参考资料注入 Agent，但不会破坏原有普通生成路径。
- 支持在 `lesson_tasks` 中保存 `use_knowledge_base`、`knowledge_query`、`knowledge_top_k`、`knowledge_context_json`，便于编辑页回看与复现。
- Agent prompt 已支持 `knowledge_context`，知识库检索失败时自动 fallback 到普通生成，不会影响课件生成结果。
- 编辑页新增“知识库参考资料”区域，可查看检索状态、命中资料、相似度与原资料跳转。

## 0.14.1
- 修复语义搜索结果显示“未命名资料”的问题，搜索结果现在会根据 `document_id` 反查 `KnowledgeDocument` 补齐标题和元信息。
- ChromaDB 向量 metadata 现在完整写入 `document_id`、`title`、`doc_type`、`grade`、`textbook`、`volume`、`unit`、`lesson_type`、`tags`、`chunk_index`，旧索引也能在搜索页回填标题。
- 优化知识库列表页表格布局，合并资料信息、解析信息与索引状态列，避免文字在窄列中被挤成竖排。
- 优化语义搜索结果卡片展示，资料标题、元信息、Distance / Score 与原资料跳转更清晰。

## 0.14.0
- 新增知识库文本切块、KnowledgeChunk 模型、Ollama embedding 服务与 ChromaDB 向量存储服务，知识库从资料管理升级为可语义检索的知识库。
- 新增知识库索引、重新索引与删除索引流程，向量数据持久化到本地 `CHROMA_PERSIST_DIR`，SQLite 同步保存 chunk 元信息便于调试与查看。
- 新增 `/knowledge/search-semantic` 语义检索页面，支持 query、Top K 和 metadata 筛选，展示相似 chunk、来源资料与距离/得分。
- 知识资料删除与重新解析流程已联动清理向量索引和 chunk 元信息，但课件生成流程暂未接入知识库。

## 0.13.1
- 完成本机 Mac Pro 环境适配检查：确认项目可在本地 Ollama `http://127.0.0.1:11434` 下运行，并将默认模型对齐为 `qwen3:30b`。
- `config.py` 与 `services/llm_service.py` 的 Ollama 默认模型回退值已从 `qwen2.5:7b` 调整为 `qwen3:30b`，避免新环境在没有 `.env` 时误落到旧默认。
- `models/database.py` 新增轻量启动迁移：当数据库里没有默认模型、且仅存在一个可用 Ollama 配置时，会自动将其提升为默认模型，确保本地运行优先使用已验证的 `qwen3:30b`。
- 模型配置页占位提示同步更新为 `qwen3:30b`，便于后续新增或编辑模型时保持一致。

## 0.13.0
- 新增教学资料知识库模块，提供资料上传、文本录入、解析、检索、详情查看、重解析、下载与删除能力，首版只做资料管理，不接入向量库与 RAG。
- 新增 `KnowledgeDocument` 数据结构（`knowledge_documents` 表）及 SQLite 兼容迁移，包含标题、类型、学段教材元信息、来源、文件路径、解析文本、摘要、字数、状态、错误信息等字段。
- 预留后续向量化字段：`embedding_status`、`chunk_count`、`vector_collection`，默认分别为 `not_indexed`、`0`、空字符串。
- 新增 `routes/knowledge_routes.py` Blueprint 与路由：
  - `GET /knowledge`
  - `GET /knowledge/new`
  - `POST /knowledge/new`
  - `GET /knowledge/<id>`
  - `POST /knowledge/<id>/delete`
  - `POST /knowledge/<id>/reparse`
  - `GET /knowledge/<id>/download`
  - `GET /knowledge/<id>/text`
- 新增页面模板：
  - `templates/knowledge_list.html`
  - `templates/knowledge_new.html`
  - `templates/knowledge_detail.html`
  - `templates/knowledge_text.html`
- 顶部导航新增“知识库”入口，已注册知识库 Blueprint 到应用启动流程。
- 扩展 `services/document_parse_service.py`，支持 `txt / md / docx / pdf` 解析、文本清洗、字数统计、规则摘要生成与解析文本文件落盘；PDF 无文本时会明确提示“当前版本暂不支持 OCR”。
- 新增知识库目录：`uploads/knowledge/`（原始文件）与 `uploads/knowledge_text/`（解析文本）；删除资料时会尝试清理关联文件，失败不致崩溃。
- 新增关键词检索与多条件筛选（SQL LIKE，范围包含 `title/tags/summary/parsed_text`），列表按创建时间倒序，状态 badge 区分 `parsed/failed/pending`。
- 新增回归测试脚本 `tests_round_013.py`，覆盖知识库建表、文本创建、解析摘要、字数统计、列表查询、重解析、纯文本查看、删除及旧页面可用性检查。

## 0.12.1
- 修复保真模式 `Learning Objectives` 编号解析问题：`original_page_parser_agent` 现在会将孤立编号（如 `1.`、`2.`）与后续目标句自动绑定，避免把纯编号写入 `visible_content`。
- 优化 `content_compressor_agent`：新增孤立编号过滤；在 `preserve_original_pages` 下优先保留原文表达，减少任务标签式过度改写。
- 优化 `ppt_render_service.py` 的 `objectives_layout`：目标卡片会跳过空内容或仅编号内容，避免导出页出现 `Objective X: 1.` 这类孤立文本。
- 新增 `tests_round_0121.py` 回归脚本，校验 Learning Objectives 至少保留 3 条完整目标句且不出现孤立编号。

## 0.12.0
- 优化保真模式 `preserve_original_pages` 的渲染与性能策略：页结构检测、原页解析、内容压缩默认走本地规则链路，不再强制调用模型；`page_structure_detector_agent` 与 `original_page_parser_agent` 的默认绑定已收敛为 `rule_only`，保真模式生成耗时显著降低。
- `lesson_tasks` 新增兼容迁移字段：`manuscript_preserve_completion_mode`、`manuscript_preserve_polish_mode`，分别控制“仅按原文页数生成 / 自动补充 Summary、Homework、Blackboard Design”和“跳过英文润色 / 按 Agent 策略执行润色”。
- `/ppt/from-manuscript` 页面新增“保真补全模式”和“保真模式英文润色”选项；默认保真补全为“仅按原文页数生成”，默认英文润色为“跳过，保留原文表述”。
- `services/manuscript_pipeline_service.py` 调整 preserve 流程：保真模式下按原文页顺序解析并保留标题，不擅自重构课堂流程；若选择自动补全，则在原文页之后追加 `Summary`、`Homework`、`Blackboard Design` 三页。
- `slide JSON` 新增视觉字段继续贯通 `PPTX / DOCX / 编辑页预览`：`image_suggestion`、`key_sentence`、`useful_expressions`、`possible_answers`、`chinese_hint` 已根据保真模式进行更明显的版式渲染。
- `layout_planner_agent.py` 新增保真专项版式规划：`preserve_cover_layout`、`leadin_question_layout`、`prediction_flow_layout`、`warmup_card_layout`；封面、目标、导入、热身、读前预测等页面在 preserve 模式下会自动切换到更接近正式高中英语课件的结构。
- `ppt_render_service.py` 强化 preserve 模式视觉层级：
  - 封面页支持大标题 + 次级信息 + 大图片占位框
  - 学习目标页维持目标卡片结构
  - 导入页支持多问题 Question Cards
  - 预测页支持 `Before reading → Predict → Share` 任务流
  - Key Sentence / Possible Answers / Useful Expressions 会以句子卡、答案标签、表达支架卡片等形式显示
  - `image_suggestion` 始终优先渲染为图片占位框，而不是普通文本
- `edit_task.html` 与 `style.css` 优化网页预览：新增 `cover-preview`、`objectives-preview`、`leadin-preview`、`warmup-preview`、`prereading-preview` 等样式，学生可见内容与教师信息继续分区展示，图片建议、重点句、表达支架和答案标签的视觉层级更明显。
- 完成第十二轮验证：`python -m compileall app.py routes models services` 通过；数据库绑定迁移生效；Flask `test_client` 回归覆盖 AI 自动生成、保真模式 5 页原文生成、保真自动补全生成、普通 `ai_restructure` 生成、编辑页预览、PPTX 导出、DOCX 导出；“The Power of Reading” 文案在 preserve 模式下可保持 5 页原结构，开启自动补全后可扩展到至少 8 页，PPTX 兼容性保持正常。

## 0.11.0
- 新增 manuscript 生成模式 `manuscript_generation_strategy`，支持“严格按原文页结构生成”与“AI 优化重构生成”；`/ppt/from-manuscript` 页面新增模式选择，并在检测到 `第1页 / Page 1 / Slide 1 / 幻灯片1 / 一、封面` 等结构时自动默认保真模式。
- `lesson_tasks` 新增 `manuscript_generation_strategy` 兼容迁移字段，保留旧数据并让 manuscript 任务在后续重生成、重新分析和导出时继续沿用原策略。
- 新增 [services/agents/page_structure_detector_agent.py](/Volumes/DevSSD/Projects/project_scaffold/services/agents/page_structure_detector_agent.py)，用于检测原文是否已包含明确页结构，并输出 `has_page_structure`、`page_count_detected`、`detected_page_markers`、`recommended_strategy`。
- 新增 [services/agents/original_page_parser_agent.py](/Volumes/DevSSD/Projects/project_scaffold/services/agents/original_page_parser_agent.py)，在 `preserve_original_pages` 模式下按原文页码拆页，尽量保留原页标题、Teacher’s Guide、Key Sentence、Useful Expressions、Possible Answers、图片建议和中文提示。
- `services/manuscript_pipeline_service.py` 改为双分流：
  - `preserve_original_pages`：页结构检测 -> 原页解析 -> 内容压缩 -> 语言润色 -> 布局规划 -> schema 校验
  - `ai_restructure`：继续走原有 manuscript 分析 -> 教学结构提取 -> 拆页 -> 压缩 -> 润色 -> 活动审查 -> 布局规划 -> schema 校验
- slide JSON 新增可选字段：`image_suggestion`、`key_sentence`、`useful_expressions`、`possible_answers`、`chinese_hint`；这些字段已贯通 schema、编辑保存、单页重生成、JSON 预览、PPTX 导出和 DOCX 授课稿导出。
- `layout_planner_agent.py` 与 `ppt_render_service.py` 增强保真模式页面版式：`image_suggestion` 可驱动图片占位框，`key_sentence` 可驱动句子重点卡片，`useful_expressions` 可驱动表达卡片，`possible_answers` 可进入对比列或任务答案区，`chinese_hint` 以弱化提示显示。
- 编辑页预览重构：学生可见区域优先展示 `title / visible_content / key_sentence / useful_expressions / image_suggestion / possible_answers`，教师相关 `Purpose / Interaction / Notes` 收纳到“教师信息”区域，降低页面主体噪音。
- manuscript 任务新增“重新分析文案并生成课件”后，若仍选择保真模式，会继续按原文页结构重跑，不会退化成课型模板页。
- 完成第十一轮验证：`python -m compileall app.py routes models services` 通过；Flask `test_client` 回归覆盖 AI 自动生成、保真模式 manuscript 生成、普通重构模式 manuscript 生成、编辑页预览、PPTX 导出、DOCX 导出；“The Power of Reading” 测试文案在保真模式下前 5 页与原文页结构对齐，第 4 页 Key Sentence、图片建议、Teacher’s Guide 与 Useful Expressions 均被保留。

## 0.20.0
- 新增 PPT 设计规范文档体系（skills）：`ppt_design_rules.md`、`senior_english_slide_rules.md`、`slide_density_rules.md`、`reading_lesson_layout_rules.md`，统一页面信息密度、字号下限和教学页展示边界。
- 新增 `services/layout_template_service.py`，建立布局模板注册表，提供模板参数（`max_blocks`、`max_items_per_block`、`title/body/label/min font`、`overflow_strategy`、`use_graphic` 等）与 slide_type 映射。
- `layout_planner_agent.py` 增强：在 `layout_plan` 中新增 `layout_template` 输出，形成“布局类型 + 模板约束 + 图形策略”三层规划。
- `ppt_render_service.py` 新增 `render_by_layout_template(...)` 通用模板渲染入口，模板优先；当模板存在时优先执行模板规则，不足内容自动提示 `More details in teacher script.` 并下沉到 teacher script。
- `ppt_quality_check_service.py` 接入模板规则校验：检测模板溢出、模板最小字号过低、`big label / small body` 风险，和既有质量检查合并输出。
- 新增 `tests_round_020.py`，覆盖模板选择、summary/vocabulary约束、最小字号阈值、旧任务兼容导出、质量检查模板风险识别。

## 0.19.3
- 简化图形组件显示策略，优先保证可读性：PPT 主体遵循“少量核心信息”原则，超过容量的细节统一下沉到 teacher script / DOCX。
- Reading 课图形分配收敛：默认仅 `careful_reading -> reading_structure`、`vocabulary_focus -> vocabulary_cards`、`summary -> mindmap`；`lead_in/prediction/fast_reading/homework/group_discussion/language_points` 默认不强制图形化。
- 新增安全渲染降级 `safe_compact_layout(...)`：当图形节点过多或文本过密时自动改为标题 + 3 条核心要点 + 可选 key sentence，避免字体继续缩小和页面拥挤。
- 优化图形组件密度与信息块上限：discussion、grammar、vocabulary、mindmap、task_steps、reading_structure 均减少显示块数量，并增加 “More details in teacher script.” 提示。
- 修复词汇卡占位问题：优先输出自然词汇（如 `online community`、`social network`、`digital life`），避免 `Item 1/2/3` 占位词进入 PPT 主体。
- 强化质量检查：`font_too_small_risk`、`graphic_too_dense`、`hard_truncation_risk` 升级为更高风险级别，并新增 `item_placeholder_risk`、`summary_hard_truncated` 提示，建议使用安全模式渲染或减少主体内容。
- 新增 `tests_round_0193.py`，覆盖 discussion 简化输出、词汇占位防回归、summary 非硬截断、dense 图形触发安全渲染、Reading 图形默认分配与旧任务导出兼容。

## 0.19.2
- 优化图形组件字体策略：新增统一字体常量（`GRAPHIC_TITLE_FONT`、`GRAPHIC_CARD_TITLE_FONT`、`GRAPHIC_BODY_FONT`、`GRAPHIC_SMALL_FONT`、`GRAPHIC_MIN_FONT`），并强制正文字号不低于 9，避免页面出现过小字体。
- 新增 `smart_clip(text, max_chars, preserve_words=True)`，英文优先按单词截断，减少 `main classr...` 这类半词硬截断。
- 收敛图形内容密度：词汇卡最多 3 张、思维导图最多 4 个分支、任务流程最多 3 步、阅读结构最多 3 块，并对长文本做语义化裁剪。
- 优化 `render_vocabulary_cards`、`render_grammar_rule_chart`、`render_discussion_grid`、`render_mindmap`、`render_task_steps`、`render_flowchart`、`render_reading_structure` 的布局与文本显示策略，过多细节提示转移到教师讲稿。
- 增强质量检查：新增/强化 `font_too_small_risk`、`hard_truncation_risk`、`graphic_too_dense`、`vocabulary_card_too_long`、`summary_too_verbose`，用于提前提示页面过密或裁剪风险。
- 新增 `tests_round_0192.py`，覆盖 `smart_clip` 半词截断保护、图形组件内容上限、最小字号约束、图形过密识别与旧任务导出兼容。

## 0.19.1
- 修复图形组件与普通主体内容重复渲染导致的页面图层叠加问题：新增 `has_active_graphic()`，当图形有效时进入图形专用渲染路径，不再重复绘制普通 bullet/body 卡片。
- `ppt_render_service.py` 增加统一图形安全区域 `GRAPHIC_AREA`，图形组件仅在该区域内绘制；标题区、页脚区和图形区互相分离，降低重叠风险。
- 图形渲染流程改为整段 `try/except` 互斥回退：图形失败时完整回退到旧布局，不出现“半图形 + 半普通内容”的混合状态。
- 当 `image_suggestion` 与图形组件同时存在时，PPT 主体优先渲染图形，图片建议降级为底部小提示，避免大面积重复占位。
- `ppt_graphics_service.py` 优化组件内部布局：统一基于传入 area 计算位置，限制卡片数量（最多 3-4），并对长文本截断，减少组件内部重叠。
- `layout_planner_agent.py` 调整 Reading 图形分配：`lead_in` 不再分配 `task_steps`，优先 `discussion_grid`；`fast_reading` 使用 `flowchart`，`careful_reading` 使用 `reading_structure`，`summary` 使用 `mindmap`。
- `ppt_quality_check_service.py` 新增 `duplicate_rendering_risk` 检查项，对“图形组件已启用但可见文本过多”给出风险提示。
- `tests_round_019.py` 更新互斥回归：验证图形模式下不调用普通 body 渲染路径、图形失败可回退、`lead_in` 不再分配 `task_steps`、`careful_reading` 继续使用 `reading_structure`、旧任务无图形字段仍可导出。

## 0.19.0
- 新增图形化教学组件系统：在 slide JSON / `layout_plan` 中支持 `graphic_type` 与 `graphic_data`，兼容旧任务与旧导出链路。
- `layout_planner_agent` 增加按课型与页面类型的规则分配：支持 `mindmap / flowchart / timeline / comparison_table / reading_structure / writing_framework / grammar_rule_chart / vocabulary_cards / task_steps / discussion_grid`，并自动补全基础图形数据。
- 新增 `services/ppt_graphics_service.py`，实现教学图形组件渲染函数，全部基于 `python-pptx` 公共 API，不操作底层 OOXML。
- `ppt_render_service.py` 接入图形组件渲染：优先读取 slide 或 layout_plan 的 graphic 配置，图形渲染失败自动回退普通布局，不阻断 PPTX 导出。
- `slide_content_agent` prompt 增强：Reading/Writing/Grammar 关键页要求输出更具体结构化教学内容，降低空泛任务表达。
- 编辑页预览增强图形提示：增加 graphic badge 与组件预览块（mindmap/flowchart/comparison/reading-structure/writing-framework/grammar-chart/vocabulary-cards 等）。
- `ppt_quality_check_service` 增加图形检查项：`graphic_type_missing`、`graphic_data_empty`、`task_steps_too_generic`、`reading_structure_missing`、`writing_framework_missing`、`grammar_rule_chart_missing`。
- 新增 `tests_round_019.py`，覆盖图形分配、图形渲染可调用性、task_steps 空泛识别、无效 graphic fallback、旧任务兼容导出等回归。

## 0.18.0
- `services/ppt_render_service.py` 统一了 PPT 设计常量（尺寸、边距、字号层级、色彩变量、页脚安全区），并逐步替换关键布局中的 magic number，提升导出版式一致性与可维护性。
- 新增文本稳态工具函数：`estimate_text_lines`、`fit_font_size`、`truncate_text`、`normalize_bullets`、`split_long_text_to_bullets`；用于标题缩放、长文截断、bullet 数量/长度约束，降低文字溢出风险。
- 强化封面、目标、阅读任务、词汇卡、讨论、总结、作业等布局函数的密度控制与回退逻辑，避免卡片拥挤和空泛文案，支持关键句突出与更稳定的任务展示。
- 图片建议渲染升级为统一图片占位框样式（`Image suggestion:`），并保持不写 notesSlides / notesMasters / 底层 XML 的兼容导出策略。
- 所有页面统一页脚信息与页码样式：左侧显示课题/Unit，右侧显示页码，视觉弱化但稳定可见。
- `services/ppt_quality_check_service.py` 增强为分级报告（`info / warning / critical`），新增 `title_too_long`、`too_many_bullets`、`bullet_too_long`、`possible_overflow`、`too_many_visual_blocks`、`image_suggestion_not_rendered`、`layout_missing`、`teacher_notes_too_short`、`page_may_be_too_dense` 等检查项。
- 编辑页新增导出前质量摘要提示（通过/有风险/严重问题）和规则说明文案；严重问题会红色提示“建议先修改”，但仍不阻止导出。
- 新增 `tests_round_018.py`，覆盖 bullet 规范化、文本截断、字号自适应、质量检查命中、超长内容渲染稳定性与 image_suggestion 渲染路径回归。

## 0.10.0
- 优化 `manuscript_analyzer_agent.py`，增强教案 / 讲稿 / 课文 / 说课稿 / 练习材料 / 综合材料识别，并新增 `detected_sections`、`missing_sections`、`content_density`、`recommended_generation_strategy`、`organization_suggestion` 等分析字段，用于后续拆页和编辑页预览。
- 优化 `lesson_structure_extractor_agent.py`，更强地识别教学目标、重点难点、导入、阅读任务、语法讲解、写作任务、课堂活动、总结、作业和板书；当原文缺环节时，会按课型自动补齐基础教学步骤。
- 优化 `slide_splitter_agent.py`，按 Reading / Grammar / Writing / Listening and Speaking / Revision 使用不同拆页策略；同时新增 manuscript 单页重生成逻辑，单页重生成会结合 `manuscript_raw_text` 与上下页上下文，而不是只走普通 AI 自动生成路径。
- 优化 `content_compressor_agent.py`，强化长文压缩策略：每页 `visible_content` 最多 5 条，长句优先转入 `teacher_notes`；阅读课更偏问题与任务，写作课更偏结构与支架，语法课更偏例句、规则与练习。
- `lesson_tasks` 新增 `manuscript_analysis_json` 兼容迁移字段，用于持久化文案分析结果，不破坏已有 SQLite 数据。
- 编辑页新增“文案分析结果预览”区域，显示文案类型、摘要、识别出的教学环节、缺失环节、建议生成策略、内容密度与原文长度；对 manuscript 任务新增“重新分析文案并生成课件”按钮。
- manuscript 任务编辑页的 trace 增强显示 manuscript 相关 Agent，并在样式上突出 `manuscript_analyzer_agent`、`lesson_structure_extractor_agent`、`slide_splitter_agent`、`content_compressor_agent` 的调用记录。
- manuscript pipeline 与编辑页重生成逻辑继续保留 fallback 机制与非空课件保护，不会创建 0 页 manuscript 任务；PPTX / DOCX 导出兼容性策略保持不变。
- 完成第十轮验证：`python -m compileall app.py routes models services` 通过；Flask `test_client` 回归覆盖首页、任务列表、AI 自动生成、文案转 PPT 页面、800 字 Reading 文案粘贴生成、docx 教案上传、短文案自动补全、单页重生成、重新分析文案并生成课件、PPTX 导出、DOCX 导出。

## 0.9.0
- 新增“文案 / 教案转 PPT”入口与页面 `/ppt/from-manuscript`，支持输入课程信息、粘贴文案、上传文档、补充要求，并在提交后直接生成可编辑课件。
- `lesson_tasks` 新增文案生成相关字段与兼容迁移：`generation_mode`、`manuscript_source_name`、`manuscript_raw_text`、`manuscript_summary`、`source_word_count`，原有数据保持不破坏。
- 新增 [services/document_parse_service.py](/Volumes/DevSSD/Projects/project_scaffold/services/document_parse_service.py)，支持 txt / md / docx / pdf 文本提取与基础清洗；PDF 在当前环境缺少 `pypdf` 时会返回明确错误，不会导致系统崩溃。
- `requirements.txt` 补充 `pypdf` 依赖，并增加 20MB 上传限制配置。
- 新增 4 个 manuscript agents：`manuscript_analyzer_agent`、`lesson_structure_extractor_agent`、`slide_splitter_agent`、`content_compressor_agent`，统一接入 Agent 策略中心，支持 `model_first` 和规则 fallback。
- 新增 [services/manuscript_pipeline_service.py](/Volumes/DevSSD/Projects/project_scaffold/services/manuscript_pipeline_service.py)，按“文案分析 -> 结构提取 -> 页面拆分 -> 内容压缩 -> 语言润色 -> 活动审查 -> 布局规划 -> schema 校验 -> 非空兜底”生成最终课件。
- `services/llm_service.py` 增加 manuscript pipeline 入口与单页重生成分流；文案任务会继续使用 trace、fallback 和空课件保护，不会生成 0 页任务。
- 编辑页、预览、JSON 查看、trace、PPTX / DOCX 导出继续兼容 manuscript 任务；错误格式文件会给出“文案解析失败，请检查文件格式或粘贴文本内容。”的明确提示。
- Agent 策略中心新增 manuscript 相关 Agent 预置绑定，并继续保留 `.env -> 数据库默认模型 -> mock / rule fallback` 的整体运行策略。
- 完成第九轮验证：`compileall` 通过；Flask `test_client` 回归覆盖首页、任务列表、AI 自动生成、文案转 PPT 页面、粘贴文案生成、txt 上传、docx 上传、pdf 错误提示、编辑页、单页重生成、PPTX 导出、DOCX 导出；文案任务 trace 中可见 manuscript Agents，短文案也能自动补齐基础教学流程且不会创建空课件。

## 0.8.1
- 修复第八轮 fallback 测试暴露的“0 页课件”问题：新增 `ensure_non_empty_slides()` 与完整 rule-based 重建链路，当 pipeline 最终返回空 slides 时会自动重建基础课件，而不是保存空任务。
- `pipeline_service.py` 新增本地 rule-only 兜底构建流程，保证在 `lesson_design_agent` 等模型型 Agent 回退规则后，后续仍能继续得到 `teaching_design`、`ppt_outline`、`slides`、`layout_plan` 和最终 `ppt_json`。
- `llm_service.py` 增加空 slides 检查；如果主 pipeline 意外返回空结果，会记录 fallback 并继续尝试本地 mock 兜底。
- `routes/ppt_routes.py` 增加整套课件重生成能力，支持在编辑页一键“重新生成整套课件”；新建课件时如果最终仍拿不到有效 slides，会删除空任务并提示明确错误，避免留下 0 页记录。
- 编辑页增加空课件恢复提示：当任务没有有效 slides 时，会显示“当前课件没有生成有效幻灯片，请重新生成课件。”并提供整套重生成按钮，不再只展示空白 JSON。
- 导出路由增加空课件保护，没有 slides 时会先提示用户重新生成整套课件，避免空课件进入 PPTX / DOCX 导出。
- 清理测试数据策略：回归测试任务统一使用 `[TEST]` 前缀或在测试结束后清理，避免 fallback 测试任务混入正常课件列表。

## 0.8.0
- 新增 `AgentModelBinding` 数据表及默认种子数据，支持为 `requirement_parser_agent`、`lesson_design_agent`、`ppt_outline_agent`、`slide_content_agent`、`language_polish_agent`、`activity_review_agent`、`layout_planner_agent`、`json_schema_checker` 配置执行模式、主模型、备用模型、超时、温度、`max_tokens`、JSON 要求和规则回退策略。
- 新增 `LLMCallLog` 数据表，按调用记录 `task_id`、`agent_name`、`provider`、`model_name`、`status`、`duration_ms`、`error_message`、`created_at`，用于追踪模型调用、规则跳过和 fallback 结果。
- `services/llm_service.py` 增加 `get_model_for_agent()` 与 `call_agent_json()`，实现“数据库 Agent 绑定优先，`.env` 运行模型兜底，mock 最后回退”的按 Agent 调用策略中心。
- `lesson_design_agent.py`、`ppt_outline_agent.py`、`slide_content_agent.py`、`language_polish_agent.py` 改为通过 Agent 策略中心调用模型；主模型失败、备用模型失败、非法 JSON、超时等情况都会自动按绑定策略回退。
- `pipeline_service.py` 为 `requirement_parser_agent`、`activity_review_agent`、`layout_planner_agent`、`json_schema_checker` 记录 rule-only 执行日志，确保这类 Agent 不调用 Ollama 时仍能在 trace 中被审计。
- 新增 `/settings/agent-bindings` 页面，可查看并编辑每个 Agent 的执行模式、主模型、备用模型、超时覆盖、temperature、max_tokens、JSON 要求、fallback_to_rule 和启用状态。
- 模型配置中心页面新增“Agent 模型绑定”入口，编辑页新增“生成 trace”区域，展示各 Agent 的 provider / model、调用状态、是否 fallback 和耗时。
- 完成第八轮验证：`compileall`、Flask `test_client` 回归、Reading 课件新建/单页重生成/PPTX/DOCX 导出通过；`rule_only` Agent 会记录规则执行且不调用 Ollama，`model_first` Agent 可调用 `qwen2.5:7b`，Ollama 不可用时可按绑定策略回退规则。

## 0.7.0
- 新增 `AIModelConfig` 数据表及访问函数，支持管理 `mock`、`ollama`、`deepseek`、`openai` 四类模型配置，并记录默认状态、启用状态与最近测试结果。
- 新增模型配置中心页面 `/settings/ai-models`，支持查看、新增、编辑、删除、设为默认、启用/禁用、测试连接。
- 模型设置页增加运行时信息展示，明确当前实际使用的来源是数据库默认模型、`.env` 回退，还是 mock 回退。
- `services/llm_service.py` 调整为优先读取数据库中 `enabled=1` 且 `is_default=1` 的模型配置；如果数据库没有可用配置，则回退 `.env`；如果 `.env` 也不可用，则回退到 mock。
- `services/llm_service.py` 新增模型连接测试能力：Ollama 会请求 `/api/tags` 验证可达性并返回模型列表；DeepSeek / OpenAI 当前保留为占位测试；API Key 展示统一脱敏。
- `routes/ppt_routes.py` 扩展模型设置相关路由与表单处理，同时保留现有课件新建、编辑、重生成、导出流程不变。
- 更新导航与样式，加入“模型设置”入口和模型配置卡片、状态标签、运行时配置摘要。
- 完成第七轮验证：`compileall` 通过，设置页 CRUD / 默认模型 / 启用禁用 / Ollama 测试连接通过；数据库默认 Ollama 配置已实际驱动 Reading 课件新建、单页重生成、PPTX 导出、DOCX 导出。

## 0.6.0
- `services/llm_service.py` 升级为统一的 LLM 服务层，支持通过 `.env` 配置 `LLM_PROVIDER`、`OLLAMA_BASE_URL`、`OLLAMA_MODEL`、`OLLAMA_TIMEOUT`，默认接入本地 `http://127.0.0.1:11434` 上的 `qwen2.5:7b`。
- 新增 Ollama JSON 调用、超时控制、非法 JSON 检测、本地代理绕过和请求级生成 trace，页面提示与日志可区分 `mock`、`ollama`、`fallback` 三种状态。
- `lesson_design_agent.py`、`ppt_outline_agent.py`、`slide_content_agent.py`、`language_polish_agent.py` 改为“先调 Ollama，失败自动回退规则逻辑”的混合模式；返回结果统一先做 JSON 解析，再做字段归一化与最终 schema 校验。
- `slide_content_agent.py` 与 `language_polish_agent.py` 改为分批调用 Ollama，降低 `qwen2.5:7b` 一次性生成整套课件时的超时风险。
- `pipeline_service.py` 不再吞掉异常，统一由 `llm_service.py` 做顶层 fallback，保证生成方式记录准确。
- `routes/ppt_routes.py` 更新为在新建课件和单页重生成后显示当前生成方式，并避免在持有 SQLite 连接时等待模型返回，修复本地模型慢调用时的数据库锁问题。
- 完成第六轮验证：`compileall` 通过，Flask `test_client` mock 回归通过，`qwen2.5:7b` 已实际完成 Reading 课件新建、单页重生成、PPTX 导出、DOCX 导出。

## 0.5.0
- 新增 `services/agents/layout_planner_agent.py`，按 `slide_type`、课堂任务和可见内容为每页生成 `layout_plan`，统一输出 `layout_type`、`content_blocks`、`visual_suggestion`、`emphasis_level`、`need_image_placeholder`、`teacher_hint_position`。
- `services/pipeline_service.py` 在活动审查后、schema 校验前接入布局规划阶段；单页“重新生成本页”也会补齐 `layout_plan`。
- `routes/ppt_routes.py` 与 `json_schema_checker.py` 更新为保留可选 `layout_plan` 字段，避免编辑保存、重生成和导出时丢失页面版式信息。
- `services/ppt_render_service.py` 升级为多版式渲染器，基于 `layout_plan` 使用封面、目标、导入、阅读任务、对比分析、词汇卡片、长难句分析、讨论、思维导图、作业、板书设计等不同教学场景版式。
- 新版 PPT 渲染仅使用 `python-pptx` 公开 API，继续保持 PowerPoint / Keynote / WPS 兼容性，不写 notes slide / notes master，也不改动底层 zip/xml 结构。
- 导出渲染增加旧任务兼容逻辑：若历史 slide 尚未包含 `layout_plan`，导出时会根据 `slide_type` 自动补齐布局计划。

## 0.4.1
- 为修复 PPTX 兼容性问题，暂时禁用备注页写入，`teacher_notes` 改由 DOCX 授课稿承载。
- `services/ppt_render_service.py` 不再访问或写入 notes slide / notes master 相关结构，PPTX 导出仅保留普通幻灯片内容。
- 新增 `validate_pptx_file(path)`，在导出后检查文件存在性、文件大小、zip 合法性，以及 `ppt/presentation.xml`、`[Content_Types].xml`、`ppt/slides/slide1.xml` 等关键条目。

## 0.4.0
- 优化 `ppt_outline_agent.py`，按 Reading、Grammar、Writing、Listening and Speaking、Revision 五种课型输出不同的大纲模板。
- 优化 `slide_content_agent.py`，让每页内容更接近真实高中英语课堂 PPT，控制文字密度，补充明确任务提示、可执行 teacher notes 和更具体的 interaction type。
- 优化 `language_polish_agent.py`，通过规则改写让课堂英语表达更自然，减少生硬的中文式英语和不必要的句号。
- 优化 `activity_review_agent.py`，检查整节课是否具备导入、语言输入、学生活动、语言输出、总结和作业；缺失时自动补页，并写入可选 `warning` 字段。
- 优化 `json_schema_checker.py` 与 `routes/ppt_routes.py`，保留可选 `warning` 字段，避免活动审查结果在保存与重生成后丢失。
- 新增 `services/ppt_style_config.py`，提供 `default`、`open_class`、`review` 三套基础 PPT 风格配置。
- 重写 `ppt_render_service.py`，根据 `slide_type` 使用不同版式，优化封面页、标题层级、正文留白、页码展示，并将 `teacher_notes` 写入 PPT 备注页。
- 编辑页增强当前 slide 信息展示，增加 slide type、teaching purpose、estimated time、interaction type 的显式信息区，并支持显示自动审查 warning。
- 完成第四轮回归验证：`compileall`、Flask `test_client` 路由测试、课件新建、保存本页、重新生成本页、PPTX 导出、DOCX 导出均通过。

## 0.3.0
- 完成第三轮 Agent 流水线架构搭建，新增 `services/agents/` 目录并拆分为 requirement parser、lesson design、ppt outline、slide content、language polish、activity review、json schema checker 七个独立 Agent。
- 新增 `services/pipeline_service.py`，按 `parse_requirement -> generate_lesson_design -> generate_ppt_outline -> generate_slide_content -> polish_language -> review_activities -> check_schema` 串联生成最终 PPT JSON。
- `services/llm_service.py` 已切换为优先调用本地 Agent pipeline，保留 `mock_ai_service.py` 作为 fallback，不接入真实 AI API。
- 编辑页“重新生成本页”已接入新的 Agent 结构，当前使用单页内容生成 + 语言润色 + schema 校验的轻量流程。
- 新 pipeline 会先把表单输入整理成标准 `lesson_request`，再生成教学设计与课件大纲，并在活动审查阶段将整份课件时长压到 45 分钟内。
- 完成第三轮回归验证：`compileall` 通过，Flask `test_client` 基础路由、新建课件、保存本页、重新生成本页、PPTX 导出、DOCX 导出全部通过。

## 0.2.0
- 完成 `docs/02_Codex任务流.md` 第一轮与第二轮任务，保留 Flask + Blueprint MVP 可运行结构。
- 课件任务改为保存结构化 `slide_json`，并补充数据库兼容迁移与 slide 索引。
- mock 课件生成改为按课型输出更完整的高中英语课件结构，覆盖 objectives、key points、difficult points、lead-in、vocabulary support、task design、classroom interaction、summary、homework、blackboard design。
- 编辑页改为左侧 slide 列表、右侧当前 slide 表单，并新增“保存本页”“重新生成本页”“预览全部内容”“结构化 JSON 预览”。
- 首页、新建页、任务页、编辑页样式重做，统一为更适合教师使用的简洁专业界面。
- PPTX 导出增加更清晰的版式与元信息区块，DOCX 导出补充任务摘要。
- 应用启动增加 `.env` 读取、端口自动回退逻辑，并补齐 `/favicon.ico` 响应以避免额外 404。

## 0.1.0
- 初始化 Flask MVP 项目骨架。
- 增加课件新建、任务列表、逐页编辑。
- 增加 mock AI 生成 slide JSON。
- 增加 PPTX 与 DOCX 导出服务。
