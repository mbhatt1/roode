"""Type definitions for Roo Code SDK"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class ApiProvider(str, Enum):
    """Supported API providers"""
    ANTHROPIC = "anthropic"
    CLAUDE_CODE = "claude-code"
    GLAMA = "glama"
    OPENROUTER = "openrouter"
    BEDROCK = "bedrock"
    VERTEX = "vertex"
    OPENAI = "openai"
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"
    GEMINI = "gemini"
    OPENAI_NATIVE = "openai-native"
    DEEPSEEK = "deepseek"
    DOUBAO = "doubao"
    QWEN_CODE = "qwen-code"
    MOONSHOT = "moonshot"
    VSCODE_LM = "vscode-lm"
    MISTRAL = "mistral"
    UNBOUND = "unbound"
    REQUESTY = "requesty"
    HUMAN_RELAY = "human-relay"
    FAKE_AI = "fake-ai"
    XAI = "xai"
    GROQ = "groq"
    DEEPINFRA = "deepinfra"
    HUGGINGFACE = "huggingface"
    CHUTES = "chutes"
    LITELLM = "litellm"
    CEREBRAS = "cerebras"
    SAMBANOVA = "sambanova"
    ZAI = "zai"
    FIREWORKS = "fireworks"
    IO_INTELLIGENCE = "io-intelligence"
    ROO = "roo"
    FEATHERLESS = "featherless"
    VERCEL_AI_GATEWAY = "vercel-ai-gateway"
    MINIMAX = "minimax"


class ModelInfo(BaseModel):
    """Information about an AI model"""
    max_tokens: Optional[int] = Field(default=None, description="Maximum number of tokens the model can handle")
    context_window: int = Field(description="Size of the context window")
    supports_images: bool = Field(default=False, description="Whether the model supports image inputs")
    supports_prompt_cache: bool = Field(default=False, description="Whether the model supports prompt caching")
    input_price: Optional[float] = Field(default=None, description="Price per input token")
    output_price: Optional[float] = Field(default=None, description="Price per output token")
    cache_writes_price: Optional[float] = Field(default=None, description="Price per cache write token")
    cache_reads_price: Optional[float] = Field(default=None, description="Price per cache read token")
    description: Optional[str] = Field(default=None, description="Model description")


class ProviderSettings(BaseModel):
    """Settings for API provider configuration"""
    api_provider: ApiProvider = Field(description="The API provider to use")
    api_model_id: str = Field(description="The model ID to use")
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    api_base_url: Optional[str] = Field(default=None, alias="baseUrl", description="Base URL for API requests")
    aws_region: Optional[str] = Field(default=None, alias="awsRegion", description="AWS region for Bedrock")
    aws_access_key: Optional[str] = Field(default=None, alias="awsAccessKeyId", description="AWS access key")
    aws_secret_key: Optional[str] = Field(default=None, alias="awsSecretAccessKey", description="AWS secret key")
    aws_session_token: Optional[str] = Field(default=None, alias="awsSessionToken", description="AWS session token")
    vertex_project_id: Optional[str] = Field(default=None, alias="vertexProjectId", description="Vertex AI project ID")
    vertex_region: Optional[str] = Field(default=None, alias="vertexRegion", description="Vertex AI region")
    azure_api_version: Optional[str] = Field(default=None, alias="azureApiVersion", description="Azure API version")

    class Config:
        use_enum_values = True
        populate_by_name = True


class TextContent(BaseModel):
    """Text content block"""
    type: Literal["text"] = "text"
    text: str


class ImageSource(BaseModel):
    """Image source data"""
    type: Literal["base64"] = "base64"
    media_type: str
    data: str


class ImageContent(BaseModel):
    """Image content block"""
    type: Literal["image"] = "image"
    source: ImageSource


class ToolUseContent(BaseModel):
    """Tool use content block from Anthropic"""
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: Dict[str, Any]


class ToolResultContent(BaseModel):
    """Tool result content block for Anthropic"""
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: Union[str, List[Dict[str, Any]]]
    is_error: Optional[bool] = False


ContentBlock = Union[TextContent, ImageContent, ToolUseContent, ToolResultContent]


class MessageParam(BaseModel):
    """Message parameter for API requests"""
    role: Literal["user", "assistant"]
    content: Union[str, List[ContentBlock]]


class ApiHandlerCreateMessageMetadata(BaseModel):
    """Metadata for creating messages"""
    task_id: str = Field(description="Task ID for tracking")
    mode: Optional[str] = Field(default=None, description="Current mode slug")


class StreamChunkType(str, Enum):
    """Types of streaming chunks"""
    MESSAGE_START = "message_start"
    CONTENT_BLOCK_START = "content_block_start"
    CONTENT_BLOCK_DELTA = "content_block_delta"
    CONTENT_BLOCK_STOP = "content_block_stop"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_STOP = "message_stop"
    ERROR = "error"


class TextDelta(BaseModel):
    """Text delta in streaming response"""
    type: Literal["text_delta"] = "text_delta"
    text: str


class InputJsonDelta(BaseModel):
    """Input JSON delta in streaming response for tool use"""
    type: Literal["input_json_delta"] = "input_json_delta"
    partial_json: str


class ContentBlockDelta(BaseModel):
    """Content block delta chunk"""
    type: Literal["content_block_delta"] = "content_block_delta"
    index: int
    delta: Union[TextDelta, InputJsonDelta]


class ContentBlockStart(BaseModel):
    """Content block start chunk"""
    type: Literal["content_block_start"] = "content_block_start"
    index: int
    content_block: Union[TextContent, ToolUseContent]


class ContentBlockStop(BaseModel):
    """Content block stop chunk"""
    type: Literal["content_block_stop"] = "content_block_stop"
    index: int


class MessageStart(BaseModel):
    """Message start chunk"""
    type: Literal["message_start"] = "message_start"
    message: Dict[str, Any]


class UsageDelta(BaseModel):
    """Usage delta information"""
    output_tokens: int


class MessageDelta(BaseModel):
    """Message delta chunk"""
    type: Literal["message_delta"] = "message_delta"
    delta: Dict[str, Any]
    usage: UsageDelta


class MessageStop(BaseModel):
    """Message stop chunk"""
    type: Literal["message_stop"] = "message_stop"


class StreamError(BaseModel):
    """Stream error chunk"""
    type: Literal["error"] = "error"
    error: Dict[str, Any]


StreamChunk = Union[
    MessageStart,
    ContentBlockStart,
    ContentBlockDelta,
    ContentBlockStop,
    MessageDelta,
    MessageStop,
    StreamError,
]


class CompletionResponse(BaseModel):
    """Complete response from API"""
    content: List[ContentBlock]
    stop_reason: Optional[str] = None
    usage: Dict[str, int] = Field(default_factory=dict)