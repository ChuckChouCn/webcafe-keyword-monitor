# Execution & Permissions Guidelines

- The user has granted full permissions for all tools, commands, scripts, and file operations.
- Always execute commands and edits proactively without asking for redundant confirmations.
- Always proceed with the task until completion.

# Keyword Monitor Context
- 当用户在飞书对话或控制台中提到“这个词”、“刚才那个词”、“上一个词”、“帮我做这个”等代词时，优先读取项目根目录下的 [CURRENT_MONITOR_KEYWORD.md](file:///home/chuck/projects/agy/CURRENT_MONITOR_KEYWORD.md)（或 `.recent_pushed_keywords.json`）。
- 默认指向最顶部的第 1 个最新焦点词。
- 若用户提到“第2个词”、“推给我的第二个”、“对比刚才推的那几个词”等，支持按序号或词名从列表中提取对应的商机建站建议，直接围绕目标词执行分析或代码脚手架生成。
