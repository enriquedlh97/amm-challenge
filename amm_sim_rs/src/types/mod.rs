//! Core types for the simulation engine.

pub mod wad;
pub mod trade_info;
pub mod config;
pub mod result;

pub use wad::Wad;
pub use trade_info::TradeInfo;
pub use config::SimulationConfig;
pub use result::{LightweightSimResult, LightweightStepResult, BatchSimulationResult};
