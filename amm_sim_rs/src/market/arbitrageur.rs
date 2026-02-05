//! Arbitrageur logic for extracting profit from mispriced AMMs.

use crate::amm::CFMM;

/// Result of an arbitrage attempt.
#[derive(Debug, Clone)]
pub struct ArbResult {
    /// AMM name
    pub amm_name: String,
    /// Profit from the arbitrage
    pub profit: f64,
    /// Side: "buy" or "sell" from AMM perspective
    pub side: &'static str,
    /// Amount of X traded
    pub amount_x: f64,
    /// Amount of Y traded
    pub amount_y: f64,
}

/// Arbitrageur that extracts profit from mispriced AMMs.
///
/// Uses closed-form solutions for constant product AMMs.
/// For reserves (x, y), k=xy, fee f, and fair price p:
/// - Buy X from AMM: Δx = x - sqrt(k*(1+f)/p) (profit-maximizing)
/// - Sell X to AMM: Δx = sqrt(k*(1-f)/p) - x (profit-maximizing)
pub struct Arbitrageur;

impl Arbitrageur {
    /// Create a new arbitrageur.
    pub fn new() -> Self {
        Self
    }

    /// Find and execute the optimal arbitrage trade.
    pub fn execute_arb(&self, amm: &mut CFMM, fair_price: f64, timestamp: u64) -> Option<ArbResult> {
        let (rx, ry) = amm.reserves();
        let spot_price = ry / rx;

        if spot_price < fair_price {
            // AMM underprices X - buy X from AMM (AMM sells X)
            self.compute_buy_arb(amm, fair_price, timestamp)
        } else if spot_price > fair_price {
            // AMM overprices X - sell X to AMM (AMM buys X)
            self.compute_sell_arb(amm, fair_price, timestamp)
        } else {
            None
        }
    }

    /// Compute and execute optimal trade when buying X from AMM.
    ///
    /// Maximize profit = Δx * p - Y_paid
    /// Closed-form: Δx = x - sqrt(k*(1+f)/p)
    fn compute_buy_arb(&self, amm: &mut CFMM, fair_price: f64, timestamp: u64) -> Option<ArbResult> {
        let (rx, ry) = amm.reserves();
        let k = rx * ry;
        let fee = amm.fees().ask_fee.to_f64();

        // Optimal trade size
        let new_x = (k * (1.0 + fee) / fair_price).sqrt();
        let amount_x = rx - new_x;

        if amount_x <= 0.0 {
            return None;
        }

        // Cap at 99% of reserves
        let amount_x = amount_x.min(rx * 0.99);

        // Use fast quote to compute profit
        let (total_y, _) = amm.quote_sell_x(amount_x);
        if total_y <= 0.0 {
            return None;
        }

        // Profit = value of X at fair price - Y paid
        let profit = amount_x * fair_price - total_y;

        if profit <= 0.0 {
            return None;
        }

        // Execute the trade
        let _trade = amm.execute_sell_x(amount_x, timestamp)?;

        Some(ArbResult {
            amm_name: amm.name.clone(),
            profit,
            side: "sell", // AMM sells X
            amount_x,
            amount_y: total_y,
        })
    }

    /// Compute and execute optimal trade when selling X to AMM.
    ///
    /// Maximize profit = Y_received - Δx * p
    /// Closed-form: Δx = sqrt(k*(1-f)/p) - x
    fn compute_sell_arb(&self, amm: &mut CFMM, fair_price: f64, timestamp: u64) -> Option<ArbResult> {
        let (rx, ry) = amm.reserves();
        let k = rx * ry;
        let fee = amm.fees().bid_fee.to_f64();

        // Optimal trade size
        let new_x = (k * (1.0 - fee) / fair_price).sqrt();
        let amount_x = new_x - rx;

        if amount_x <= 0.0 {
            return None;
        }

        // Use fast quote to compute profit
        let (y_out, _) = amm.quote_buy_x(amount_x);
        if y_out <= 0.0 {
            return None;
        }

        // Profit = Y received - cost of X at fair price
        let profit = y_out - amount_x * fair_price;

        if profit <= 0.0 {
            return None;
        }

        // Execute the trade
        let _trade = amm.execute_buy_x(amount_x, timestamp)?;

        Some(ArbResult {
            amm_name: amm.name.clone(),
            profit,
            side: "buy", // AMM buys X
            amount_x,
            amount_y: y_out,
        })
    }

    /// Execute arbitrage on multiple AMMs.
    pub fn arbitrage_all(&self, amms: &mut [CFMM], fair_price: f64, timestamp: u64) -> Vec<ArbResult> {
        amms.iter_mut()
            .filter_map(|amm| self.execute_arb(amm, fair_price, timestamp))
            .collect()
    }
}

impl Default for Arbitrageur {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_arb_formulas() {
        // Test the closed-form formulas without EVM
        let rx = 1000.0;
        let ry = 1000.0;
        let k = rx * ry;
        let fee = 0.0025; // 25 bps

        // If fair price > spot price, buy X from AMM
        let fair_price = 1.1; // Above spot of 1.0
        let new_x = (k * (1.0 + fee) / fair_price).sqrt();
        let amount_x = rx - new_x;
        assert!(amount_x > 0.0); // Should want to buy X

        // If fair price < spot price, sell X to AMM
        let fair_price = 0.9; // Below spot of 1.0
        let new_x = (k * (1.0 - fee) / fair_price).sqrt();
        let amount_x = new_x - rx;
        assert!(amount_x > 0.0); // Should want to sell X
    }
}
