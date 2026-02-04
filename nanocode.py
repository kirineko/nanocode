#!/usr/bin/env python3
"""nanocode - minimal claude code alternative"""

import glob as globlib
import json
import os
import re
import subprocess
import urllib.request
import urllib.parse

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
API_URL = (
    "https://openrouter.ai/api/v1/messages"
    if OPENROUTER_KEY
    else "https://api.anthropic.com/v1/messages"
)
MODEL = os.environ.get(
    "MODEL", "anthropic/claude-opus-4.5" if OPENROUTER_KEY else "claude-opus-4-5"
)

# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)


# --- Tool implementations ---
def bash(args):
    proc = subprocess.Popen(
        args["cmd"],
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output_lines = []
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\n(timed out after 30s)")
    return "".join(output_lines).strip() or "(empty)"


def read_file(args):
    path = args["path"]
    if not os.path.exists(path):
        return f"error: file not found: {path}"
    with open(path, "r") as f:
        content = f.read()
    lines = content.split("\n")
    numbered = [f"{i+1:4} | {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered)


def write_file(args):
    path = args["path"]
    content = args["content"]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    lines = len(content.split("\n"))
    return f"wrote {lines} lines to {path}"


def glob(args):
    pattern = args["pattern"]
    matches = globlib.glob(pattern, recursive=True)
    return "\n".join(sorted(matches)) if matches else "(no matches)"


def web_search(args):
    query = args["query"]
    encoded_query = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8")
    except Exception as e:
        return f"search error: {e}"
    
    # Parse results from DuckDuckGo HTML
    results = []
    # Match result blocks: title, url, snippet
    pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.+?)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.+?)</a>'
    matches = re.findall(pattern, html, re.DOTALL)
    
    for url, title, snippet in matches[:5]:  # Top 5 results
        # Clean HTML tags
        title = re.sub(r"<[^>]+>", "", title).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet).strip()
        # Decode URL redirect
        if "uddg=" in url:
            url = urllib.parse.unquote(url.split("uddg=")[1].split("&")[0])
        results.append(f"**{title}**\n{url}\n{snippet}\n")
    
    return "\n".join(results) if results else "no results found"


def gh(args):
    """Execute GitHub CLI commands"""
    cmd = args["cmd"]
    # Ensure the command starts with 'gh'
    if not cmd.strip().startswith("gh "):
        cmd = f"gh {cmd}"
    
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output_lines = []
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\n(timed out after 60s)")
    return "".join(output_lines).strip() or "(empty)"


# --- Tool definitions: (description, schema, function) ---

TOOLS = {
    "bash": (
        "Run shell command",
        {"cmd": "string"},
        bash,
    ),
    "read_file": (
        "Read file content with line numbers",
        {"path": "string"},
        read_file,
    ),
    "write_file": (
        "Write content to file (creates dirs if needed)",
        {"path": "string", "content": "string"},
        write_file,
    ),
    "glob": (
        "Find files matching pattern (supports **)",
        {"pattern": "string"},
        glob,
    ),
    "web_search": (
        "Search the web using DuckDuckGo, returns top results with titles, URLs and snippets",
        {"query": "string"},
        web_search,
    ),
    "gh": (
        "Execute GitHub CLI (gh) commands. Examples: 'gh repo view', 'gh issue list', 'gh pr create', 'gh pr list', 'gh release list'",
        {"cmd": "string"},
        gh,
    ),
}


def run_tool(name, args):
    try:
        return TOOLS[name][2](args)
    except Exception as err:
        return f"error: {err}"


def make_schema():
    result = []
    for name, (description, params, _fn) in TOOLS.items():
        properties = {}
        required = []
        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            properties[param_name] = {
                "type": "integer" if base_type == "number" else base_type
            }
            if not is_optional:
                required.append(param_name)
        result.append(
            {
                "name": name,
                "description": description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
        )
    return result


def call_api(messages, system_prompt):
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(
            {
                "model": MODEL,
                "max_tokens": 8192,
                "system": system_prompt,
                "messages": messages,
                "tools": make_schema(),
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            **(
                {"Authorization": f"Bearer {OPENROUTER_KEY}"}
                if OPENROUTER_KEY
                else {"x-api-key": os.environ.get("ANTHROPIC_API_KEY", "")}
            ),
        },
    )
    response = urllib.request.urlopen(request)
    return json.loads(response.read())


def separator():
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"


def render_markdown(text):
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def main():
    print(
        f"{BOLD}nanocode{RESET} | {DIM}{MODEL} ({'OpenRouter' if OPENROUTER_KEY else 'Anthropic'}) | {os.getcwd()}{RESET}\n"
    )
    messages = []
    system_prompt = f"Concise coding assistant. cwd: {os.getcwd()}"

    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            print(separator())
            if not user_input:
                continue
            if user_input in ("/q", "exit"):
                break
            if user_input == "/c":
                messages = []
                print(f"{GREEN}⏺ Cleared conversation{RESET}")
                continue

            messages.append({"role": "user", "content": user_input})

            # agentic loop: keep calling API until no more tool calls
            while True:
                response = call_api(messages, system_prompt)
                content_blocks = response.get("content", [])
                tool_results = []

                for block in content_blocks:
                    if block["type"] == "text":
                        print(f"\n{CYAN}⏺{RESET} {render_markdown(block['text'])}")

                    if block["type"] == "tool_use":
                        tool_name = block["name"]
                        tool_args = block["input"]
                        arg_preview = str(list(tool_args.values())[0])[:50]
                        print(
                            f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})"
                        )

                        result = run_tool(tool_name, tool_args)
                        result_lines = result.split("\n")
                        preview = result_lines[0][:60]
                        if len(result_lines) > 1:
                            preview += f" ... +{len(result_lines) - 1} lines"
                        elif len(result_lines[0]) > 60:
                            preview += "..."
                        print(f"  {DIM}⎿  {preview}{RESET}")

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block["id"],
                                "content": result,
                            }
                        )

                messages.append({"role": "assistant", "content": content_blocks})

                if not tool_results:
                    break
                messages.append({"role": "user", "content": tool_results})

            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")


if __name__ == "__main__":
    main()
