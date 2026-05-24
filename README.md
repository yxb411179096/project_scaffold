# 高中英语 AI PPT 生成系统项目包

本项目包用于交给 Codex / Hermes / Copilot 开发一个本地部署的“高中英语教学 PPT 智能生成系统”。

目标：让高中英语教师输入课程信息后，自动生成可编辑的教学设计、PPT大纲、逐页课件内容、授课稿，并导出 PPTX / DOCX。

建议开发顺序：
1. 先运行 `project_scaffold` 中的 Flask MVP。
2. 确认 mock 课件生成、编辑、导出 PPTX 流程可用。
3. 再接入 Ollama / DeepSeek / OpenAI。
4. 再加入教材知识库与模板系统。

核心文档：
- `docs/01_项目总流程.md`
- `docs/02_Codex任务流.md`
- `docs/03_本地部署流程.md`
- `docs/04_数据库与目录结构.md`
- `docs/05_AI工作流设计.md`
- `docs/06_后续迭代路线.md`
- `AGENTS.md`

