use instant_distance::Point;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VectorPoint(pub Vec<f32>);

pub fn normalize_vector(vec: &[f32]) -> Vec<f32> {
    let clean: Vec<f32> = vec
        .iter()
        .map(|&x| if x.is_finite() { x } else { 0.0 })
        .collect();
    // Use f64 accumulator to prevent f32 overflow on large components
    let norm_sq: f64 = clean.iter().map(|&x| (x as f64) * (x as f64)).sum();
    let norm = norm_sq.sqrt();
    if norm == 0.0 || !norm.is_finite() {
        clean
    } else {
        clean.iter().map(|&x| ((x as f64) / norm) as f32).collect()
    }
}

impl Point for VectorPoint {
    fn distance(&self, other: &Self) -> f32 {
        let sum: f64 = self
            .0
            .iter()
            .zip(other.0.iter())
            .map(|(&a, &b)| {
                let da = if a.is_finite() { a as f64 } else { 0.0 };
                let db = if b.is_finite() { b as f64 } else { 0.0 };
                let diff = da - db;
                diff * diff
            })
            .sum();
        if sum.is_finite() {
            sum as f32
        } else {
            f32::MAX
        }
    }
}
