"""
Enhanced tool wrapper system with @retry_tool decorator for FastMCP tools.

Provides seamless integration of retry logic with existing FastMCP tool decorators,
enabling automatic error recovery and type correction for LLM tool calls.
"""

import asyncio
import inspect
import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union
from fastmcp import FastMCP

from .retry_manager import RetryManager, RetryContext, ErrorAnalyzer

logger = logging.getLogger(__name__)


class ToolWrapperConfig:
    """Configuration for tool retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        enable_type_coercion: bool = True,
        enable_logging: bool = True,
        enable_stats: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.enable_type_coercion = enable_type_coercion
        self.enable_logging = enable_logging
        self.enable_stats = enable_stats


# Global configuration - can be customized per application
DEFAULT_CONFIG = ToolWrapperConfig()

# Global retry manager instance  
_retry_manager = RetryManager(
    max_attempts=DEFAULT_CONFIG.max_attempts,
    base_delay=DEFAULT_CONFIG.base_delay,
    enable_state_management=False  # Disabled - no vector memory dependency
)


def configure_retry_behavior(config: ToolWrapperConfig) -> None:
    """Configure global retry behavior for all @retry_tool decorators"""
    global _retry_manager, DEFAULT_CONFIG
    DEFAULT_CONFIG = config
    _retry_manager = RetryManager(
        max_attempts=config.max_attempts,
        base_delay=config.base_delay,
        enable_state_management=False  # Disabled - no vector memory dependency
    )
    logger.info(f"Retry behavior configured: max_attempts={config.max_attempts}, base_delay={config.base_delay}")


def retry_tool(
    mcp_instance: FastMCP,
    description: Optional[str] = None,
    max_attempts: Optional[int] = None,
    enable_type_coercion: bool = True
):
    """
    Enhanced decorator that wraps FastMCP @mcp.tool with retry logic.
    
    Usage:
        @retry_tool(mcp, description="Get stock data with retry support")
        def get_stock_data(symbol: str, count: int = 10) -> str:
            # Tool implementation
            pass
            
    Args:
        mcp_instance: FastMCP server instance
        description: Tool description (passed to @mcp.tool)
        max_attempts: Override global max attempts for this tool
        enable_type_coercion: Enable automatic type correction
    """
    
    def decorator(func: Callable) -> Callable:
        # Store original function for introspection
        original_func = func
        retry_attempts = max_attempts or DEFAULT_CONFIG.max_attempts
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            """Async wrapper with retry logic"""
            
            # Create retry context
            context = _retry_manager.create_context(
                tool_name=func.__name__,
                args=kwargs
            )
            context.max_attempts = retry_attempts
            
            # Create async tool function for retry manager
            async def tool_func(**tool_kwargs) -> Any:
                if inspect.iscoroutinefunction(original_func):
                    return await original_func(*args, **tool_kwargs)
                else:
                    return original_func(*args, **tool_kwargs)
            
            # Execute with retry logic
            result, success = await _retry_manager.execute_with_retry(tool_func, context)
            
            # Log statistics if enabled
            if DEFAULT_CONFIG.enable_stats:
                stats = _retry_manager.get_context_stats(context)
                if stats["total_attempts"] > 1:
                    logger.info(f"Tool {func.__name__} stats: {stats}")
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            """Sync wrapper - converts to async internally"""
            
            # Check if we're already in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, create a task
                return asyncio.create_task(async_wrapper(*args, **kwargs))
            except RuntimeError:
                # No event loop running, create one
                return asyncio.run(async_wrapper(*args, **kwargs))
        
        # Determine if the original function is async
        if inspect.iscoroutinefunction(original_func):
            wrapped_func = async_wrapper
        else:
            wrapped_func = sync_wrapper
            
        # Apply the original FastMCP decorator
        if description:
            mcp_tool_func = mcp_instance.tool(description=description)(wrapped_func)
        else:
            mcp_tool_func = mcp_instance.tool()(wrapped_func)
        
        # Preserve original function metadata for debugging
        mcp_tool_func._original_func = original_func
        mcp_tool_func._retry_enabled = True
        mcp_tool_func._retry_attempts = retry_attempts
        
        return mcp_tool_func
    
    return decorator


def simple_retry_tool(
    description: Optional[str] = None,
    max_attempts: int = 3,
    enable_type_coercion: bool = True
):
    """
    Simplified retry decorator that can be used without MCP instance.
    Useful for testing or standalone tool functions.
    
    Usage:
        @simple_retry_tool(description="Test tool", max_attempts=2)
        def my_tool(value: int) -> str:
            return str(value * 2)
    """
    
    def decorator(func: Callable) -> Callable:
        original_func = func
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Create retry context
            context = RetryContext(
                tool_name=func.__name__,
                original_args=kwargs,
                max_attempts=max_attempts
            )
            
            # Create async tool function
            async def tool_func(**tool_kwargs) -> Any:
                if inspect.iscoroutinefunction(original_func):
                    return await original_func(*args, **tool_kwargs)
                else:
                    return original_func(*args, **tool_kwargs)
            
            # Execute with retry logic
            result, success = await _retry_manager.execute_with_retry(tool_func, context)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                loop = asyncio.get_running_loop()
                return asyncio.create_task(async_wrapper(*args, **kwargs))
            except RuntimeError:
                return asyncio.run(async_wrapper(*args, **kwargs))
        
        if inspect.iscoroutinefunction(original_func):
            wrapped_func = async_wrapper
        else:
            wrapped_func = sync_wrapper
            
        # Store metadata
        wrapped_func._original_func = original_func
        wrapped_func._retry_enabled = True
        wrapped_func._retry_attempts = max_attempts
        
        return wrapped_func
    
    return decorator


class InputValidator:
    """Utility class for validating and coercing tool inputs"""
    
    @staticmethod
    def validate_and_coerce_args(
        func: Callable,
        args: Dict[str, Any],
        enable_coercion: bool = True
    ) -> Dict[str, Any]:
        """
        Validate and optionally coerce arguments based on function signature.
        
        Args:
            func: The tool function
            args: Arguments to validate/coerce
            enable_coercion: Whether to attempt type coercion
            
        Returns:
            Validated/corrected arguments
        """
        
        # Get function signature
        sig = inspect.signature(func)
        corrected_args = args.copy()
        
        for param_name, param in sig.parameters.items():
            if param_name in args:
                value = args[param_name]
                expected_type = param.annotation
                
                # Skip if no type annotation
                if expected_type == inspect.Parameter.empty:
                    continue
                
                # Check if type coercion is needed and possible
                if enable_coercion and not isinstance(value, expected_type):
                    coerced_value = InputValidator._coerce_type(value, expected_type)
                    if coerced_value is not None:
                        corrected_args[param_name] = coerced_value
                        logger.debug(f"Coerced {param_name}: {value} -> {coerced_value}")
        
        return corrected_args
    
    @staticmethod
    def _coerce_type(value: Any, target_type: type) -> Any:
        """Attempt to coerce value to target type"""
        
        # Handle string inputs (common from LLMs)
        if isinstance(value, str):
            if target_type == int:
                if ErrorAnalyzer._looks_like_int(value):
                    try:
                        return int(value)
                    except ValueError:
                        pass
                        
            elif target_type == float:
                if ErrorAnalyzer._looks_like_float(value) or ErrorAnalyzer._looks_like_int(value):
                    try:
                        return float(value)
                    except ValueError:
                        pass
                        
            elif target_type == bool:
                if ErrorAnalyzer._looks_like_bool(value):
                    return ErrorAnalyzer._parse_bool(value)
        
        # Handle numeric conversions
        elif isinstance(value, (int, float)):
            if target_type == str:
                return str(value)
            elif target_type == float and isinstance(value, int):
                return float(value)
            elif target_type == int and isinstance(value, float) and value.is_integer():
                return int(value)
        
        # Could not coerce
        return None


def get_tool_stats(tool_func: Callable) -> Optional[Dict[str, Any]]:
    """Get retry statistics for a tool function"""
    if hasattr(tool_func, '_retry_enabled') and tool_func._retry_enabled:
        return {
            "retry_enabled": True,
            "max_attempts": getattr(tool_func, '_retry_attempts', DEFAULT_CONFIG.max_attempts),
            "original_function": getattr(tool_func, '_original_func', None).__name__
        }
    return {"retry_enabled": False}


def is_retry_enabled(tool_func: Callable) -> bool:
    """Check if a tool has retry functionality enabled"""
    return hasattr(tool_func, '_retry_enabled') and tool_func._retry_enabled