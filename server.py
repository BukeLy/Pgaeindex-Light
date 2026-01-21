from fastmcp import FastMCP
from fastmcp.server.providers import FileSystemProvider
from pathlib import Path

mcp = FastMCP(
    name="PDF索引助手",
    instructions="PDF 文档索引服务，支持文本提取和内容摘要",
)

# v3: FileSystemProvider 自动发现 tools/ 下的工具
tools_provider = FileSystemProvider(
    root=Path(__file__).parent / "tools",
    reload=True,  # 开发模式：热重载
)

mcp.add_provider(tools_provider)

if __name__ == "__main__":
    mcp.run()
