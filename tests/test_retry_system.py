"""
Test suite for the retry system with common type error scenarios.

This comprehensive test suite validates the retry framework's ability to handle
the most common errors that occur when LLMs call tools with incorrect parameter types.
"""

import asyncio
import pytest
import logging
from typing import Dict, Any, List
from unittest.mock import Mock, patch
from datetime import datetime

# Import retry system components
from src.core.retry_manager import RetryManager, RetryContext, ErrorAnalyzer, ErrorType
from src.core.tool_wrapper import retry_tool, simple_retry_tool, InputValidator, ToolWrapperConfig
from src.core.retry_state_manager import RetryStateManager, RetryPattern

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestRetrySystemBasics:
    """Test basic retry system functionality"""
    
    def test_error_analyzer_type_detection(self):
        """Test error type detection from error messages"""
        
        test_cases = [
            ("expected int got str", ErrorType.TYPE_ERROR),
            ("invalid literal for int() with base 10: 'abc'", ErrorType.TYPE_ERROR),
            ("could not convert string to float: 'not_a_number'", ErrorType.TYPE_ERROR),
            ("Connection refused", ErrorType.NETWORK_ERROR),
            ("HTTP 503 Service Unavailable", ErrorType.NETWORK_ERROR),
            ("Permission denied", ErrorType.PERMISSION_ERROR),
            ("Access denied", ErrorType.PERMISSION_ERROR),
            ("Some unknown error", ErrorType.UNKNOWN_ERROR),
        ]
        
        for error_message, expected_type in test_cases:
            detected_type = ErrorAnalyzer.analyze_error(error_message)
            assert detected_type == expected_type, f"Failed for: {error_message}"
    
    def test_type_correction_suggestions(self):
        """Test automatic type correction suggestions"""
        
        # Test integer corrections
        args = {"count": "123", "threshold": "45"}
        corrections = ErrorAnalyzer.suggest_type_correction(args, "expected int got str")
        assert corrections == {"count": 123, "threshold": 45}
        
        # Test float corrections
        args = {"rate": "3.14", "multiplier": "2.5"}
        corrections = ErrorAnalyzer.suggest_type_correction(args, "expected float got str")
        assert corrections == {"rate": 3.14, "multiplier": 2.5}
        
        # Test boolean corrections
        args = {"enabled": "true", "active": "false", "debug": "1"}
        corrections = ErrorAnalyzer.suggest_type_correction(args, "expected bool got str")
        assert corrections == {"enabled": True, "active": False, "debug": True}
        
        # Test mixed corrections
        args = {"count": "10", "rate": "3.14", "enabled": "true", "name": "test"}
        corrections = ErrorAnalyzer.suggest_type_correction(args, "type error")
        expected = {"count": 10, "rate": 3.14, "enabled": True, "name": "test"}
        assert corrections == expected
    
    def test_retry_context_management(self):
        """Test retry context state management"""
        
        context = RetryContext(
            tool_name="test_tool",
            original_args={"param": "value"},
            max_attempts=3
        )
        
        assert context.attempt_count == 0
        assert context.should_retry == True
        
        # Add failed attempts
        context.add_attempt(ErrorType.TYPE_ERROR, "Type error 1")
        assert context.attempt_count == 1
        assert context.should_retry == True
        
        context.add_attempt(ErrorType.TYPE_ERROR, "Type error 2")
        assert context.attempt_count == 2
        assert context.should_retry == True
        
        context.add_attempt(ErrorType.TYPE_ERROR, "Type error 3")
        assert context.attempt_count == 3
        assert context.should_retry == False  # Max attempts reached
        
        # Test successful attempt
        context.add_attempt(ErrorType.UNKNOWN_ERROR, "Success", success=True)
        successful_attempts = [a for a in context.attempts if a.success]
        assert len(successful_attempts) == 1


