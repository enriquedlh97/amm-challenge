//! Retail trader simulation with Poisson arrivals.

use rand::SeedableRng;
use rand_distr::{Distribution, LogNormal, Poisson};
use rand_pcg::Pcg64;

/// A retail order to be routed to AMMs.
#[derive(Debug, Clone)]
pub struct RetailOrder {
    /// "buy" or "sell" (from trader's perspective, re: X)
    pub side: &'static str,
    /// Size in Y terms (how much Y willing to spend/receive)
    pub size: f64,
}

/// Generates retail trading flow with Poisson arrivals.
///
/// Retail traders arrive according to a Poisson process and
/// submit orders of random size. They are uninformed and
/// trade randomly (buy or sell with equal probability by default).
pub struct RetailTrader {
    /// Expected number of trades per time step (lambda)
    #[allow(dead_code)]
    arrival_rate: f64,
    /// Mean trade size (in Y terms)
    #[allow(dead_code)]
    mean_size: f64,
    /// Lognormal sigma (log-space)
    #[allow(dead_code)]
    size_sigma: f64,
    /// Probability of a buy order
    buy_prob: f64,
    /// Random number generator
    rng: Pcg64,
    /// Poisson distribution for arrivals
    poisson: Poisson<f64>,
    /// Lognormal distribution for sizes
    lognormal: LogNormal<f64>,
}

impl RetailTrader {
    /// Create a new retail trader.
    pub fn new(
        arrival_rate: f64,
        mean_size: f64,
        size_sigma: f64,
        buy_prob: f64,
        seed: Option<u64>,
    ) -> Self {
        let rng = match seed {
            Some(s) => Pcg64::seed_from_u64(s),
            None => Pcg64::from_entropy(),
        };

        // Create distributions, handling edge cases
        let poisson = Poisson::new(arrival_rate.max(0.01)).unwrap_or_else(|_| Poisson::new(1.0).unwrap());
        let mean = mean_size.max(0.01);
        let sigma = size_sigma.max(0.01);
        let mu = mean.ln() - 0.5 * sigma * sigma;
        let lognormal = LogNormal::new(mu, sigma).unwrap_or_else(|_| LogNormal::new(0.0, 1.0).unwrap());

        Self {
            arrival_rate,
            mean_size,
            size_sigma: sigma,
            buy_prob,
            rng,
            poisson,
            lognormal,
        }
    }

    /// Generate retail orders for one time step.
    #[inline]
    pub fn generate_orders(&mut self) -> Vec<RetailOrder> {
        // Number of arrivals follows Poisson distribution
        let n_arrivals = self.poisson.sample(&mut self.rng) as usize;

        if n_arrivals == 0 {
            return Vec::new();
        }

        let mut orders = Vec::with_capacity(n_arrivals);

        for _ in 0..n_arrivals {
            // Lognormally distributed sizes
            let size = self.lognormal.sample(&mut self.rng);

            // Random side
            let side = if rand::Rng::gen::<f64>(&mut self.rng) < self.buy_prob {
                "buy"
            } else {
                "sell"
            };

            orders.push(RetailOrder { side, size });
        }

        orders
    }

    /// Reset the random state.
    pub fn reset(&mut self, seed: Option<u64>) {
        if let Some(s) = seed {
            self.rng = Pcg64::seed_from_u64(s);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_retail_trader_deterministic() {
        let mut trader1 = RetailTrader::new(5.0, 2.0, 0.5, 0.5, Some(42));
        let mut trader2 = RetailTrader::new(5.0, 2.0, 0.5, 0.5, Some(42));

        // Same seed should produce same orders
        for _ in 0..10 {
            let orders1 = trader1.generate_orders();
            let orders2 = trader2.generate_orders();
            assert_eq!(orders1.len(), orders2.len());
            for (o1, o2) in orders1.iter().zip(orders2.iter()) {
                assert_eq!(o1.side, o2.side);
                assert_eq!(o1.size, o2.size);
            }
        }
    }

    #[test]
    fn test_retail_trader_positive_sizes() {
        let mut trader = RetailTrader::new(5.0, 2.0, 0.5, 0.5, Some(42));

        for _ in 0..100 {
            let orders = trader.generate_orders();
            for order in orders {
                assert!(order.size > 0.0);
            }
        }
    }
}
