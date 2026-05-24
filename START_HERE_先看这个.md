# 先看这个

于哥，建议你按这个顺序推进：

## 第一步：先让 Codex 阅读这些文件

让 Codex 先读：

1. AGENTS.md
2. docs/01_项目总流程.md
3. docs/02_Codex任务流.md
4. skills/*.md

然后告诉它：

```text
请先不要大改架构，先检查 project_scaffold 是否能运行，然后按照 docs/02_Codex任务流.md 的第一轮任务完善 MVP。
```

## 第二步：本地运行项目骨架

```bash
cd project_scaffold
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

访问：

```text
http://127.0.0.1:5000
```

## 第三步：验证最小闭环

1. 点击“新建课件”；
2. 填写课题；
3. 生成课件；
4. 编辑任意一页；
5. 导出 PPTX；
6. 导出 DOCX。

## 第四步：交给 Codex 的第一句话

```text
请阅读 AGENTS.md、docs/01_项目总流程.md、docs/02_Codex任务流.md 和 skills 文件夹。当前 project_scaffold 是一个 Flask MVP 骨架。请先检查它是否能运行，并在不破坏现有功能的前提下，完成 docs/02_Codex任务流.md 中第一轮和第二轮任务。每次修改后更新 CHANGELOG.md，并说明修改了哪些文件。
```

## 第五步：再接入 AI

等 mock 流程跑通后，再让 Codex 接入 Ollama。不要一开始就接入真实模型，否则报错点太多，不利于推进。