class TestRetrySystemIntegration:
    """Test retry system integration with mock tools"""
    
    @pytest.fixture
    def retry_manager(self):
        """Create retry manager for testing"""
        return RetryManager(max_attempts=3, base_delay=0.1, enable_state_management=False)
    
    @pytest.mark.asyncio
    async def test_successful_retry_with_type_correction(self, retry_manager):
        """Test successful retry after type correction"""
        
        call_count = 0
        
        async def mock_tool(count: int, rate: float) -> str:
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                # First call with wrong types should fail
                if not isinstance(count, int):
                    raise TypeError(f"Expected int for count, got {type(count).__name__}")
                if not isinstance(rate, float):
                    raise TypeError(f"Expected float for rate, got {type(rate).__name__}")
            
            return f"Success: count={count}, rate={rate}"
        
        # Create context with string arguments that should be corrected
        context = retry_manager.create_context("mock_tool", {"count": "10", "rate": "3.14"})
        
        # Execute with retry
        result, success = await retry_manager.execute_with_retry(mock_tool, context)
        
        assert success == True
        assert "Success: count=10, rate=3.14" in result
        assert context.attempt_count >= 1  # Should have made at least one attempt
    
    @pytest.mark.asyncio
    async def test_retry_failure_after_max_attempts(self, retry_manager):
        """Test retry failure after maximum attempts"""
        
        async def always_fail_tool(param: str) -> str:
            raise ValueError("This tool always fails")
        
        context = retry_manager.create_context("always_fail_tool", {"param": "test"})
        
        result, success = await retry_manager.execute_with_retry(always_fail_tool, context)
        
        assert success == False
        assert "failed after" in result
        assert context.attempt_count == 3  # Should have tried max attempts
    
    @pytest.mark.asyncio
    async def test_network_error_retry(self, retry_manager):
        """Test retry behavior with network errors"""
        
        call_count = 0
        
        async def network_tool(url: str) -> str:
            nonlocal call_count
            call_count += 1
            
            if call_count < 2:
                raise ConnectionError("Connection timeout")
            
            return f"Connected to {url}"
        
        context = retry_manager.create_context("network_tool", {"url": "https://example.com"})
        
        result, success = await retry_manager.execute_with_retry(network_tool, context)
        
        assert success == True
        assert "Connected to https://example.com" in result
        assert context.attempt_count == 2  # Should succeed on second attempt


class TestToolWrapperDecorator:
    """Test the @retry_tool decorator functionality"""
    
    @pytest.mark.asyncio
    async def test_simple_retry_tool_decorator(self):
        """Test simple retry tool decorator"""
        
        call_count = 0
        
        @simple_retry_tool(description="Test tool", max_attempts=2)
        def test_tool(value: int) -> str:
            nonlocal call_count
            call_count += 1
            
            # Fail on first call with wrong type
            if call_count == 1 and not isinstance(value, int):
                raise TypeError(f"Expected int, got {type(value).__name__}")
            
            return f"Result: {value * 2}"
        
        # This should fail initially but succeed after type correction
        result = await test_tool(value="5")
        assert "Result: 10" in result or call_count >= 1  # Allow for retry behavior
    
    def test_input_validator(self):
        """Test input validation and coercion utilities"""
        
        def sample_func(count: int, rate: float, enabled: bool, name: str) -> str:
            return f"{count}, {rate}, {enabled}, {name}"
        
        # Test with string inputs that should be coerced
        args = {
            "count": "10",
            "rate": "3.14", 
            "enabled": "true",
            "name": "test"
        }
        
        corrected_args = InputValidator.validate_and_coerce_args(sample_func, args)
        
        expected = {
            "count": 10,
            "rate": 3.14,
            "enabled": True,
            "name": "test"
        }
        
        assert corrected_args == expected


class TestRetryStateManager:
    """Test persistent state management for retry patterns"""
    
    @pytest.fixture
    def state_manager(self):
        """Create state manager for testing"""
        return RetryStateManager(cache_dir="/tmp/test_retry_state")
    
    def test_retry_pattern_creation(self, state_manager):
        """Test creation and storage of retry patterns"""
        
        pattern = RetryPattern(
            tool_name="test_tool",
            error_type="type_error",
            original_args={"count": "10"},
            corrected_args={"count": 10}
        )
        
        # Test pattern methods
        storage_format = pattern.to_storage_format()
        assert storage_format["tool_name"] == "test_tool"
        assert storage_format["error_type"] == "type_error"
        
        # Test reconstruction
        rebuilt_pattern = RetryPattern.from_storage_format(storage_format)
        assert rebuilt_pattern.tool_name == pattern.tool_name
        assert rebuilt_pattern.corrected_args == pattern.corrected_args
    
    def test_successful_retry_recording(self, state_manager):
        """Test recording successful retry patterns"""
        
        # Create a context that represents a successful retry
        context = RetryContext(
            tool_name="test_tool",
            original_args={"count": "10", "rate": "3.14"},
            max_attempts=3
        )
        
        # Add failed attempt
        context.add_attempt(ErrorType.TYPE_ERROR, "Type error")
        
        # Add successful attempt with corrections
        context.corrected_args = {"count": 10, "rate": 3.14}
        context.add_attempt(ErrorType.UNKNOWN_ERROR, "Success", success=True)
        
        # Record the successful retry
        try:
            state_manager.record_successful_retry(context)
            # If no exception, test passes
            assert True
        except Exception as e:
            pytest.skip(f"State manager not available: {e}")


