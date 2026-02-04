#!/usr/bin/env node
/**
 * nanocode - minimal claude code alternative
 */

const { execSync, spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const readline = require("readline");

const OPENROUTER_KEY = process.env.OPENROUTER_API_KEY;
const API_URL = OPENROUTER_KEY
  ? "https://openrouter.ai/api/v1/messages"
  : "https://api.anthropic.com/v1/messages";
const MODEL =
  process.env.MODEL ||
  (OPENROUTER_KEY ? "anthropic/claude-opus-4.5" : "claude-opus-4-5");

// ANSI colors
const RESET = "\x1b[0m",
  BOLD = "\x1b[1m",
  DIM = "\x1b[2m";
const BLUE = "\x1b[34m",
  CYAN = "\x1b[36m",
  GREEN = "\x1b[32m",
  YELLOW = "\x1b[33m",
  RED = "\x1b[31m";

// --- Tool implementations ---
function bash(args) {
  return new Promise((resolve) => {
    const proc = spawn(args.cmd, { shell: true });
    const outputLines = [];

    const handleData = (data) => {
      const lines = data.toString().split("\n");
      lines.forEach((line) => {
        if (line) {
          console.log(`  ${DIM}│ ${line}${RESET}`);
          outputLines.push(line);
        }
      });
    };

    proc.stdout.on("data", handleData);
    proc.stderr.on("data", handleData);

    const timeout = setTimeout(() => {
      proc.kill();
      outputLines.push("(timed out after 30s)");
      resolve(outputLines.join("\n") || "(empty)");
    }, 30000);

    proc.on("close", () => {
      clearTimeout(timeout);
      resolve(outputLines.join("\n").trim() || "(empty)");
    });
  });
}

function readFile(args) {
  const filePath = args.path;
  if (!fs.existsSync(filePath)) {
    return `error: file not found: ${filePath}`;
  }
  const content = fs.readFileSync(filePath, "utf-8");
  const lines = content.split("\n");
  const numbered = lines.map(
    (line, i) => `${String(i + 1).padStart(4)} | ${line}`
  );
  return numbered.join("\n");
}

function writeFile(args) {
  const filePath = args.path;
  const content = args.content;
  const dir = path.dirname(filePath);
  if (dir && dir !== ".") {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(filePath, content);
  const lines = content.split("\n").length;
  return `wrote ${lines} lines to ${filePath}`;
}

function glob(args) {
  const pattern = args.pattern;
  const { globSync } = require("fs");
  // Use a simple recursive glob implementation
  const matches = globRecursive(pattern);
  return matches.length ? matches.sort().join("\n") : "(no matches)";
}

function globRecursive(pattern) {
  const results = [];
  const parts = pattern.split("/");
  const hasGlobstar = pattern.includes("**");

  function walkDir(dir, remainingParts) {
    if (remainingParts.length === 0) return;

    const currentPart = remainingParts[0];
    const isLast = remainingParts.length === 1;

    if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) return;

    const entries = fs.readdirSync(dir, { withFileTypes: true });

    if (currentPart === "**") {
      // Match zero or more directories
      walkDir(dir, remainingParts.slice(1));
      for (const entry of entries) {
        if (entry.isDirectory()) {
          walkDir(path.join(dir, entry.name), remainingParts);
        }
      }
    } else {
      const regex = new RegExp(
        "^" + currentPart.replace(/\*/g, ".*").replace(/\?/g, ".") + "$"
      );
      for (const entry of entries) {
        if (regex.test(entry.name)) {
          const fullPath = path.join(dir, entry.name);
          if (isLast) {
            results.push(fullPath);
          } else if (entry.isDirectory()) {
            walkDir(fullPath, remainingParts.slice(1));
          }
        }
      }
    }
  }

  const startDir = parts[0] === "" ? "/" : ".";
  const startParts = parts[0] === "" ? parts.slice(1) : parts;
  walkDir(startDir, startParts);
  return results;
}

// --- Tool definitions ---
const TOOLS = {
  bash: {
    description: "Run shell command",
    schema: { cmd: "string" },
    fn: bash,
  },
  read_file: {
    description: "Read file content with line numbers",
    schema: { path: "string" },
    fn: readFile,
  },
  write_file: {
    description: "Write content to file (creates dirs if needed)",
    schema: { path: "string", content: "string" },
    fn: writeFile,
  },
  glob: {
    description: "Find files matching pattern (supports **)",
    schema: { pattern: "string" },
    fn: glob,
  },
};

async function runTool(name, args) {
  try {
    const result = await TOOLS[name].fn(args);
    return result;
  } catch (err) {
    return `error: ${err.message}`;
  }
}

function makeSchema() {
  return Object.entries(TOOLS).map(([name, { description, schema }]) => {
    const properties = {};
    const required = [];
    for (const [paramName, paramType] of Object.entries(schema)) {
      const isOptional = paramType.endsWith("?");
      const baseType = paramType.replace(/\?$/, "");
      properties[paramName] = {
        type: baseType === "number" ? "integer" : baseType,
      };
      if (!isOptional) required.push(paramName);
    }
    return {
      name,
      description,
      input_schema: { type: "object", properties, required },
    };
  });
}

async function callApi(messages, systemPrompt) {
  const headers = {
    "Content-Type": "application/json",
    "anthropic-version": "2023-06-01",
  };

  if (OPENROUTER_KEY) {
    headers["Authorization"] = `Bearer ${OPENROUTER_KEY}`;
  } else {
    headers["x-api-key"] = process.env.ANTHROPIC_API_KEY || "";
  }

  const response = await fetch(API_URL, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 8192,
      system: systemPrompt,
      messages,
      tools: makeSchema(),
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error: ${response.status} ${text}`);
  }

  return response.json();
}

function separator() {
  const cols = process.stdout.columns || 80;
  return `${DIM}${"─".repeat(Math.min(cols, 80))}${RESET}`;
}

function renderMarkdown(text) {
  return text.replace(/\*\*(.+?)\*\*/g, `${BOLD}$1${RESET}`);
}

async function main() {
  console.log(
    `${BOLD}nanocode${RESET} | ${DIM}${MODEL} (${OPENROUTER_KEY ? "OpenRouter" : "Anthropic"}) | ${process.cwd()}${RESET}\n`
  );

  const messages = [];
  const systemPrompt = `Concise coding assistant. cwd: ${process.cwd()}`;

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const prompt = () => {
    console.log(separator());
    rl.question(`${BOLD}${BLUE}❯${RESET} `, async (userInput) => {
      userInput = userInput.trim();
      console.log(separator());

      if (!userInput) {
        prompt();
        return;
      }

      if (userInput === "/q" || userInput === "exit") {
        rl.close();
        return;
      }

      if (userInput === "/c") {
        messages.length = 0;
        console.log(`${GREEN}⏺ Cleared conversation${RESET}`);
        prompt();
        return;
      }

      messages.push({ role: "user", content: userInput });

      try {
        // Agentic loop: keep calling API until no more tool calls
        while (true) {
          const response = await callApi(messages, systemPrompt);
          const contentBlocks = response.content || [];
          const toolResults = [];

          for (const block of contentBlocks) {
            if (block.type === "text") {
              console.log(`\n${CYAN}⏺${RESET} ${renderMarkdown(block.text)}`);
            }

            if (block.type === "tool_use") {
              const toolName = block.name;
              const toolArgs = block.input;
              const argPreview = String(Object.values(toolArgs)[0]).slice(
                0,
                50
              );
              console.log(
                `\n${GREEN}⏺ ${toolName.charAt(0).toUpperCase() + toolName.slice(1)}${RESET}(${DIM}${argPreview}${RESET})`
              );

              const result = await runTool(toolName, toolArgs);
              const resultLines = result.split("\n");
              let preview = resultLines[0].slice(0, 60);
              if (resultLines.length > 1) {
                preview += ` ... +${resultLines.length - 1} lines`;
              } else if (resultLines[0].length > 60) {
                preview += "...";
              }
              console.log(`  ${DIM}⎿  ${preview}${RESET}`);

              toolResults.push({
                type: "tool_result",
                tool_use_id: block.id,
                content: result,
              });
            }
          }

          messages.push({ role: "assistant", content: contentBlocks });

          if (toolResults.length === 0) break;
          messages.push({ role: "user", content: toolResults });
        }

        console.log();
      } catch (err) {
        console.log(`${RED}⏺ Error: ${err.message}${RESET}`);
      }

      prompt();
    });
  };

  rl.on("close", () => {
    console.log();
    process.exit(0);
  });

  prompt();
}

main();
