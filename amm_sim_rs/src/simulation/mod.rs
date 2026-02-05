//! Simulation engine and parallel runner.

pub mod engine;
pub mod runner;

pub use engine::SimulationEngine;
pub use runner::{run_simulations_parallel, SimulationBatchConfig};