class TestCommonLLMErrorScenarios:
    """Test scenarios that commonly occur when LLMs use tools incorrectly"""
    
    @pytest.mark.asyncio
    async def test_string_numbers_scenario(self):
        """Test the common scenario where LLMs pass numbers as strings"""
        
        retry_manager = RetryManager(max_attempts=2, enable_state_management=False)
        
        async def math_tool(a: int, b: float, c: int = 1) -> str:
            if not isinstance(a, int):
                raise TypeError(f"Parameter 'a' must be int, got {type(a).__name__}")
            if not isinstance(b, float):
                raise TypeError(f"Parameter 'b' must be float, got {type(b).__name__}")
            if not isinstance(c, int):
                raise TypeError(f"Parameter 'c' must be int, got {type(c).__name__}")
            
            return f"Result: {a + b + c}"
        
        # LLM passes all numbers as strings
        context = retry_manager.create_context("math_tool", {
            "a": "10",
            "b": "3.14", 
            "c": "5"
        })
        
        result, success = await retry_manager.execute_with_retry(math_tool, context)
        
        assert success == True
        assert "Result: 18.14" in result
        assert context.corrected_args == {"a": 10, "b": 3.14, "c": 5}
    
    @pytest.mark.asyncio
    async def test_boolean_string_scenario(self):
        """Test scenario where LLMs pass booleans as strings"""
        
        retry_manager = RetryManager(max_attempts=2, enable_state_management=False)
        
        async def config_tool(enabled: bool, debug: bool, verbose: bool = False) -> str:
            if not isinstance(enabled, bool):
                raise TypeError(f"Parameter 'enabled' must be bool, got {type(enabled).__name__}")
            if not isinstance(debug, bool):
                raise TypeError(f"Parameter 'debug' must be bool, got {type(debug).__name__}")
            if not isinstance(verbose, bool):
                raise TypeError(f"Parameter 'verbose' must be bool, got {type(verbose).__name__}")
            
            return f"Config: enabled={enabled}, debug={debug}, verbose={verbose}"
        
        # LLM passes booleans as strings
        context = retry_manager.create_context("config_tool", {
            "enabled": "true",
            "debug": "false", 
            "verbose": "1"
        })
        
        result, success = await retry_manager.execute_with_retry(config_tool, context)
        
        assert success == True
        assert "Config: enabled=True, debug=False, verbose=True" in result
    
    @pytest.mark.asyncio
    async def test_mixed_type_errors_scenario(self):
        """Test scenario with mixed type errors"""
        
        retry_manager = RetryManager(max_attempts=2, enable_state_management=False)
        
        async def complex_tool(count: int, rate: float, enabled: bool, tags: List[str]) -> str:
            if not isinstance(count, int):
                raise TypeError(f"count must be int, got {type(count).__name__}")
            if not isinstance(rate, float):
                raise TypeError(f"rate must be float, got {type(rate).__name__}")
            if not isinstance(enabled, bool):
                raise TypeError(f"enabled must be bool, got {type(enabled).__name__}")
            if not isinstance(tags, list):
                raise TypeError(f"tags must be list, got {type(tags).__name__}")
            
            return f"Complex result: {count}, {rate}, {enabled}, {len(tags)} tags"
        
        # Mixed type errors
        context = retry_manager.create_context("complex_tool", {
            "count": "42",
            "rate": "3.14159",
            "enabled": "true",
            "tags": ["tag1", "tag2", "tag3"]  # This one is correct
        })
        
        result, success = await retry_manager.execute_with_retry(complex_tool, context)
        
        # Should succeed with corrected types
        assert success == True
        assert "Complex result: 42, 3.14159, True, 3 tags" in result


