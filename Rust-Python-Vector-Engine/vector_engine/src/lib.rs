pub mod engine;
pub mod storage;
pub mod types;

use engine::index::VectorIndex;
use pyo3::prelude::*;

#[pymodule]
fn vector_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<VectorIndex>()?;
    Ok(())
}