# 02 Codex 任务流

## 使用方式

把本文件和 AGENTS.md 一起放到项目根目录。然后分阶段让 Codex 执行，避免一次性要求太多。

---

## 第一轮任务：搭建 Flask MVP

请执行以下任务：

1. 检查当前项目结构。
2. 基于 Flask + Blueprint 搭建可运行项目。
3. 实现以下页面：
   - `/` 首页；
   - `/ppt/new` 新建课件；
   - `/ppt/tasks` 课件任务列表；
   - `/ppt/task/<id>/edit` 课件编辑；
   - `/ppt/task/<id>/export_pptx` 导出 PPT；
   - `/ppt/task/<id>/export_docx` 导出授课稿。
4. 先使用 mock AI 数据，不要接入真实模型。
5. 使用 SQLite 保存任务和 slide JSON。
6. 使用 python-pptx 生成 PPTX。
7. 使用 python-docx 生成授课稿。
8. 页面使用 Bootstrap，保持简洁专业。
9. 完成后更新 CHANGELOG.md。

---

## 第二轮任务：完善编辑体验

请继续完善：

1. 编辑页面左侧显示 slide 列表。
2. 右侧显示当前 slide 编辑表单。
3. 每页可编辑：
   - title；
   - visible_content；
   - teacher_notes；
   - teaching_purpose；
   - estimated_time；
   - interaction_type。
4. 增加“保存本页”按钮。
5. 增加“重新生成本页”按钮，暂时使用 mock 方法。
6. 增加“预览全部内容”区域。

---

## 第三轮任务：接入 Ollama

请实现：

1. 在 `services/llm_service.py` 中增加 Ollama 调用方法。
2. 默认地址：`http://localhost:11434/api/chat`。
3. 配置项写入 `.env`：
   - LLM_PROVIDER=ollama
   - OLLAMA_BASE_URL=http://localhost:11434
   - OLLAMA_MODEL=qwen3:30b
4. 生成失败时回退 mock 数据。
5. 所有 AI 输出必须要求 JSON 格式。
6. 做 JSON 解析错误处理。

---

## 第四轮任务：接入云端 API

请实现：

1. 支持 DeepSeek API。
2. 支持 OpenAI API。
3. LLM_PROVIDER 可选：mock / ollama / deepseek / openai。
4. API key 从环境变量读取。
5. 不允许把 key 写进代码。

---

## 第五轮任务：教材知识库

请实现：

1. 教材上传页面。
2. 支持 PDF / DOCX / TXT。
3. 解析文本后保存。
4. 后续接入 ChromaDB。
5. 课件生成时可选择关联教材资料。

---

## 第六轮任务：模板系统

请实现：

1. 内置阅读课、语法课、写作课、听说课、复习课模板。
2. 不同课型使用不同 slide 结构。
3. PPT 导出时根据课型选择模板布局。
4. 支持上传自定义 PPT 模板，先保存文件，后续再解析。

---

## 每轮完成后必须检查

1. `python app.py` 能否启动；
2. 页面是否能打开；
3. 新建课件是否成功；
4. 编辑页面是否正常；
5. PPTX 能否下载并打开；
6. DOCX 能否下载并打开；
7. 控制台是否有报错；
8. CHANGELOG.md 是否更新。
