import asyncio
import json
import gradio as gr
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TOOLS = [
    "read_file", "safe_read_file", "tail_file", "list_directory",
    "disk_usage", "inode_usage", "memory_info", "cpu_info",
    "running_processes", "top_memory_processes", "system_logs",
    "service_logs", "network_info", "port_listeners", "dns_lookup",
    "http_check", "check_service", "environment_info", "uptime", "grep_log"
]

async def run_tool(url: str, tool_name: str, args_json: str):
    try:
        arguments = json.loads(args_json) if args_json.strip() else {}
    except json.JSONDecodeError:
        return "Error: Invalid JSON in arguments."

    try:
        async with streamablehttp_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                if getattr(result, "isError", False):
                    return f"Error: {result.content[0].text}"
                if result.content and hasattr(result.content[0], 'text'):
                    return result.content[0].text
                return str(result.content)
    except Exception as e:
        return f"Error: {e}"

def sync_run_tool(url: str, tool_name: str, args_json: str):
    return asyncio.run(run_tool(url, tool_name, args_json))

with gr.Blocks(title="MCP System Debugger UI") as demo:
    gr.Markdown("# MCP System Debugger UI")
    gr.Markdown("Test the `system-debugger` MCP server tools via HTTP.")
    
    with gr.Row():
        with gr.Column():
            url_input = gr.Textbox(
                label="MCP Server URL", 
                value="http://localhost:9001/mcp",
                info="The HTTP endpoint of the MCP server."
            )
            tool_dropdown = gr.Dropdown(
                choices=TOOLS,
                label="Tool Name",
                value="environment_info",
                info="Select the tool to execute."
            )
            args_input = gr.Textbox(
                label="Arguments (JSON)",
                value="{}",
                lines=5,
                info="Provide tool arguments as a valid JSON object."
            )
            run_btn = gr.Button("Run Tool", variant="primary")
        
        with gr.Column():
            output_text = gr.Textbox(
                label="Output",
                lines=20,
                interactive=False
            )
            
    run_btn.click(
        fn=sync_run_tool,
        inputs=[url_input, tool_dropdown, args_input],
        outputs=[output_text]
    )

if __name__ == "__main__":
    demo.launch(share=True)
