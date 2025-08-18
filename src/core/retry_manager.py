"""
Core retry framework for LLM tool execution with state management and error recovery.

Based on research from "Gradientsys: A Multi-Agent LLM Scheduler with ReAct Orchestration"
and modern agentic system patterns for robust tool retry mechanisms.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from enum import Enum
import re
import json

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Categories of tool execution errors for targeted recovery"""
    TYPE_ERROR = "type_error"
    VALIDATION_ERROR = "validation_error" 
    NETWORK_ERROR = "network_error"
    PERMISSION_ERROR = "permission_error"
    RESOURCE_ERROR = "resource_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class RetryAttempt:
    """Record of a single retry attempt"""
    attempt_number: int
    timestamp: float
    error_type: ErrorType
    error_message: str
    corrected_args: Optional[Dict[str, Any]] = None
    success: bool = False
    execution_time: float = 0.0


@dataclass 
class RetryContext:
    """State management for tool retry attempts"""
    tool_name: str
    original_args: Dict[str, Any]
    max_attempts: int = 3
    attempts: List[RetryAttempt] = field(default_factory=list)
    last_error: Optional[str] = None
    corrected_args: Optional[Dict[str, Any]] = None
    
    @property
    def attempt_count(self) -> int:
        return len(self.attempts)
    
    @property
    def should_retry(self) -> bool:
        return self.attempt_count < self.max_attempts
    
    @property
    def total_execution_time(self) -> float:
        return sum(attempt.execution_time for attempt in self.attempts)
    
    def add_attempt(self, error_type: ErrorType, error_message: str, 
                   corrected_args: Optional[Dict[str, Any]] = None,
                   success: bool = False, execution_time: float = 0.0) -> None:
        """Record a retry attempt"""
        attempt = RetryAttempt(
            attempt_number=self.attempt_count + 1,
            timestamp=time.time(),
            error_type=error_type,
            error_message=error_message,
            corrected_args=corrected_args,
            success=success,
            execution_time=execution_time
        )
        self.attempts.append(attempt)
        
        if not success:
            self.last_error = error_message
        if corrected_args:
            self.corrected_args = corrected_args


