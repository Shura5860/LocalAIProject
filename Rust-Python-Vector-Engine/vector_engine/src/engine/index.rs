use instant_distance::{Builder, HnswMap, Search};
use numpy::{PyReadonlyArray1, PyReadonlyArray2};
use pyo3::exceptions::{PyIOError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::storage::wal::{append_wal, WalEntry};
use crate::types::{normalize_vector, VectorPoint};

use std::collections::{HashMap, HashSet};
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Read, Write};
use std::sync::{Arc, RwLock};

#[derive(Default)]
pub struct InnerState {
    pub raw_vectors: Vec<VectorPoint>,
    pub ids: Vec<usize>,
    pub metadata_store: HashMap<usize, HashMap<String, String>>,
    pub inverted_index: HashMap<String, HashMap<String, HashSet<usize>>>,
    pub tombstone_ids: HashSet<usize>,
    pub hnsw_index: Option<HnswMap<VectorPoint, usize>>,
}

impl InnerState {
    fn remove_metadata_from_inverted(&mut self, id: usize) {
        if let Some(old_meta) = self.metadata_store.remove(&id) {
            for (k, v) in old_meta {
                let mut remove_val_key = false;
                if let Some(val_map) = self.inverted_index.get_mut(&k) {
                    if let Some(id_set) = val_map.get_mut(&v) {
                        id_set.remove(&id);
                        if id_set.is_empty() {
                            remove_val_key = true;
                        }
                    }
                    if remove_val_key {
                        val_map.remove(&v);
                    }
                }
                if self
                    .inverted_index
                    .get(&k)
                    .map(|m| m.is_empty())
                    .unwrap_or(false)
                {
                    self.inverted_index.remove(&k);
                }
            }
        }
    }

    fn upsert_vector(&mut self, id: usize, normalized_vec: Vec<f32>, meta: HashMap<String, String>) {
        // Remove any previous vector/metadata for the same ID to prevent duplicates or resurrection
        self.remove_metadata_from_inverted(id);
        if let Some(pos) = self.ids.iter().position(|&existing| existing == id) {
            self.raw_vectors[pos] = VectorPoint(normalized_vec);
        } else {
            self.raw_vectors.push(VectorPoint(normalized_vec));
            self.ids.push(id);
        }
        self.metadata_store.insert(id, meta.clone());
        for (k, v) in &meta {
            self.inverted_index
                .entry(k.clone())
                .or_insert_with(HashMap::new)
                .entry(v.clone())
                .or_insert_with(HashSet::new)
                .insert(id);
        }
        self.tombstone_ids.remove(&id);
    }

    fn rebuild_hnsw_live(&mut self) {
        let mut live_vecs = Vec::with_capacity(self.raw_vectors.len());
        let mut live_ids = Vec::with_capacity(self.ids.len());
        for (vec, &id) in self.raw_vectors.iter().zip(self.ids.iter()) {
            if !self.tombstone_ids.contains(&id) {
                live_vecs.push(vec.clone());
                live_ids.push(id);
            }
        }
        if live_vecs.is_empty() {
            self.hnsw_index = None;
        } else {
            let hnsw = Builder::default().build(live_vecs, live_ids);
            self.hnsw_index = Some(hnsw);
        }
    }
}

#[pyclass]
pub struct VectorIndex {
    state: Arc<RwLock<InnerState>>,
    wal_path: Arc<RwLock<Option<String>>>,
}

#[pymethods]
impl VectorIndex {
    #[new]
    pub fn new() -> Self {
        VectorIndex {
            state: Arc::new(RwLock::new(InnerState::default())),
            wal_path: Arc::new(RwLock::new(None)),
        }
    }

    pub fn enable_wal(&self, path: String) -> PyResult<()> {
        let mut wal_lock = self
            .wal_path
            .write()
            .map_err(|_| PyRuntimeError::new_err("WAL lock poisoned"))?;
        *wal_lock = Some(path);
        Ok(())
    }

