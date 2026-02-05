"""EVM-based strategy execution module.

This module provides:
- EVMStrategyExecutor: Executes Solidity strategies using pyrevm
- SolidityCompiler: Compiles Solidity code using Foundry
- SolidityValidator: Static analysis for security
- EVMStrategyAdapter: Adapts EVM strategies to the AMMStrategy interface
"""

from amm_competition.evm.executor import EVMStrategyExecutor, EVMExecutionResult
from amm_competition.evm.compiler import SolidityCompiler, CompilationResult
from amm_competition.evm.validator import SolidityValidator, ValidationResult
from amm_competition.evm.adapter import EVMStrategyAdapter

__all__ = [
    "EVMStrategyExecutor",
    "EVMExecutionResult",
    "SolidityCompiler",
    "CompilationResult",
    "SolidityValidator",
    "ValidationResult",
    "EVMStrategyAdapter",
]
