#!/usr/bin/env python3
"""
Test script to verify Bedrock integration with read_file tool

This script tests if the read_file tool works correctly with the Bedrock provider.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from roo_code import RooClient, ProviderSettings
from roo_code.types import ApiProvider
from roo_code.builtin_tools.file_operations import ReadFileTool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

async def test_read_file():
    """Test the read_file tool with Bedrock provider"""
    # Get AWS credentials from environment
    aws_region = os.getenv("AWS_REGION")
    if not aws_region:
        logger.error("AWS_REGION environment variable must be set")
        sys.exit(1)

    # Create provider settings
    provider_settings = ProviderSettings(
        api_provider=ApiProvider.BEDROCK,
        api_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        aws_region=aws_region,
    )
    
    # Create client
    client = RooClient(provider_settings=provider_settings)
    logger.info(f"Created RooClient with Bedrock provider")
    
    # Create read file tool
    read_tool = ReadFileTool(cwd=str(Path.cwd()))
    logger.info(f"Created ReadFileTool with cwd: {read_tool.cwd}")
    
    # Try to read a few files
    test_files = [
        "README.md",
        "pyproject.toml",
        "./pyproject.toml",
        "examples/test_bedrock_read_file.py",
    ]
    
    for file_path in test_files:
        try:
            logger.info(f"Reading file: {file_path}")
            result = await read_tool.execute({"path": file_path})
            
            if result.is_error:
                error_details = ""
                if hasattr(result, 'exception') and result.exception:
                    error_details = f" - Exception: {type(result.exception).__name__}: {str(result.exception)}"
                logger.error(f"Error reading {file_path}: {result.content}{error_details}")
            else:
                content_preview = result.content[:100] + "..." if len(result.content) > 100 else result.content
                logger.info(f"Successfully read {file_path}, preview: {content_preview}")
        except Exception as e:
            logger.error(f"Exception while reading {file_path}: {e}")
    
    # Test directly through the AI
    logger.info("Testing read_file through Bedrock AI...")
    
    system_prompt = "You are a helpful assistant. Read the requested file and provide a brief summary."
    response = await client.create_message(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "Please read the README.md file and summarize it"}],
        tools=[read_tool.to_tool_definition()]
    )
    
    result = await response.get_text()
    logger.info(f"AI response to file read request: {result[:200]}...")

if __name__ == "__main__":
    asyncio.run(test_read_file())