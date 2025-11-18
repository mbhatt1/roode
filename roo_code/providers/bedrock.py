"""Amazon Bedrock provider implementation"""

from typing import Any, Dict, List, Optional, AsyncIterator, cast
import logging
import json
import asyncio
from datetime import datetime
import boto3
from botocore.config import Config

from ..types import (
    ModelInfo,
    ProviderSettings,
    MessageParam,
    ApiHandlerCreateMessageMetadata,
    StreamChunk,
    ContentBlockDelta,
    ContentBlockStart,
    ContentBlockStop,
    MessageStart,
    MessageDelta,
    MessageStop,
    TextDelta,
    TextContent,
    ToolUseContent,
    ToolResultContent,
    StreamError,
)
from ..stream import ApiStream
from .base import BaseProvider


class BedrockProvider(BaseProvider):
    """Provider for Amazon Bedrock Claude models"""

    # Model information for Claude models on Bedrock
    MODEL_INFO = {
        "anthropic.claude-3-sonnet-20240229-v1:0": ModelInfo(
            max_tokens=4096,
            context_window=200000,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=3.00,
            output_price=15.00,
            cache_writes_price=3.75,
            cache_reads_price=0.30,
        ),
        "anthropic.claude-3-haiku-20240307-v1:0": ModelInfo(
            max_tokens=4096,
            context_window=200000,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=0.25,
            output_price=1.25,
            cache_writes_price=0.30,
            cache_reads_price=0.03,
        ),
        "anthropic.claude-3-opus-20240229-v1:0": ModelInfo(
            max_tokens=4096,
            context_window=200000,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=15.00,
            output_price=75.00,
            cache_writes_price=18.75,
            cache_reads_price=1.50,
        ),
        "anthropic.claude-3-5-sonnet-20240620-v1:0": ModelInfo(
            max_tokens=8192,
            context_window=200000,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=3.00,
            output_price=15.00,
            cache_writes_price=3.75,
            cache_reads_price=0.30,
        ),
    }

    def __init__(self, settings: ProviderSettings):
        """
        Initialize Bedrock provider
        
        Args:
            settings: Provider configuration settings
        """
        super().__init__(settings)
        
        # Initialize AWS credentials
        aws_config = Config(
            region_name=settings.aws_region,
            retries={"max_attempts": 3, "mode": "standard"},
        )
        
        # Check for required AWS parameters
        if not settings.aws_region:
            raise ValueError("AWS region is required for Bedrock")
        
        # Create bedrock client
        session_params = {}
        if settings.aws_access_key and settings.aws_secret_key:
            session_params["aws_access_key_id"] = settings.aws_access_key
            session_params["aws_secret_access_key"] = settings.aws_secret_key
        
        if settings.aws_session_token:
            session_params["aws_session_token"] = settings.aws_session_token
        
        # Create session and client
        session = boto3.Session(**session_params)
        self.client = session.client("bedrock-runtime", config=aws_config)

    def get_model(self) -> tuple[str, ModelInfo]:
        """
        Get model ID and information
        
        Returns:
            tuple: (model_id, ModelInfo)
        """
        model_id = self.settings.api_model_id
        model_info = self.MODEL_INFO.get(
            model_id,
            ModelInfo(
                context_window=200000,
                supports_images=True,
                supports_prompt_cache=True,
            ),
        )
        return model_id, model_info

    async def create_message(
        self,
        system_prompt: str,
        messages: List[MessageParam],
        metadata: Optional[ApiHandlerCreateMessageMetadata] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ApiStream:
        """
        Create a message with Claude via Bedrock
        
        Args:
            system_prompt: System prompt for the conversation
            messages: List of messages in the conversation
            metadata: Optional metadata for tracking
            tools: Optional list of tool definitions for the AI to use
        
        Returns:
            ApiStream: Streaming response
        """
        # Convert messages to Anthropic format for Bedrock
        logging.info(f"API_REQUEST: Converting {len(messages)} messages to Bedrock format")
        anthropic_messages = []
        for idx, msg in enumerate(messages):
            if isinstance(msg.content, str):
                logging.debug(f"API_REQUEST: Message {idx} ({msg.role}): text content ({len(msg.content)} chars)")
                anthropic_messages.append(
                    {"role": msg.role, "content": msg.content}
                )
            else:
                # Handle content blocks
                logging.debug(f"API_REQUEST: Message {idx} ({msg.role}): {len(msg.content)} content blocks")
                content_blocks = []
                for block_idx, block in enumerate(msg.content):
                    if block.type == "text":
                        # For Bedrock: Skip empty or whitespace-only text blocks entirely
                        if not block.text or not block.text.strip():
                            logging.warning(f"API_REQUEST:   Skipping empty/whitespace text block in message {idx}, block {block_idx}")
                            continue  # Skip this block entirely
                        else:
                            content_blocks.append({"type": "text", "text": block.text})
                            logging.debug(f"API_REQUEST:   Message {idx}, Block {block_idx}: text ({len(block.text)} chars)")
                    elif block.type == "image":
                        content_blocks.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": block.source.type,
                                    "media_type": block.source.media_type,
                                    "data": block.source.data,
                                },
                            }
                        )
                        logging.debug(f"API_REQUEST:   Message {idx}, Block {block_idx}: image")
                    elif block.type == "tool_use":
                        # Include tool_use blocks in assistant messages
                        content_blocks.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        logging.info(f"API_REQUEST:   Message {idx}, Block {block_idx}: tool_use - {block.name} (id: {block.id})")
                        logging.debug(f"API_REQUEST:   Tool input: {block.input}")
                    elif block.type == "tool_result":
                        # Include tool_result blocks in user messages
                        result_preview = str(block.content)[:200] + ("..." if len(str(block.content)) > 200 else "")
                        content_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": block.tool_use_id,
                            "content": block.content,
                            "is_error": block.is_error,
                        })
                        logging.info(f"API_REQUEST:   Message {idx}, Block {block_idx}: tool_result for tool_use_id: {block.tool_use_id}, is_error: {block.is_error}")
                        logging.debug(f"API_REQUEST:   Result preview: {result_preview}")
                
                # For Bedrock: Only add messages with valid, non-empty content blocks
                if content_blocks:
                    anthropic_messages.append(
                        {"role": msg.role, "content": content_blocks}
                    )
                    logging.debug(f"API_REQUEST: Message {idx} added with {len(content_blocks)} blocks")
                else:
                    # If all content blocks were empty/whitespace, we need to handle this carefully
                    # For user messages, we can add a minimal valid message
                    if msg.role == "user":
                        anthropic_messages.append(
                            {"role": msg.role, "content": [{"type": "text", "text": "Please continue."}]}
                        )
                        logging.warning(f"API_REQUEST: Message {idx} ({msg.role}) had no valid content, added placeholder")
                    else:
                        # For assistant messages, we can skip them entirely
                        logging.warning(f"API_REQUEST: Skipping assistant message {idx} with no valid content")

        # Create request payload
        _, model_info = self.get_model()

        # Build API call parameters for Bedrock
        # Bedrock uses a different format than direct Anthropic API
        if "claude-3" in self.settings.api_model_id:
            # Claude 3 models on Bedrock
            request_body = {
                "max_tokens": model_info.max_tokens or 4096,
                "anthropic_version": "bedrock-2023-05-31",
            }
            
            # Add system prompt if provided
            if system_prompt:
                request_body["system"] = system_prompt
                
            # Add messages
            request_body["messages"] = anthropic_messages
            
            # Add tools if provided - only for Claude models that support it
            if tools:
                request_body["tools"] = tools
                logging.info(f"API_REQUEST: Sending request with {len(tools)} tools available")
                logging.debug(f"API_REQUEST: Tool names: {[t.get('name', 'unknown') for t in tools]}")
            else:
                logging.info(f"API_REQUEST: Sending request without tools")
        else:
            # Handle other model formats if needed in the future
            request_body = {
                "max_tokens": model_info.max_tokens or 4096,
                "anthropic_version": "bedrock-2023-05-31",
                "system": system_prompt,
                "messages": anthropic_messages,
            }
            
            # Tools might not be supported in non-Claude models
            if tools:
                logging.warning(f"API_REQUEST: Tools may not be supported in model {self.settings.api_model_id}")
        
        logging.info(f"API_REQUEST: Calling Bedrock API with model '{self.settings.api_model_id}'")
        logging.debug(f"API_REQUEST: Total messages to API: {len(anthropic_messages)}")
        
        # Create async iterator for streaming response
        stream = self._create_stream(request_body)
        
        logging.info(f"API_RESPONSE: Stream created successfully")
        return ApiStream(self._convert_stream(stream))

    async def _create_stream(self, request_body: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """
        Create a streaming response from Bedrock
        
        Args:
            request_body: Request body for Bedrock API
        
        Yields:
            Dict: Parsed JSON chunks from Bedrock streaming response
        """
        try:
            # Convert the request body to a JSON string
            body_json = json.dumps(request_body)
            
            # Make the async streaming call to Bedrock
            # Bedrock streaming requires specific parameters
            loop = asyncio.get_event_loop()
            
            # For Claude models, we need to set different parameters
            if "claude" in self.settings.api_model_id.lower():
                invoke_params = {
                    "modelId": self.settings.api_model_id,
                    "body": body_json,
                    "accept": "application/json",
                    "contentType": "application/json",
                }
            else:
                invoke_params = {
                    "modelId": self.settings.api_model_id,
                    "body": body_json,
                }
                
            response = await loop.run_in_executor(
                None,
                lambda: self.client.invoke_model_with_response_stream(**invoke_params)
            )
            
            # Process the streaming response
            stream = response.get('body')
            
            if not stream:
                raise ValueError("Empty response stream from Bedrock")
                
            # Process each chunk in the stream
            for event in stream:
                chunk = event.get("chunk")
                if not chunk:
                    continue
                
                # Parse the chunk payload
                payload = chunk.get("bytes")
                if not payload:
                    continue
                
                try:
                    # Decode and parse the JSON payload
                    chunk_str = payload.decode("utf-8")
                    chunk_data = json.loads(chunk_str)
                    
                    # Transform Bedrock format to our internal format if needed
                    if "completion" in chunk_data:
                        # For models that return simple completion in Bedrock format
                        transformed_chunk = {
                            "type": "content_block_delta",
                            "delta": {
                                "type": "text_delta",
                                "text": chunk_data["completion"]
                            }
                        }
                        yield transformed_chunk
                    elif "type" not in chunk_data and "completion" not in chunk_data:
                        # Handle case where Bedrock returns a different structure
                        if "amazon-bedrock-invocationMetrics" in chunk_data:
                            # Skip Bedrock metrics chunks
                            continue
                        
                        # Check if it contains message content
                        if "message" in chunk_data:
                            text = chunk_data.get("message", {}).get("content", "")
                            transformed_chunk = {
                                "type": "content_block_delta",
                                "delta": {
                                    "type": "text_delta",
                                    "text": text
                                }
                            }
                            yield transformed_chunk
                        else:
                            # If no recognizable format, log and pass through
                            logging.warning(f"Unknown Bedrock chunk format: {chunk_str[:100]}...")
                            yield chunk_data
                    else:
                        # Standard format we already handle
                        yield chunk_data
                        
                except Exception as e:
                    logging.error(f"Error processing chunk: {str(e)}")
                    # Try to yield something useful even on error
                    yield {
                        "type": "error",
                        "error": {"message": f"Error processing chunk: {str(e)}", "type": "ChunkProcessingError"}
                    }
                
        except Exception as e:
            logging.error(f"API_STREAM: Stream creation error - {type(e).__name__}: {str(e)}")
            yield {"type": "error", "error": {"message": str(e), "type": type(e).__name__}}

    async def _convert_stream(
        self, stream: AsyncIterator[Dict[str, Any]]
    ) -> AsyncIterator[StreamChunk]:
        """
        Convert Bedrock stream events to our StreamChunk format
        
        Args:
            stream: Bedrock message stream
        
        Yields:
            StreamChunk: Converted stream chunks
        """
        message_sent = False
        content_block_index = 0
        content_block_started = False
        accumulated_text = ""
        
        try:
            # Send initial message_start to set up the stream
            yield MessageStart(
                type="message_start",
                message={
                    "id": f"bedrock-{int(datetime.now().timestamp())}",
                    "type": "message",
                    "role": "assistant",
                    "model": self.settings.api_model_id,
                    "content": [],
                    "stop_reason": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            )
            message_sent = True
            
            # Start text content block immediately for Bedrock
            yield ContentBlockStart(
                type="content_block_start",
                index=content_block_index,
                content_block=TextContent(
                    type="text",
                    text="",  # Start with empty, will be filled as content comes in
                ),
            )
            content_block_started = True
                
            async for event in stream:
                # Check for error events
                if event.get("type") == "error":
                    yield StreamError(
                        type="error",
                        error=event.get("error", {"message": "Unknown error", "type": "UnknownError"}),
                    )
                    continue
                
                # Bedrock format handlers - primarily looking for completion chunks
                if "completion" in event:
                    # This is the typical Bedrock Claude format with completion field
                    text = event["completion"]
                    accumulated_text += text
                    
                    yield ContentBlockDelta(
                        type="content_block_delta",
                        index=content_block_index,
                        delta=TextDelta(
                            type="text_delta",
                            text=text,
                        ),
                    )
                    continue
                
                # Handle standard Anthropic formats that may come through Bedrock
                if event.get("type") == "content_block_start":
                    content_block = event.get("content_block", {})
                    if content_block.get("type") == "text":
                        if content_block_started:
                            # Close previous block if one is open
                            yield ContentBlockStop(
                                type="content_block_stop",
                                index=content_block_index,
                            )
                            content_block_index += 1
                            
                        yield ContentBlockStart(
                            type="content_block_start",
                            index=content_block_index,
                            content_block=TextContent(
                                type="text",
                                text=content_block.get("text", ""),
                            ),
                        )
                        content_block_started = True
                    elif content_block.get("type") == "tool_use":
                        if content_block_started:
                            # Close previous block if one is open
                            yield ContentBlockStop(
                                type="content_block_stop",
                                index=content_block_index,
                            )
                            content_block_index += 1
                            
                        yield ContentBlockStart(
                            type="content_block_start",
                            index=content_block_index,
                            content_block=ToolUseContent(
                                type="tool_use",
                                id=content_block.get("id", ""),
                                name=content_block.get("name", ""),
                                input=content_block.get("input", {}),
                            ),
                        )
                        content_block_started = True
                
                elif event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        accumulated_text += text
                        
                        yield ContentBlockDelta(
                            type="content_block_delta",
                            index=content_block_index,
                            delta=TextDelta(
                                type="text_delta",
                                text=text,
                            ),
                        )
                    elif delta.get("type") == "input_json_delta":
                        from ..types import InputJsonDelta
                        yield ContentBlockDelta(
                            type="content_block_delta",
                            index=content_block_index,
                            delta=InputJsonDelta(
                                type="input_json_delta",
                                partial_json=delta.get("partial_json", ""),
                            ),
                        )
                
                elif event.get("type") == "content_block_stop":
                    if content_block_started:
                        yield ContentBlockStop(
                            type="content_block_stop",
                            index=content_block_index,
                        )
                        content_block_index += 1
                        content_block_started = False
                
                elif event.get("type") == "message_delta":
                    yield MessageDelta(
                        type="message_delta",
                        delta=event.get("delta", {}),
                        usage=event.get("usage", {"output_tokens": 0}),
                    )
                
                elif event.get("type") == "message_stop":
                    if content_block_started:
                        # Close any open content block
                        yield ContentBlockStop(
                            type="content_block_stop",
                            index=content_block_index,
                        )
                        content_block_started = False
                    yield MessageStop(type="message_stop")
                    
                # Custom event types that might be returned by Bedrock
                elif "message" in event and isinstance(event["message"], dict):
                    # Some Bedrock models return this format
                    if "content" in event["message"]:
                        text = event["message"]["content"]
                        if text:
                            if not content_block_started:
                                yield ContentBlockStart(
                                    type="content_block_start",
                                    index=content_block_index,
                                    content_block=TextContent(
                                        type="text",
                                        text="",
                                    ),
                                )
                                content_block_started = True
                            
                            accumulated_text += text
                            yield ContentBlockDelta(
                                type="content_block_delta",
                                index=content_block_index,
                                delta=TextDelta(
                                    type="text_delta",
                                    text=text,
                                ),
                            )
                
                # Handle stop condition from Bedrock
                if event.get("stop_reason") is not None and content_block_started:
                    yield ContentBlockStop(
                        type="content_block_stop",
                        index=content_block_index,
                    )
                    content_block_started = False
                    yield MessageStop(type="message_stop")
                
                # Check for end-of-stream markers specific to Bedrock
                if "amazon-bedrock-invocationMetrics" in event:
                    # This is a Bedrock-specific metrics event, typically at the end
                    if content_block_started:
                        yield ContentBlockStop(
                            type="content_block_stop",
                            index=content_block_index,
                        )
                        content_block_started = False
                    
                    yield MessageStop(type="message_stop")

            # Ensure we close any open content blocks and the message if the stream ends
            if content_block_started:
                yield ContentBlockStop(
                    type="content_block_stop",
                    index=content_block_index,
                )
                content_block_started = False
                
            # Always send a final message_stop if it wasn't sent
            yield MessageStop(type="message_stop")

        except Exception as e:
            logging.error(f"API_STREAM: Stream error - {type(e).__name__}: {str(e)}")
            if content_block_started:
                try:
                    yield ContentBlockStop(
                        type="content_block_stop",
                        index=content_block_index,
                    )
                except:
                    pass
                    
            yield StreamError(
                type="error",
                error={"message": str(e), "type": type(e).__name__},
            )

    async def count_tokens(self, content: List[Any]) -> int:
        """
        Count tokens using tiktoken-based counting
        
        Args:
            content: List of content blocks
        
        Returns:
            int: Token count
        """
        # Use the base implementation with tiktoken
        return await super().count_tokens(content)