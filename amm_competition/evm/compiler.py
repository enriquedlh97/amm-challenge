"""Solidity compilation service using py-solc-x."""

import solcx
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CompilationResult:
    """Result of Solidity compilation."""

    success: bool
    bytecode: Optional[bytes] = None
    deployed_bytecode: Optional[bytes] = None
    abi: Optional[list] = None
    errors: Optional[list[str]] = None
    warnings: Optional[list[str]] = None


class SolidityCompiler:
    """Compiles Solidity strategies using py-solc-x.

    Uses inline sources to avoid filesystem dependencies.
    """

    SOLC_VERSION = "0.8.24"

    # Path to the contracts directory with base contracts
    CONTRACTS_DIR = Path(__file__).parent.parent.parent / "contracts"

    def __init__(self):
        """Initialize the compiler and ensure solc is installed."""
        self._ensure_solc_installed()

    def _ensure_solc_installed(self) -> None:
        """Install solc if not already installed."""
        installed = [str(v) for v in solcx.get_installed_solc_versions()]
        if self.SOLC_VERSION not in installed:
            solcx.install_solc(self.SOLC_VERSION)

    def _load_base_contracts(self) -> dict[str, str]:
        """Load base contract sources from the contracts directory."""
        sources = {}
        base_contracts = ["IAMMStrategy.sol", "AMMStrategyBase.sol"]
        for contract in base_contracts:
            src_file = self.CONTRACTS_DIR / "src" / contract
            if src_file.exists():
                sources[contract] = src_file.read_text()
        return sources

    def compile(self, source_code: str, contract_name: str = "Strategy") -> CompilationResult:
        """Compile Solidity source code.

        Args:
            source_code: The Solidity source code (must define a contract named `contract_name`)
            contract_name: Name of the contract to extract (default: "Strategy")

        Returns:
            CompilationResult with bytecode, ABI, and any errors
        """
        errors: list[str] = []
        warnings: list[str] = []

        try:
            # Load base contracts
            base_sources = self._load_base_contracts()

            # Build sources dict with all contracts
            sources = {
                "Strategy.sol": {"content": source_code},
            }
            for name, content in base_sources.items():
                sources[name] = {"content": content}

            # Build compile_standard input
            input_json = {
                "language": "Solidity",
                "sources": sources,
                "settings": {
                    "optimizer": {
                        "enabled": True,
                        "runs": 200,
                    },
                    "viaIR": True,
                    "evmVersion": "paris",
                    "outputSelection": {
                        "*": {
                            "*": ["abi", "evm.bytecode.object", "evm.deployedBytecode.object"],
                        },
                    },
                },
            }

            # Compile
            output = solcx.compile_standard(
                input_json,
                solc_version=self.SOLC_VERSION,
            )

            # Check for errors in output
            if "errors" in output:
                for err in output["errors"]:
                    severity = err.get("severity", "error")
                    message = err.get("formattedMessage", err.get("message", "Unknown error"))
                    if severity == "error":
                        errors.append(message)
                    elif severity == "warning":
                        warnings.append(message)

            if errors:
                return CompilationResult(
                    success=False,
                    errors=errors,
                    warnings=warnings,
                )

            # Extract bytecode and ABI from the output
            contracts = output.get("contracts", {})
            strategy_contracts = contracts.get("Strategy.sol", {})

            if contract_name not in strategy_contracts:
                available = list(strategy_contracts.keys())
                return CompilationResult(
                    success=False,
                    errors=[
                        f"Contract '{contract_name}' not found in output. "
                        f"Available contracts: {available}"
                    ],
                    warnings=warnings,
                )

            contract_output = strategy_contracts[contract_name]
            abi = contract_output.get("abi", [])
            evm = contract_output.get("evm", {})

            bytecode_hex = evm.get("bytecode", {}).get("object", "")
            deployed_bytecode_hex = evm.get("deployedBytecode", {}).get("object", "")

            if not bytecode_hex:
                return CompilationResult(
                    success=False,
                    errors=["No bytecode in compiled output"],
                    warnings=warnings,
                )

            return CompilationResult(
                success=True,
                bytecode=bytes.fromhex(bytecode_hex),
                deployed_bytecode=bytes.fromhex(deployed_bytecode_hex) if deployed_bytecode_hex else None,
                abi=abi,
                warnings=warnings,
            )

        except solcx.exceptions.SolcError as e:
            return CompilationResult(
                success=False,
                errors=[f"Solidity compilation error: {str(e)}"],
            )
        except Exception as e:
            return CompilationResult(
                success=False,
                errors=[f"Compilation error: {str(e)}"],
            )

    def compile_and_get_bytecode(self, source_code: str) -> tuple[bytes, list]:
        """Convenience method to compile and return bytecode directly.

        Args:
            source_code: Solidity source code

        Returns:
            Tuple of (bytecode, abi)

        Raises:
            RuntimeError: If compilation fails
        """
        result = self.compile(source_code)
        if not result.success:
            raise RuntimeError(f"Compilation failed: {'; '.join(result.errors or [])}")
        return result.bytecode, result.abi
