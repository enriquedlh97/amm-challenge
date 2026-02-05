//! Simulation configuration.

use pyo3::prelude::*;

/// Configuration for a simulation run.
#[pyclass]
#[derive(Debug, Clone)]
pub struct SimulationConfig {
    /// Number of simulation steps
    #[pyo3(get, set)]
    pub n_steps: u32,

    /// Initial fair price
    #[pyo3(get, set)]
    pub initial_price: f64,

    /// Initial X reserves
    #[pyo3(get, set)]
    pub initial_x: f64,

    /// Initial Y reserves
    #[pyo3(get, set)]
    pub initial_y: f64,

    /// GBM drift (annualized)
    #[pyo3(get, set)]
    pub gbm_mu: f64,

    /// GBM volatility (annualized)
    #[pyo3(get, set)]
    pub gbm_sigma: f64,

    /// GBM time step
    #[pyo3(get, set)]
    pub gbm_dt: f64,

    /// Retail order arrival rate (Poisson lambda)
    #[pyo3(get, set)]
    pub retail_arrival_rate: f64,

    /// Mean retail order size (lognormal mean)
    #[pyo3(get, set)]
    pub retail_mean_size: f64,

    /// Lognormal sigma for retail order sizes (log-space)
    #[pyo3(get, set)]
    pub retail_size_sigma: f64,

    /// Probability of buy order
    #[pyo3(get, set)]
    pub retail_buy_prob: f64,

    /// Random seed for reproducibility (None = random)
    #[pyo3(get, set)]
    pub seed: Option<u64>,
}

#[pymethods]
impl SimulationConfig {
    #[new]
    #[pyo3(signature = (
        n_steps,
        initial_price,
        initial_x,
        initial_y,
        gbm_mu,
        gbm_sigma,
        gbm_dt,
        retail_arrival_rate,
        retail_mean_size,
        retail_size_sigma,
        retail_buy_prob,
        seed
    ))]
    pub fn new(
        n_steps: u32,
        initial_price: f64,
        initial_x: f64,
        initial_y: f64,
        gbm_mu: f64,
        gbm_sigma: f64,
        gbm_dt: f64,
        retail_arrival_rate: f64,
        retail_mean_size: f64,
        retail_size_sigma: f64,
        retail_buy_prob: f64,
        seed: Option<u64>,
    ) -> Self {
        Self {
            n_steps,
            initial_price,
            initial_x,
            initial_y,
            gbm_mu,
            gbm_sigma,
            gbm_dt,
            retail_arrival_rate,
            retail_mean_size,
            retail_size_sigma,
            retail_buy_prob,
            seed,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "SimulationConfig(n_steps={}, seed={:?})",
            self.n_steps, self.seed
        )
    }
}

/// Configuration for hyperparameter variance across simulations.
#[derive(Debug, Clone)]
pub struct HyperparameterVariance {
    pub retail_mean_size_min: f64,
    pub retail_mean_size_max: f64,
    pub vary_retail_mean_size: bool,

    pub retail_arrival_rate_min: f64,
    pub retail_arrival_rate_max: f64,
    pub vary_retail_arrival_rate: bool,

    pub gbm_sigma_min: f64,
    pub gbm_sigma_max: f64,
    pub vary_gbm_sigma: bool,
}

impl HyperparameterVariance {
    /// Apply variance to create a new config based on seed.
    pub fn apply(&self, base: &SimulationConfig, seed: u64) -> SimulationConfig {
        use rand::SeedableRng;
        use rand::Rng;
        use rand_pcg::Pcg64;

        let mut rng = Pcg64::seed_from_u64(seed);

        let retail_mean_size = if self.vary_retail_mean_size {
            rng.gen_range(self.retail_mean_size_min..self.retail_mean_size_max)
        } else {
            base.retail_mean_size
        };

        let retail_arrival_rate = if self.vary_retail_arrival_rate {
            rng.gen_range(self.retail_arrival_rate_min..self.retail_arrival_rate_max)
        } else {
            base.retail_arrival_rate
        };

        let gbm_sigma = if self.vary_gbm_sigma {
            rng.gen_range(self.gbm_sigma_min..self.gbm_sigma_max)
        } else {
            base.gbm_sigma
        };

        SimulationConfig {
            n_steps: base.n_steps,
            initial_price: base.initial_price,
            initial_x: base.initial_x,
            initial_y: base.initial_y,
            gbm_mu: base.gbm_mu,
            gbm_sigma,
            gbm_dt: base.gbm_dt,
            retail_arrival_rate,
            retail_mean_size,
            retail_size_sigma: base.retail_size_sigma,
            retail_buy_prob: base.retail_buy_prob,
            seed: Some(seed),
        }
    }
}
