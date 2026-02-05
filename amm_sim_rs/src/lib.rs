//! AMM Simulation Engine in Rust
//!
//! High-performance simulation engine for AMM fee algorithm competition.
//! Eliminates Python interpreter overhead in the hot path by implementing
//! the simulation loop, AMM math, and market actors in Rust.

pub mod types;
pub mod evm;
pub mod amm;
pub mod market;
pub mod simulation;

use pyo3::prelude::*;

use crate::simulation::runner::{run_simulations_parallel, SimulationBatchConfig};
use crate::types::config::SimulationConfig;
use crate::types::result::{BatchSimulationResult, LightweightSimResult};

/// Run multiple simulations in parallel using Rust engine.
///
/// # Arguments
/// * `submission_bytecode` - Compiled bytecode for the submission strategy
/// * `baseline_bytecode` - Compiled bytecode for the baseline strategy
/// * `configs` - List of simulation configurations (one per simulation)
/// * `n_workers` - Number of parallel workers (0 = auto-detect)
///
/// # Returns
/// BatchSimulationResult containing all simulation results
#[pyfunction]
#[pyo3(signature = (submission_bytecode, baseline_bytecode, configs, n_workers = 0))]
fn run_batch(
    submission_bytecode: Vec<u8>,
    baseline_bytecode: Vec<u8>,
    configs: Vec<SimulationConfig>,
    n_workers: usize,
) -> PyResult<BatchSimulationResult> {
    let batch_config = SimulationBatchConfig {
        submission_bytecode,
        baseline_bytecode,
        configs,
        n_workers: if n_workers == 0 { None } else { Some(n_workers) },
    };

    run_simulations_parallel(batch_config)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
}

/// Run a single simulation and return lightweight result.
#[pyfunction]
fn run_single(
    submission_bytecode: Vec<u8>,
    baseline_bytecode: Vec<u8>,
    config: SimulationConfig,
) -> PyResult<LightweightSimResult> {
    use crate::simulation::engine::SimulationEngine;
    use crate::evm::strategy::EVMStrategy;

    let submission = EVMStrategy::new(submission_bytecode, "Submission".to_string())
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    let baseline = EVMStrategy::new(baseline_bytecode, "Baseline".to_string())
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let mut engine = SimulationEngine::new(config);
    engine.run(submission, baseline)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
}

/// Python module definition
#[pymodule]
fn amm_sim_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(run_batch, m)?)?;
    m.add_function(wrap_pyfunction!(run_single, m)?)?;
    m.add_class::<SimulationConfig>()?;
    m.add_class::<LightweightSimResult>()?;
    m.add_class::<BatchSimulationResult>()?;
    Ok(())
}
