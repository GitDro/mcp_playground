"""
Example tools demonstrating retry patterns and error recovery capabilities.

This module shows how to integrate the @retry_tool decorator with various
tool scenarios and error conditions that commonly occur with LLM interactions.
"""

import logging
import time
import random
from typing import Dict, List, Optional, Union
from datetime import datetime

from fastmcp import FastMCP
from ..core.tool_wrapper import retry_tool, simple_retry_tool, InputValidator

logger = logging.getLogger(__name__)


def register_retry_example_tools(mcp: FastMCP):
    """Register example tools demonstrating retry patterns"""
    
    @retry_tool(mcp, description="Example tool that demonstrates type error recovery", max_attempts=3)
    def calculate_compound_interest(principal: float, rate: float, years: int, compounds_per_year: int = 12) -> str:
        """Calculate compound interest with automatic type correction for common LLM parameter errors.
        
        This tool demonstrates how the retry system handles type errors when LLMs pass
        string values instead of numbers.
        
        Args:
            principal: Principal amount (e.g., 1000.0)
            rate: Annual interest rate as decimal (e.g., 0.05 for 5%)
            years: Number of years (e.g., 10)
            compounds_per_year: Compounding frequency per year (default: 12 for monthly)
        """
        
        # Validate types - this will trigger retry if LLM passes strings
        if not isinstance(principal, (int, float)):
            raise TypeError(f"Expected principal to be float, got {type(principal).__name__}")
        if not isinstance(rate, (int, float)):
            raise TypeError(f"Expected rate to be float, got {type(rate).__name__}")
        if not isinstance(years, int):
            raise TypeError(f"Expected years to be int, got {type(years).__name__}")
        if not isinstance(compounds_per_year, int):
            raise TypeError(f"Expected compounds_per_year to be int, got {type(compounds_per_year).__name__}")
        
        # Calculate compound interest: A = P(1 + r/n)^(nt)
        amount = principal * (1 + rate / compounds_per_year) ** (compounds_per_year * years)
        interest_earned = amount - principal
        
        return f"""
### Compound Interest Calculation

**Input Parameters:**
- Principal: ${principal:,.2f}
- Annual Rate: {rate*100:.2f}%
- Years: {years}
- Compounding: {compounds_per_year}x per year

**Results:**
- Final Amount: ${amount:,.2f}
- Interest Earned: ${interest_earned:,.2f}
- Total Return: {((amount/principal - 1) * 100):.2f}%
        """.strip()
    
    @retry_tool(mcp, description="Example tool with network simulation and retry recovery", max_attempts=4)
    def fetch_simulated_data(api_endpoint: str, timeout: int = 10, retry_on_failure: bool = True) -> str:
        """Simulate an API call that may fail due to network issues, demonstrating retry recovery.
        
        This tool randomly fails to simulate network errors and shows how the retry
        system handles different types of failures.
        
        Args:
            api_endpoint: API endpoint URL (string)
            timeout: Request timeout in seconds (integer)
            retry_on_failure: Whether to enable retry logic (boolean)
        """
        
        # Type validation
        if not isinstance(api_endpoint, str):
            raise TypeError(f"Expected api_endpoint to be str, got {type(api_endpoint).__name__}")
        if not isinstance(timeout, int):
            raise TypeError(f"Expected timeout to be int, got {type(timeout).__name__}")
        if not isinstance(retry_on_failure, bool):
            raise TypeError(f"Expected retry_on_failure to be bool, got {type(retry_on_failure).__name__}")
        
        # Simulate network conditions
        failure_chance = 0.6  # 60% chance of failure on first attempt
        if random.random() < failure_chance:
            error_types = [
                "Connection timeout after {} seconds".format(timeout),
                "HTTP 503 Service Unavailable",
                "DNS resolution failed for {}".format(api_endpoint),
                "Connection refused by {}".format(api_endpoint)
            ]
            raise ConnectionError(random.choice(error_types))
        
        # Simulate successful response
        response_data = {
            "endpoint": api_endpoint,
            "timestamp": datetime.now().isoformat(),
            "data": {"value": random.randint(1, 1000), "status": "success"},
            "response_time": f"{random.uniform(0.1, 2.0):.2f}s"
        }
        
        return f"""
### API Response Simulation

**Endpoint:** {api_endpoint}
**Response Time:** {response_data['response_time']}
**Timestamp:** {response_data['timestamp']}

**Data:**
```json
{response_data['data']}
```

*Note: This was a simulated API call for demonstration purposes.*
        """.strip()
    
    @retry_tool(mcp, description="Statistical analysis tool with input validation", max_attempts=2)
    def analyze_numbers(numbers: List[Union[int, float]], operation: str = "summary") -> str:
        """Perform statistical analysis on a list of numbers with robust input handling.
        
        Demonstrates retry system handling of complex parameter types and validation errors.
        
        Args:
            numbers: List of numbers to analyze
            operation: Type of analysis ("summary", "distribution", "outliers")
        """
        
        # Validate inputs
        if not isinstance(numbers, list):
            raise TypeError(f"Expected numbers to be list, got {type(numbers).__name__}")
        
        if not numbers:
            raise ValueError("Numbers list cannot be empty")
        
        # Convert string numbers if needed (common LLM error)
        validated_numbers = []
        for i, num in enumerate(numbers):
            if isinstance(num, str):
                try:
                    # Try to convert string to number
                    if '.' in num:
                        validated_numbers.append(float(num))
                    else:
                        validated_numbers.append(int(num))
                except ValueError:
                    raise TypeError(f"Item {i} in numbers list is not a valid number: '{num}'")
            elif isinstance(num, (int, float)):
                validated_numbers.append(num)
            else:
                raise TypeError(f"Item {i} in numbers list must be a number, got {type(num).__name__}")
        
        if operation not in ["summary", "distribution", "outliers"]:
            raise ValueError(f"Operation must be 'summary', 'distribution', or 'outliers', got '{operation}'")
        
        # Perform analysis
        nums = validated_numbers
        count = len(nums)
        total = sum(nums)
        mean = total / count
        sorted_nums = sorted(nums)
        median = sorted_nums[count // 2] if count % 2 == 1 else (sorted_nums[count // 2 - 1] + sorted_nums[count // 2]) / 2
        
        if operation == "summary":
            return f"""
### Statistical Summary

**Dataset:** {count} numbers
**Sum:** {total}
**Mean:** {mean:.2f}
**Median:** {median:.2f}
**Min:** {min(nums)}
**Max:** {max(nums)}
**Range:** {max(nums) - min(nums)}
            """.strip()
        
        elif operation == "distribution":
            # Simple quartile analysis
            q1_idx = count // 4
            q3_idx = 3 * count // 4
            q1 = sorted_nums[q1_idx]
            q3 = sorted_nums[q3_idx]
            iqr = q3 - q1
            
            return f"""
### Distribution Analysis

**Quartiles:**
- Q1 (25%): {q1}
- Q2 (50%, Median): {median}
- Q3 (75%): {q3}
- IQR: {iqr}

**Distribution:**
- Below Q1: {q1_idx + 1} values
- Q1-Q3: {q3_idx - q1_idx} values  
- Above Q3: {count - q3_idx - 1} values
            """.strip()
        
        else:  # outliers
            # Simple outlier detection using IQR method
            q1_idx = count // 4
            q3_idx = 3 * count // 4
            q1 = sorted_nums[q1_idx]
            q3 = sorted_nums[q3_idx]
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outliers = [n for n in nums if n < lower_bound or n > upper_bound]
            
            return f"""
### Outlier Analysis

**Bounds (IQR Method):**
- Lower Bound: {lower_bound:.2f}
- Upper Bound: {upper_bound:.2f}

**Outliers Found:** {len(outliers)}
{outliers if outliers else "No outliers detected"}

**Clean Dataset:** {count - len(outliers)} values within normal range
            """.strip()

    @simple_retry_tool(description="Test tool for type correction demonstration", max_attempts=2)
    def test_type_correction(count: int, threshold: float, enabled: bool, label: str = "test") -> str:
        """A simple test tool that strictly validates parameter types to demonstrate auto-correction.
        
        This tool will fail if parameters are passed as strings instead of their expected types,
        allowing the retry system to demonstrate automatic type correction.
        
        Args:
            count: An integer count (e.g., 5)
            threshold: A float threshold (e.g., 3.14)
            enabled: A boolean flag (e.g., True)
            label: A string label (default: "test")
        """
        
        # Strict type checking to trigger retry system
        if not isinstance(count, int):
            raise TypeError(f"Parameter 'count' must be int, got {type(count).__name__}: {count}")
        if not isinstance(threshold, float):
            raise TypeError(f"Parameter 'threshold' must be float, got {type(threshold).__name__}: {threshold}")
        if not isinstance(enabled, bool):
            raise TypeError(f"Parameter 'enabled' must be bool, got {type(enabled).__name__}: {enabled}")
        if not isinstance(label, str):
            raise TypeError(f"Parameter 'label' must be str, got {type(label).__name__}: {label}")
        
        result = f"""
### Type Correction Test Results

**Parameters Received:**
- count: {count} (type: {type(count).__name__})
- threshold: {threshold} (type: {type(threshold).__name__})
- enabled: {enabled} (type: {type(enabled).__name__})
- label: "{label}" (type: {type(label).__name__})

**Test Status:** ✅ All parameters have correct types!

**Analysis:**
- Count is {'above' if count > threshold else 'at or below'} threshold
- Feature is {'enabled' if enabled else 'disabled'}
- Test labeled as: {label}
        """.strip()
        
        return result

    logger.info("Retry example tools registered successfully")


# Standalone examples for testing without MCP server
def test_retry_examples():
    """Test the retry examples independently"""
    
    print("Testing retry system with type errors...")
    
    # Test 1: Type correction
    try:
        # This should succeed after retry with type correction
        result = test_type_correction("5", "3.14", "true", "demo")
        print("✅ Test 1 passed:", result[:100] + "...")
    except Exception as e:
        print("❌ Test 1 failed:", str(e))
    
    # Test 2: Compound interest with string inputs
    try:
        result = calculate_compound_interest("1000", "0.05", "10", "12")
        print("✅ Test 2 passed:", result[:100] + "...")
    except Exception as e:
        print("❌ Test 2 failed:", str(e))
    
    print("Retry examples testing completed!")


if __name__ == "__main__":
    test_retry_examples()