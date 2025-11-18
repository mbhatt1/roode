"""Browser automation tools using Playwright."""

from typing import Any, Dict, Optional
from ..tools import Tool, ToolInputSchema, ToolResult


class BrowserActionTool(Tool):
    """Tool for browser automation and interaction."""
    
    def __init__(self):
        self.browser = None
        self.page = None
        self.context = None
        super().__init__(
            name="browser_action",
            description=(
                "Request to interact with a Puppeteer-controlled browser. Every action, except "
                "`close`, will be responded to with a screenshot of the browser's current state, "
                "along with any new console logs. You may only perform one browser action per "
                "message."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "action": {
                        "type": "string",
                        "enum": ["launch", "hover", "click", "type", "resize", "scroll_down", "scroll_up", "close"],
                        "description": (
                            "The action to perform:\n"
                            "- launch: Launch browser at specified URL\n"
                            "- hover: Move cursor to x,y coordinate\n"
                            "- click: Click at x,y coordinate\n"
                            "- type: Type text on keyboard\n"
                            "- resize: Resize viewport to w,h\n"
                            "- scroll_down: Scroll down one page\n"
                            "- scroll_up: Scroll up one page\n"
                            "- close: Close the browser"
                        )
                    },
                    "url": {
                        "type": "string",
                        "description": "URL for launch action. Optional."
                    },
                    "coordinate": {
                        "type": "string",
                        "description": "x,y coordinates for click/hover actions. Optional."
                    },
                    "size": {
                        "type": "string",
                        "description": "width,height for resize action. Optional."
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type for type action. Optional."
                    }
                },
                required=["action"]
            )
        )
    
    async def _ensure_playwright(self):
        """Ensure playwright is installed and imported."""
        try:
            from playwright.async_api import async_playwright
            return async_playwright
        except ImportError:
            raise ImportError(
                "Playwright is not installed. Install it with: pip install playwright && playwright install"
            )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Execute browser action."""
        try:
            action = input_data["action"]
            
            # Import playwright
            async_playwright = await self._ensure_playwright()
            
            if action == "launch":
                url = input_data.get("url")
                if not url:
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content="Error: URL is required for launch action",
                        is_error=True
                    )
                
                # Launch browser
                from playwright.async_api import async_playwright
                
                playwright = await async_playwright().start()
                self.browser = await playwright.chromium.launch(headless=True)
                self.context = await self.browser.new_context(
                    viewport={"width": 900, "height": 600}
                )
                self.page = await self.context.new_page()
                
                # Navigate to URL
                await self.page.goto(url, wait_until="networkidle")
                
                # Take screenshot
                screenshot_bytes = await self.page.screenshot()
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Browser launched and navigated to {url}",
                    is_error=False
                )
            
            elif action == "close":
                if self.browser:
                    await self.browser.close()
                    self.browser = None
                    self.page = None
                    self.context = None
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content="Browser closed",
                    is_error=False
                )
            
            # All other actions require an active page
            if not self.page:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content="Error: No active browser session. Use 'launch' first.",
                    is_error=True
                )
            
            if action == "click":
                coordinate = input_data.get("coordinate", "")
                if not coordinate:
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content="Error: coordinate is required for click action",
                        is_error=True
                    )
                
                x, y = map(int, coordinate.split(','))
                await self.page.mouse.click(x, y)
                
                # Wait a bit for any animations
                await self.page.wait_for_timeout(500)
                
                screenshot_bytes = await self.page.screenshot()
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Clicked at coordinates ({x}, {y})",
                    is_error=False
                )
            
            elif action == "hover":
                coordinate = input_data.get("coordinate", "")
                if not coordinate:
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content="Error: coordinate is required for hover action",
                        is_error=True
                    )
                
                x, y = map(int, coordinate.split(','))
                await self.page.mouse.move(x, y)
                
                await self.page.wait_for_timeout(200)
                screenshot_bytes = await self.page.screenshot()
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Hovered at coordinates ({x}, {y})",
                    is_error=False
                )
            
            elif action == "type":
                text = input_data.get("text", "")
                if not text:
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content="Error: text is required for type action",
                        is_error=True
                    )
                
                await self.page.keyboard.type(text)
                
                await self.page.wait_for_timeout(200)
                screenshot_bytes = await self.page.screenshot()
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Typed text: {text}",
                    is_error=False
                )
            
            elif action == "resize":
                size = input_data.get("size", "")
                if not size:
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content="Error: size is required for resize action",
                        is_error=True
                    )
                
                width, height = map(int, size.split(','))
                await self.page.set_viewport_size({"width": width, "height": height})
                
                await self.page.wait_for_timeout(200)
                screenshot_bytes = await self.page.screenshot()
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Resized viewport to {width}x{height}",
                    is_error=False
                )
            
            elif action == "scroll_down":
                await self.page.evaluate("window.scrollBy(0, window.innerHeight)")
                
                await self.page.wait_for_timeout(200)
                screenshot_bytes = await self.page.screenshot()
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content="Scrolled down one page",
                    is_error=False
                )
            
            elif action == "scroll_up":
                await self.page.evaluate("window.scrollBy(0, -window.innerHeight)")
                
                await self.page.wait_for_timeout(200)
                screenshot_bytes = await self.page.screenshot()
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content="Scrolled up one page",
                    is_error=False
                )
            
            else:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: Unknown action: {action}",
                    is_error=True
                )
            
        except ImportError as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=str(e),
                is_error=True
            )
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error performing browser action: {str(e)}",
                is_error=True
            )
    
    async def cleanup(self):
        """Clean up browser resources."""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None
            self.context = None