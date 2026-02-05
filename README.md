# AMM Fee Strategy Challenge

Design Solidity strategies that set dynamic fees for an automated market maker (AMM). Your goal: maximize **Instantaneous Markout (IM)**, a measure of profitability.

## Quick Start

```bash
# 1. Build the Rust simulation engine
cd amm_sim_rs
pip install maturin
maturin develop --release
cd ..

# 2. Install the Python package
pip install -e .

# 3. Validate your strategy
amm-match validate contracts/src/SimpleStrategy.sol

# 4. Run simulations
amm-match run contracts/src/SimpleStrategy.sol
```

## How It Works

Your strategy runs on an AMM that competes with a default 25 bps AMM. Both AMMs share the same market:
- If your fees are too high, traders route to the cheaper AMM
- If your fees are too low, you leave money on the table
- The goal is to find the optimal fee policy that maximizes your IM score

## Writing a Strategy

Copy `contracts/src/SimpleStrategy.sol` and implement three functions:

```solidity
contract Strategy is AMMStrategyBase {
    function initialize(uint256 initialX, uint256 initialY)
        external override returns (uint256 bidFee, uint256 askFee);

    function onTrade(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee);

    function getName() external pure override returns (string memory);
}
```

### TradeInfo Fields

After each trade, `onTrade` receives:

| Field | Type | Description |
|-------|------|-------------|
| `isBuy` | `bool` | `true` if AMM bought token X (trader sold X) |
| `amountX` | `uint256` | Amount of X traded (WAD, 1e18 = 1 unit) |
| `amountY` | `uint256` | Amount of Y traded (WAD) |
| `timestamp` | `uint256` | Simulation step number |
| `reserveX` | `uint256` | Post-trade X reserves (WAD) |
| `reserveY` | `uint256` | Post-trade Y reserves (WAD) |

### Fee Precision

Fees use WAD precision where `1e18 = 100%`:
- 25 bps = `25 * BPS` = `25e14`
- 1% = `1e16`

Use the `BPS` constant: `uint256 fee = 30 * BPS;` for 30 basis points.

### Helper Functions

Inherit from `AMMStrategyBase` to get:

| Function | Description |
|----------|-------------|
| `wmul(x, y)` | Multiply two WAD values |
| `wdiv(x, y)` | Divide two WAD values |
| `clamp(v, min, max)` | Clamp value to range |
| `clampFee(fee)` | Clamp fee to [0, MAX_FEE] |
| `bpsToWad(bps)` | Convert basis points to WAD |
| `wadToBps(wad)` | Convert WAD to basis points |
| `sqrt(x)` | Integer square root |
| `absDiff(a, b)` | Absolute difference |

### Storage

You have 32 storage slots (`slots[0]` through `slots[31]`) for persistent state:

```solidity
slots[0] = value;           // Write
uint256 v = slots[0];       // Read
```

## Constraints

| Constraint | Value |
|------------|-------|
| Max fee | 10% (`MAX_FEE = 1e17`) |
| Min fee | 0 |
| Storage slots | 32 (`uint256[32]`) |
| `initialize()` gas | 250,000 |
| `onTrade()` gas | 250,000 |

## CLI Reference

### Run simulations

```bash
amm-match run <strategy.sol> [options]
```

Options:
- `--simulations N` - Number of simulations (default: 99)
- `--steps N` - Steps per simulation (default: 10,000)
- `--volatility V` - Annualized volatility
- `--retail-rate R` - Retail arrival rate per step
- `--retail-size S` - Mean retail trade size

### Validate only

```bash
amm-match validate <strategy.sol>
```

## Scoring

**Instantaneous Markout (IM)** measures profitability by comparing the price at trade time to the "true" market price:

- Positive IM = profitable trades (good)
- Negative IM = adverse selection (bad)

Your score is the average IM across all simulations. Higher is better.

## Examples

See `contracts/src/examples/AdaptiveStrategy.sol` for a more sophisticated strategy that adjusts fees based on trade flow imbalance.

## Project Structure

```
contracts/
  src/
    IAMMStrategy.sol      # Interface
    AMMStrategyBase.sol   # Base contract with helpers
    SimpleStrategy.sol    # Starter template
    examples/
      AdaptiveStrategy.sol
amm_sim_rs/               # Rust simulation engine
amm_competition/          # Python CLI
tests/                    # Test suite
```

## License

MIT
