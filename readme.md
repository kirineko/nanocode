# nanocode

最小可用的命令行 Coding Agent。使用 Anthropic 或 OpenRouter 的 Messages API，支持工具调用（shell 与文件操作），并以简洁的交互方式在终端运行。

**特性**
- 单文件实现，易读易改
- 支持工具调用：`bash`、`read_file`、`write_file`、`glob`
- 简洁的对话循环与工具结果回显

**运行**
```bash
python3 nanocode.py
```

**环境变量**
- `ANTHROPIC_API_KEY`：使用 Anthropic 官方 API 时必须
- `OPENROUTER_API_KEY`：使用 OpenRouter 时必须（设置后会自动走 OpenRouter）
- `MODEL`：可选，覆盖默认模型名

**交互命令**
- `/q` 或 `exit`：退出
- `/c`：清空上下文

**内置工具**
- `bash`：运行 shell 命令（超时 30s）
- `read_file`：读取文件并带行号
- `write_file`：写入文件（自动创建目录）
- `glob`：文件匹配（支持 `**` 递归）

**使用提示**
- 启动后会显示当前模型与工作目录
- 工具调用会在终端中以简要预览的形式回显结果

**修改记录**
第一次修改提示词：
> 我在做一个最小的Coding Agent nanocode.py,现在请帮我添加文件操作工具

结果：
```
现在我来添加文件操作工具。我会添加 `read_file`、`write_file` 和 `glob` 工具:

⏺ Bash(cat > nanocode.py << 'EOF'
#!/usr/bin/env python3
)
  ⎿  (empty)

⏺ 已添加三个文件操作工具:

| 工具 | 功能 |
|------|------|
| `read_file` | 读取文件，带行号显示 |
| `write_file` | 写入文件，自动创建目录 |
| `glob` | 文件匹配，支持 `**` 递归 |
```
