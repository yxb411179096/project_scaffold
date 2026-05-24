# AGENTS.md - 高中英语 AI PPT 生成系统开发总指令

## 项目定位
开发一个本地部署的高中英语教学 PPT 智能生成系统，用于教师日常备课、公开课、阅读课、语法课、写作课、听说课和复习课。

## 技术栈
- 后端：Python Flask
- 前端：Bootstrap + Jinja2
- 数据库：SQLite，后期可迁移 MySQL
- PPT 生成：python-pptx
- Word 生成：python-docx
- 本地模型：Ollama API
- 云端模型：预留 DeepSeek / OpenAI API
- 知识库：后期接入 ChromaDB 或 Qdrant

## 开发原则
1. 不要把所有代码写进 app.py。
2. 使用 Blueprint 拆分路由。
3. AI 调用统一放入 services/llm_service.py。
4. PPT 结构必须先生成 JSON，再由渲染器生成 PPTX。
5. 每页课件必须可编辑。
6. 导出前不允许直接依赖自由文本，必须使用结构化 slide JSON。
7. 页面风格要专业、简洁，适合教师使用。
8. 所有新增功能必须保留可运行状态。

## MVP优先级
第一阶段只做可跑通的最小闭环：
输入课程信息 -> mock生成课件JSON -> 编辑页面 -> 导出PPTX -> 导出授课稿DOCX。

## 课件生成质量标准
每份课件必须包含：
- learning objectives
- key points
- difficult points
- lead-in
- vocabulary support
- task design
- classroom interaction
- summary
- homework
- teacher notes
- blackboard design

## 输出要求
生成的代码必须包含清晰注释。每完成一阶段，请更新 CHANGELOG.md。