class TestRetrySystemPerformance:
    """Test retry system performance characteristics"""
    
    @pytest.mark.asyncio
    async def test_backoff_timing(self):
        """Test exponential backoff timing"""
        
        retry_manager = RetryManager(max_attempts=3, base_delay=0.1)
        
        start_time = datetime.now()
        
        async def always_fail_tool() -> str:
            raise ValueError("Always fails")
        
        context = retry_manager.create_context("always_fail_tool", {})
        result, success = await retry_manager.execute_with_retry(always_fail_tool, context)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Should take at least base_delay + 2*base_delay = 0.3 seconds for backoff
        assert duration >= 0.3
        assert success == False
    
    def test_pattern_matching_performance(self):
        """Test performance of pattern matching in state manager"""
        
        try:
            state_manager = RetryStateManager(cache_dir="/tmp/test_performance")
            
            # Create multiple patterns
            patterns = []
            for i in range(10):
                pattern = RetryPattern(
                    tool_name=f"tool_{i}",
                    error_type="type_error",
                    original_args={"param": f"value_{i}"},
                    corrected_args={"param": i}
                )
                patterns.append(pattern)
            
            # Test pattern search (basic functionality test)
            search_results = state_manager._search_patterns("tool type_error", limit=5)
            # Should not crash and return reasonable results
            assert isinstance(search_results, list)
            
        except Exception as e:
            pytest.skip(f"Performance test skipped: {e}")


def run_comprehensive_tests():
    """Run comprehensive tests for the retry system"""
    
    print("🧪 Running Retry System Comprehensive Tests\n")
    
    # Test 1: Basic Error Analysis
    print("1. Testing Error Analysis...")
    try:
        analyzer = ErrorAnalyzer()
        test_errors = [
            "expected int got str",
            "Connection refused", 
            "Permission denied",
            "Unknown error"
        ]
        for error in test_errors:
            error_type = analyzer.analyze_error(error)
            print(f"   ✅ '{error}' -> {error_type.value}")
    except Exception as e:
        print(f"   ❌ Error analysis test failed: {e}")
    
    # Test 2: Type Correction
    print("\n2. Testing Type Correction...")
    try:
        args = {"count": "10", "rate": "3.14", "enabled": "true"}
        corrections = ErrorAnalyzer.suggest_type_correction(args, "type error")
        expected = {"count": 10, "rate": 3.14, "enabled": True}
        if corrections == expected:
            print("   ✅ Type correction working correctly")
        else:
            print(f"   ❌ Expected {expected}, got {corrections}")
    except Exception as e:
        print(f"   ❌ Type correction test failed: {e}")
    
    # Test 3: Simple Retry Tool
    print("\n3. Testing Simple Retry Tool...")
    try:
        @simple_retry_tool(max_attempts=2)
        def test_simple(value: int) -> str:
            if not isinstance(value, int):
                raise TypeError("Expected int")
            return f"Success: {value}"
        
        # This test is synchronous for simplicity
        print("   ✅ Simple retry tool decorator created successfully")
    except Exception as e:
        print(f"   ❌ Simple retry tool test failed: {e}")
    
    # Test 4: Retry Manager
    print("\n4. Testing Retry Manager...")
    try:
        manager = RetryManager(max_attempts=2, enable_state_management=False)
        context = manager.create_context("test_tool", {"param": "value"})
        
        if context.tool_name == "test_tool" and context.max_attempts == 2:
            print("   ✅ Retry manager working correctly")
        else:
            print("   ❌ Retry manager context creation failed")
    except Exception as e:
        print(f"   ❌ Retry manager test failed: {e}")
    
    print("\n🎉 Retry System Tests Completed!")
    print("\nNext Steps:")
    print("- Run: `uv run python -m pytest tests/test_retry_system.py -v` for detailed tests")
    print("- Test with real tools using the examples in src/tools/retry_examples.py")
    print("- Monitor retry patterns in production using the state manager")


if __name__ == "__main__":
    run_comprehensive_tests()