    pub fn add_batch_with_metadata(
        &self,
        ids: Vec<usize>,
        vectors_array: PyReadonlyArray2<f32>,
        metadatas: Vec<HashMap<String, String>>,
    ) -> PyResult<()> {
        let array_view = vectors_array.as_array();
        if ids.len() != array_view.nrows() {
            return Err(PyValueError::new_err(format!(
                "ID sayısı ({}) ile vektör satır sayısı ({}) eşleşmiyor!",
                ids.len(),
                array_view.nrows()
            )));
        }

        // Consistent lock order: state FIRST, then wal_path
        let mut state = self
            .state
            .write()
            .map_err(|_| PyRuntimeError::new_err("State lock poisoned"))?;
        let wal_lock = self
            .wal_path
            .read()
            .map_err(|_| PyRuntimeError::new_err("WAL lock poisoned"))?;

        for (i, &id) in ids.iter().enumerate() {
            let row_view = array_view.row(i);
            let normalized_vec = if let Some(slice) = row_view.as_slice() {
                normalize_vector(slice)
            } else {
                let owned: Vec<f32> = row_view.iter().copied().collect();
                normalize_vector(&owned)
            };
            let meta = metadatas.get(i).cloned().unwrap_or_default();

            append_wal(
                &wal_lock,
                &WalEntry::Insert {
                    id,
                    vector: normalized_vec.clone(),
                    metadata: meta.clone(),
                },
            );

            state.upsert_vector(id, normalized_vec, meta);
        }
        Ok(())
    }

    pub fn build_hnsw_index(&self) -> PyResult<()> {
        let mut state = self
            .state
            .write()
            .map_err(|_| PyRuntimeError::new_err("State lock poisoned"))?;

        let live_count = state
            .ids
            .iter()
            .filter(|id| !state.tombstone_ids.contains(id))
            .count();
        if live_count == 0 {
            return Err(PyValueError::new_err("İndekslenecek veri yok!"));
        }

        state.rebuild_hnsw_live();
        Ok(())
    }

    pub fn vacuum(&self) -> PyResult<usize> {
        let mut state = self
            .state
            .write()
            .map_err(|_| PyRuntimeError::new_err("State lock poisoned"))?;

        if state.tombstone_ids.is_empty() {
            return Ok(0);
        }

        let tombstones = state.tombstone_ids.clone();
        let mut new_raw_vectors = Vec::with_capacity(state.raw_vectors.len());
        let mut new_ids = Vec::with_capacity(state.ids.len());
        let mut purged_count = 0usize;

        for (vec, &id) in state.raw_vectors.iter().zip(state.ids.iter()) {
            if !tombstones.contains(&id) {
                new_raw_vectors.push(vec.clone());
                new_ids.push(id);
            } else {
                purged_count += 1;
            }
        }

        state.raw_vectors = new_raw_vectors;
        state.ids = new_ids;
        state.tombstone_ids.clear();
        state.rebuild_hnsw_live();

        Ok(purged_count)
    }

    pub fn delete_id(&self, id: usize) -> PyResult<bool> {
        // Consistent lock order: state FIRST, then wal_path
        let mut state = self
            .state
            .write()
            .map_err(|_| PyRuntimeError::new_err("State lock poisoned"))?;
        let wal_lock = self
            .wal_path
            .read()
            .map_err(|_| PyRuntimeError::new_err("WAL lock poisoned"))?;

        let existed = state.ids.contains(&id) && !state.tombstone_ids.contains(&id);
        if !existed {
            return Ok(false);
        }

        append_wal(&wal_lock, &WalEntry::Delete { id });
        state.remove_metadata_from_inverted(id);
        state.tombstone_ids.insert(id);
        Ok(true)
    }

