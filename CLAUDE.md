# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Rules

- **FastMCP**: 编写 FastMCP 相关代码前，必须先查阅 `docs/fast-mcp-docs/index.txt`
- **FastMCP 版本**: 本项目使用 FastMCP v3，禁止使用 v2 版本的编码规则
- **环境变量读取**: 禁止在模块顶层读取环境变量（Python 模块导入时机早于 MCP 客户端注入 env），必须使用以下方式之一：
  1. 函数内动态读取 `os.environ.get()`（简单场景）
  2. Lifespan Context（需要启动时验证或共享资源）