class ErrorAnalyzer:
    """Analyzes tool execution errors and suggests corrections"""
    
    # Common type error patterns
    TYPE_ERROR_PATTERNS = [
        (r"expected.*int.*got.*str", ErrorType.TYPE_ERROR),
        (r"expected.*float.*got.*str", ErrorType.TYPE_ERROR), 
        (r"expected.*bool.*got.*str", ErrorType.TYPE_ERROR),
        (r"must be int.*got.*str", ErrorType.TYPE_ERROR),
        (r"must be float.*got.*str", ErrorType.TYPE_ERROR),
        (r"must be bool.*got.*str", ErrorType.TYPE_ERROR),
        (r"'(\w+)' object cannot be interpreted as an integer", ErrorType.TYPE_ERROR),
        (r"invalid literal for int\(\) with base \d+:", ErrorType.TYPE_ERROR),
        (r"could not convert string to float:", ErrorType.TYPE_ERROR),
        (r"argument must be.*not.*str", ErrorType.TYPE_ERROR),
    ]
    
    # Network and resource error patterns
    NETWORK_ERROR_PATTERNS = [
        (r"connection.*refused", ErrorType.NETWORK_ERROR),
        (r"timeout", ErrorType.NETWORK_ERROR),
        (r"http.*error", ErrorType.NETWORK_ERROR),
        (r"http.*503", ErrorType.NETWORK_ERROR),
        (r"dns.*resolution.*failed", ErrorType.NETWORK_ERROR),
    ]
    
    # Permission and access error patterns  
    PERMISSION_ERROR_PATTERNS = [
        (r"permission.*denied", ErrorType.PERMISSION_ERROR),
        (r"access.*denied", ErrorType.PERMISSION_ERROR),
        (r"unauthorized", ErrorType.PERMISSION_ERROR),
        (r"403.*forbidden", ErrorType.PERMISSION_ERROR),
    ]
    
    @classmethod
    def analyze_error(cls, error_message: str) -> ErrorType:
        """Categorize error based on message patterns"""
        error_lower = error_message.lower()
        
        # Check type errors first (most common for LLM tools)
        for pattern, error_type in cls.TYPE_ERROR_PATTERNS:
            if re.search(pattern, error_lower):
                return error_type
                
        # Check network errors
        for pattern, error_type in cls.NETWORK_ERROR_PATTERNS:
            if re.search(pattern, error_lower):
                return error_type
                
        # Check permission errors
        for pattern, error_type in cls.PERMISSION_ERROR_PATTERNS:
            if re.search(pattern, error_lower):
                return error_type
                
        return ErrorType.UNKNOWN_ERROR
    
    @classmethod
    def suggest_type_correction(cls, args: Dict[str, Any], error_message: str) -> Optional[Dict[str, Any]]:
        """Suggest corrected arguments for common type errors"""
        corrected_args = args.copy()
        made_corrections = False
        
        # Extract the parameter name that caused the error from the error message
        failed_param = cls._extract_failed_param_from_error(error_message)
        
        for key, value in args.items():
            if isinstance(value, str):
                # Check if this parameter needs boolean conversion based on error message
                if failed_param == key and "must be bool" in error_message.lower():
                    if cls._looks_like_bool(value):
                        bool_value = cls._parse_bool(value)
                        if bool_value is not None:
                            corrected_args[key] = bool_value
                            made_corrections = True
                            logger.info(f"Type correction: {key} '{value}' -> {bool_value}")
                            continue
                
                # Try to convert string numbers to appropriate types
                if cls._looks_like_bool(value):
                    bool_value = cls._parse_bool(value)
                    if bool_value is not None:
                        corrected_args[key] = bool_value
                        made_corrections = True
                        logger.info(f"Type correction: {key} '{value}' -> {bool_value}")
                elif cls._looks_like_int(value):
                    try:
                        corrected_args[key] = int(value)
                        made_corrections = True
                        logger.info(f"Type correction: {key} '{value}' -> {int(value)}")
                    except ValueError:
                        pass
                elif cls._looks_like_float(value):
                    try:
                        corrected_args[key] = float(value)
                        made_corrections = True
                        logger.info(f"Type correction: {key} '{value}' -> {float(value)}")
                    except ValueError:
                        pass
            
            # Handle cases where integer was converted but boolean is needed
            elif isinstance(value, int) and failed_param == key and "must be bool" in error_message.lower():
                if value in [0, 1]:
                    bool_value = bool(value)
                    corrected_args[key] = bool_value
                    made_corrections = True
                    logger.info(f"Type correction: {key} {value} -> {bool_value}")
        
        return corrected_args if made_corrections else None
    
    @staticmethod
    def _extract_failed_param_from_error(error_message: str) -> Optional[str]:
        """Extract parameter name from error message"""
        import re
        # Look for patterns like "Parameter 'param_name'" or "'param_name' must be"
        patterns = [
            r"Parameter '(\w+)'",
            r"'(\w+)' must be",
            r"Parameter (\w+) must be"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_message)
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def _looks_like_int(value: str) -> bool:
        """Check if string looks like an integer"""
        return bool(re.match(r'^-?\d+$', value.strip()))
    
    @staticmethod
    def _looks_like_float(value: str) -> bool:
        """Check if string looks like a float"""
        return bool(re.match(r'^-?\d+\.\d+$', value.strip()))
    
    @staticmethod
    def _looks_like_bool(value: str) -> bool:
        """Check if string looks like a boolean"""
        return value.lower().strip() in ['true', 'false', '1', '0', 'yes', 'no']
    
    @staticmethod
    def _parse_bool(value: str) -> Optional[bool]:
        """Parse string to boolean"""
        value_lower = value.lower().strip()
        if value_lower in ['true', '1', 'yes']:
            return True
        elif value_lower in ['false', '0', 'no']:
            return False
        return None