    pub fn update_id(
        &self,
        id: usize,
        new_vector_array: PyReadonlyArray1<f32>,
        new_metadata: HashMap<String, String>,
    ) -> PyResult<bool> {
        let normalized_vec = if let Some(vec_slice) = new_vector_array.as_slice().ok() {
            normalize_vector(vec_slice)
        } else {
            let owned: Vec<f32> = new_vector_array.as_array().iter().copied().collect();
            normalize_vector(&owned)
        };

        // Consistent lock order: state FIRST, then wal_path
        let mut state = self
            .state
            .write()
            .map_err(|_| PyRuntimeError::new_err("State lock poisoned"))?;
        let wal_lock = self
            .wal_path
            .read()
            .map_err(|_| PyRuntimeError::new_err("WAL lock poisoned"))?;

        append_wal(
            &wal_lock,
            &WalEntry::Insert {
                id,
                vector: normalized_vec.clone(),
                metadata: new_metadata.clone(),
            },
        );

        state.upsert_vector(id, normalized_vec, new_metadata);
        state.rebuild_hnsw_live();
        Ok(true)
    }

    #[pyo3(signature = (query_array, top_k, filter_key=None, filter_value=None, operator=None))]
    pub fn search_filtered(
        &self,
        query_array: PyReadonlyArray1<f32>,
        top_k: usize,
        filter_key: Option<String>,
        filter_value: Option<String>,
        operator: Option<String>,
    ) -> PyResult<Vec<(usize, f32, HashMap<String, String>)>> {
        if top_k == 0 {
            return Ok(Vec::new());
        }

        let state = self
            .state
            .read()
            .map_err(|_| PyRuntimeError::new_err("State lock poisoned"))?;
        let hnsw = match &state.hnsw_index {
            Some(index) => index,
            None => {
                return Err(PyValueError::new_err("İndeks henüz inşa edilmedi!"));
            }
        };

        let normalized_query = if let Ok(query_slice) = query_array.as_slice() {
            normalize_vector(query_slice)
        } else {
            let owned: Vec<f32> = query_array.as_array().iter().copied().collect();
            normalize_vector(&owned)
        };

        let query_point = VectorPoint(normalized_query);
        let mut search = Search::default();

        let op = operator.unwrap_or_else(|| "==".to_string());
        let mut allowed_ids: Option<HashSet<usize>> = None;

        if let (Some(k), Some(v)) = (&filter_key, &filter_value) {
            if op == "==" {
                if let Some(val_map) = state.inverted_index.get(k) {
                    if let Some(id_set) = val_map.get(v) {
                        let valid: HashSet<usize> = id_set
                            .iter()
                            .cloned()
                            .filter(|id| !state.tombstone_ids.contains(id))
                            .collect();
                        if valid.is_empty() {
                            return Ok(Vec::new());
                        }
                        allowed_ids = Some(valid);
                    } else {
                        return Ok(Vec::new());
                    }
                } else {
                    return Ok(Vec::new());
                }
            }
        }

        let mut filtered_results = Vec::new();
        let mut seen_ids = HashSet::new();

        for item in hnsw.search(&query_point, &mut search) {
            let id = *item.value;

            if state.tombstone_ids.contains(&id) || !seen_ids.insert(id) {
                continue;
            }

            if let Some(ref valid_set) = allowed_ids {
                if !valid_set.contains(&id) {
                    continue;
                }
            }

            let distance = item.distance;
            let empty_meta = HashMap::new();
            let meta = state.metadata_store.get(&id).unwrap_or(&empty_meta);

            if let (Some(k), Some(v)) = (&filter_key, &filter_value) {
                if op != "==" {
                    if let Some(actual_val) = meta.get(k) {
                        if let (Ok(actual_num), Ok(target_num)) =
                            (actual_val.parse::<f64>(), v.parse::<f64>())
                        {
                            let is_match = match op.as_str() {
                                ">=" => actual_num >= target_num,
                                "<=" => actual_num <= target_num,
                                ">" => actual_num > target_num,
                                "<" => actual_num < target_num,
                                _ => false,
                            };
                            if !is_match {
                                continue;
                            }
                        } else {
                            continue;
                        }
                    } else {
                        continue;
                    }
                }
            }

            filtered_results.push((id, distance, meta.clone()));

            if filtered_results.len() >= top_k {
                break;
            }
        }

        Ok(filtered_results)
    }

