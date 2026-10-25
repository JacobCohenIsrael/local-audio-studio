"""Lightweight stdio MCP proxy. All sessions connect to one local audio service."""
import asyncio
import logging
import httpx2
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp_connection import MCP_URL, ensure_service, read_token


async def main():
    await asyncio.to_thread(ensure_service)
    async with httpx2.AsyncClient(headers={"Authorization":"Bearer "+read_token()},timeout=30,trust_env=False) as http:
        async with streamable_http_client(MCP_URL,http_client=http) as streams:
            async with ClientSession(streams[0],streams[1]) as remote:
                info = await remote.initialize()

                async def list_tools(ctx, params):
                    return await remote.list_tools(params=params)

                async def call_tool(ctx, params):
                    result = await remote.call_tool(params.name,params.arguments)
                    if not isinstance(result,types.CallToolResult):
                        raise RuntimeError("Unexpected response from local audio service.")
                    return result

                server = Server("local-audio-studio",version="1.0.0",instructions=info.instructions,
                    on_list_tools=list_tools,on_call_tool=call_tool)
                async with stdio_server() as (reader,writer):
                    await server.run(reader,writer,server.create_initialization_options())


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