class RetryManager:
    """Orchestrates tool retry logic with exponential backoff and state management"""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 0.5, enable_state_management: bool = True):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.enable_state_management = enable_state_management
        self.active_contexts: Dict[str, RetryContext] = {}
        
        # Initialize state manager if enabled
        self._state_manager = None
        if enable_state_management:
            try:
                from .retry_state_manager import get_retry_state_manager
                self._state_manager = get_retry_state_manager()
                logger.info("Retry state management enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize retry state management: {e}")
                self.enable_state_management = False
        
    def create_context(self, tool_name: str, args: Dict[str, Any]) -> RetryContext:
        """Create a new retry context for a tool execution"""
        context_key = f"{tool_name}_{hash(str(sorted(args.items())))}"
        context = RetryContext(
            tool_name=tool_name,
            original_args=args,
            max_attempts=self.max_attempts
        )
        self.active_contexts[context_key] = context
        return context
    
    async def execute_with_retry(self, tool_func: Callable, context: RetryContext) -> Tuple[Any, bool]:
        """Execute tool function with retry logic and error recovery"""
        
        current_args = context.original_args.copy()
        
        while context.should_retry:
            start_time = time.time()
            
            try:
                # Attempt tool execution
                result = await tool_func(**current_args)
                execution_time = time.time() - start_time
                
                # Success - record attempt and return
                context.add_attempt(
                    error_type=ErrorType.UNKNOWN_ERROR,
                    error_message="Success",
                    corrected_args=current_args if current_args != context.original_args else None,
                    success=True,
                    execution_time=execution_time
                )
                
                # Record successful retry pattern for learning
                if self._state_manager and context.attempt_count > 1:
                    try:
                        self._state_manager.record_successful_retry(context)
                    except Exception as e:
                        logger.warning(f"Failed to record successful retry pattern: {e}")
                
                logger.info(f"Tool {context.tool_name} succeeded on attempt {context.attempt_count}")
                return result, True
                
            except Exception as e:
                execution_time = time.time() - start_time
                error_message = str(e)
                error_type = ErrorAnalyzer.analyze_error(error_message)
                
                logger.warning(f"Tool {context.tool_name} failed on attempt {context.attempt_count}: {error_message}")
                
                # Record the failed attempt
                context.add_attempt(
                    error_type=error_type,
                    error_message=error_message,
                    execution_time=execution_time
                )
                
                # Try to get predicted correction from state manager first
                corrected_args = None
                if self._state_manager and context.should_retry:
                    try:
                        predicted_args = self._state_manager.predict_correction(
                            context.tool_name, current_args, error_type
                        )
                        if predicted_args:
                            corrected_args = predicted_args
                            logger.info(f"Using predicted correction from learned patterns: {corrected_args}")
                    except Exception as e:
                        logger.warning(f"Failed to get predicted correction: {e}")
                
                # Fall back to rule-based correction if no prediction available
                if not corrected_args and error_type == ErrorType.TYPE_ERROR and context.should_retry:
                    corrected_args = ErrorAnalyzer.suggest_type_correction(current_args, error_message)
                    if corrected_args:
                        logger.info(f"Applying rule-based type corrections: {corrected_args}")
                
                # Apply corrections if available
                if corrected_args and context.should_retry:
                    current_args = corrected_args
                    # Apply exponential backoff before retry
                    await self._backoff_delay(context.attempt_count)
                    continue
                
                # If we can't correct the error or out of retries, fail
                if not context.should_retry:
                    logger.error(f"Tool {context.tool_name} failed after {context.attempt_count} attempts")
                    return self._generate_error_response(context), False
                    
                # Apply exponential backoff before retry
                await self._backoff_delay(context.attempt_count)
        
        # Should not reach here, but handle gracefully
        return self._generate_error_response(context), False
    
    async def _backoff_delay(self, attempt_number: int) -> None:
        """Apply exponential backoff delay"""
        delay = self.base_delay * (2 ** (attempt_number - 1))
        logger.debug(f"Applying backoff delay: {delay}s")
        await asyncio.sleep(delay)
    
    def _generate_error_response(self, context: RetryContext) -> str:
        """Generate comprehensive error response for LLM with actionable feedback"""
        error_summary = []
        error_summary.append(f"❌ Tool '{context.tool_name}' failed after {context.attempt_count} attempts")
        
        if context.attempts:
            last_attempt = context.attempts[-1]
            error_summary.append(f"**Final Error**: {last_attempt.error_message}")
            
            # Provide type correction suggestions if applicable
            if last_attempt.error_type == ErrorType.TYPE_ERROR:
                error_summary.append("\n**Suggestions**:")
                for key, value in context.original_args.items():
                    if isinstance(value, str):
                        if ErrorAnalyzer._looks_like_int(value):
                            error_summary.append(f"- Try passing {key} as integer: {key}={int(value)}")
                        elif ErrorAnalyzer._looks_like_float(value):
                            error_summary.append(f"- Try passing {key} as float: {key}={float(value)}")
                        elif ErrorAnalyzer._looks_like_bool(value):
                            bool_val = ErrorAnalyzer._parse_bool(value)
                            error_summary.append(f"- Try passing {key} as boolean: {key}={bool_val}")
            
            # Show attempt history for debugging
            error_summary.append(f"\n**Attempt History**:")
            for i, attempt in enumerate(context.attempts, 1):
                status = "✅" if attempt.success else "❌"
                error_summary.append(f"{i}. {status} {attempt.error_type.value}: {attempt.error_message[:100]}...")
        
        return "\n".join(error_summary)
    
    def get_context_stats(self, context: RetryContext) -> Dict[str, Any]:
        """Get statistics for a retry context"""
        return {
            "tool_name": context.tool_name,
            "total_attempts": context.attempt_count,
            "total_execution_time": context.total_execution_time,
            "success_rate": sum(1 for a in context.attempts if a.success) / max(1, context.attempt_count),
            "error_types": [a.error_type.value for a in context.attempts],
            "had_corrections": context.corrected_args is not None
        }


# Import asyncio for backoff delays
import asyncio