    pub fn save_to_disk(&self, file_path: String) -> PyResult<()> {
        let state = self
            .state
            .read()
            .map_err(|_| PyRuntimeError::new_err("State lock poisoned"))?;

        let dump = (
            &state.raw_vectors,
            &state.ids,
            &state.metadata_store,
            &state.inverted_index,
            &state.tombstone_ids,
        );

        let encoded = bincode::serialize(&dump)
            .map_err(|e| PyIOError::new_err(e.to_string()))?;

        // Atomic write: temp file -> sync_all -> rename
        let tmp_path = format!("{}.tmp", file_path);
        {
            let mut file = File::create(&tmp_path)?;
            file.write_all(&encoded)?;
            file.sync_all()?;
        }
        fs::rename(&tmp_path, &file_path)?;

        let wal_lock = self
            .wal_path
            .read()
            .map_err(|_| PyRuntimeError::new_err("WAL lock poisoned"))?;
        if let Some(ref path) = *wal_lock {
            let _ = File::create(path);
        }

        Ok(())
    }

    pub fn load_from_disk(&self, file_path: String) -> PyResult<()> {
        let mut state = self
            .state
            .write()
            .map_err(|_| PyRuntimeError::new_err("State lock poisoned"))?;

        // Reset state before loading snapshot + WAL to avoid duplicating entries
        *state = InnerState::default();

        if let Ok(mut file) = File::open(&file_path) {
            let mut buffer = Vec::new();
            if file.read_to_end(&mut buffer).is_ok() {
                if let Ok((raw_vectors, ids, metadata_store, inverted_index, tombstone_ids)) =
                    bincode::deserialize::<(
                        Vec<VectorPoint>,
                        Vec<usize>,
                        HashMap<usize, HashMap<String, String>>,
                        HashMap<String, HashMap<String, HashSet<usize>>>,
                        HashSet<usize>,
                    )>(&buffer)
                {
                    state.raw_vectors = raw_vectors;
                    state.ids = ids;
                    state.metadata_store = metadata_store;
                    state.inverted_index = inverted_index;
                    state.tombstone_ids = tombstone_ids;
                }
            }
        }

        let wal_lock = self
            .wal_path
            .read()
            .map_err(|_| PyRuntimeError::new_err("WAL lock poisoned"))?;
        if let Some(ref path) = *wal_lock {
            if let Ok(wal_file) = File::open(path) {
                let reader = BufReader::new(wal_file);
                for line in reader.lines().flatten() {
                    if let Ok(entry) = serde_json::from_str::<WalEntry>(&line) {
                        match entry {
                            WalEntry::Insert {
                                id,
                                vector,
                                metadata,
                            } => {
                                state.upsert_vector(id, vector, metadata);
                            }
                            WalEntry::Delete { id } => {
                                if state.ids.contains(&id) {
                                    state.remove_metadata_from_inverted(id);
                                    state.tombstone_ids.insert(id);
                                }
                            }
                        }
                    }
                }
            }
        }

        state.rebuild_hnsw_live();
        Ok(())
    }

    pub fn len(&self) -> PyResult<usize> {
        let state = self
            .state
            .read()
            .map_err(|_| PyRuntimeError::new_err("State lock poisoned"))?;
        let live_count = state
            .ids
            .iter()
            .filter(|id| !state.tombstone_ids.contains(id))
            .count();
        Ok(live_count)
    }

    pub fn max_id(&self) -> PyResult<Option<usize>> {
        let state = self
            .state
            .read()
            .map_err(|_| PyRuntimeError::new_err("State lock poisoned"))?;
        Ok(state.ids.iter().copied().max())
    }
}
