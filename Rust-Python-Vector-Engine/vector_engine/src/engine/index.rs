use instant_distance::{Builder, HnswMap, Search};
use numpy::{PyReadonlyArray1, PyReadonlyArray2};
use pyo3::prelude::*;

use crate::storage::wal::{append_wal, WalEntry};
use crate::types::{normalize_vector, VectorPoint};

use std::collections::{HashMap, HashSet};
use std::fs::File;
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
        let mut wal_lock = self.wal_path.write().unwrap();
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
        let mut state = self.state.write().unwrap();
        let wal_lock = self.wal_path.read().unwrap();

        for (i, &id) in ids.iter().enumerate() {
            if let Some(row) = array_view.row(i).as_slice() {
                let normalized_vec = normalize_vector(row);
                let meta = metadatas.get(i).cloned().unwrap_or_default();

                append_wal(
                    &wal_lock,
                    &WalEntry::Insert {
                        id,
                        vector: normalized_vec.clone(),
                        metadata: meta.clone(),
                    },
                );

                state.raw_vectors.push(VectorPoint(normalized_vec));
                state.ids.push(id);
                state.metadata_store.insert(id, meta.clone());

                for (k, v) in &meta {
                    state
                        .inverted_index
                        .entry(k.clone())
                        .or_insert_with(HashMap::new)
                        .entry(v.clone())
                        .or_insert_with(HashSet::new)
                        .insert(id);
                }

                state.tombstone_ids.remove(&id);
            }
        }
        Ok(())
    }

    pub fn build_hnsw_index(&self) -> PyResult<()> {
        let mut state = self.state.write().unwrap();

        if state.raw_vectors.is_empty() {
            return Err(pyo3::exceptions::PyValueError::new_err("İndekslenecek veri yok!"));
        }

        let hnsw = Builder::default().build(state.raw_vectors.clone(), state.ids.clone());
        state.hnsw_index = Some(hnsw);

        Ok(())
    }

    pub fn vacuum(&self) -> PyResult<usize> {
        let mut state = self.state.write().unwrap();
        let tombstones = state.tombstone_ids.clone();

        if tombstones.is_empty() {
            return Ok(0);
        }

        let mut new_raw_vectors = Vec::new();
        let mut new_ids = Vec::new();

        for (vec, &id) in state.raw_vectors.iter().zip(state.ids.iter()) {
            if !tombstones.contains(&id) {
                new_raw_vectors.push(vec.clone());
                new_ids.push(id);
            }
        }

        let purged_count = tombstones.len();

        state.raw_vectors = new_raw_vectors;
        state.ids = new_ids;
        state.tombstone_ids.clear();

        if !state.raw_vectors.is_empty() {
            let hnsw = Builder::default().build(state.raw_vectors.clone(), state.ids.clone());
            state.hnsw_index = Some(hnsw);
        } else {
            state.hnsw_index = None;
        }

        Ok(purged_count)
    }

    pub fn delete_id(&self, id: usize) -> bool {
        let wal_lock = self.wal_path.read().unwrap();
        append_wal(&wal_lock, &WalEntry::Delete { id });

        let mut state = self.state.write().unwrap();

        if let Some(meta) = state.metadata_store.remove(&id) {
            for (k, v) in meta {
                if let Some(val_map) = state.inverted_index.get_mut(&k) {
                    if let Some(id_set) = val_map.get_mut(&v) {
                        id_set.remove(&id);
                    }
                }
            }
            state.tombstone_ids.insert(id);
            true
        } else if state.ids.contains(&id) {
            state.tombstone_ids.insert(id);
            true
        } else {
            false
        }
    }

    pub fn update_id(
        &self,
        id: usize,
        new_vector_array: PyReadonlyArray1<f32>,
        new_metadata: HashMap<String, String>,
    ) -> PyResult<bool> {
        self.delete_id(id);

        let vec_slice = new_vector_array
            .as_slice()
            .map_err(|_| pyo3::exceptions::PyValueError::new_err("Vektör okunamadı!"))?;

        let normalized_vec = normalize_vector(vec_slice);

        let wal_lock = self.wal_path.read().unwrap();
        append_wal(
            &wal_lock,
            &WalEntry::Insert {
                id,
                vector: normalized_vec.clone(),
                metadata: new_metadata.clone(),
            },
        );

        {
            let mut state = self.state.write().unwrap();
            state.raw_vectors.push(VectorPoint(normalized_vec));
            state.ids.push(id);
            state.metadata_store.insert(id, new_metadata.clone());

            for (k, v) in &new_metadata {
                state
                    .inverted_index
                    .entry(k.clone())
                    .or_insert_with(HashMap::new)
                    .entry(v.clone())
                    .or_insert_with(HashSet::new)
                    .insert(id);
            }

            state.tombstone_ids.remove(&id);
        }

        self.build_hnsw_index()?;
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
        let state = self.state.read().unwrap();
        let hnsw = match &state.hnsw_index {
            Some(index) => index,
            None => {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "İndeks henüz inşa edilmedi!",
                ))
            }
        };

        let query_slice = query_array
            .as_slice()
            .map_err(|_| pyo3::exceptions::PyValueError::new_err("Array sürekli değil!"))?;

        let normalized_query = normalize_vector(query_slice);
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

        for item in hnsw.search(&query_point, &mut search) {
            let id = *item.value;

            if state.tombstone_ids.contains(&id) {
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
                        if let (Ok(actual_num), Ok(target_num)) = (actual_val.parse::<f64>(), v.parse::<f64>()) {
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
        let state = self.state.read().unwrap();

        let dump = (
            &state.raw_vectors,
            &state.ids,
            &state.metadata_store,
            &state.inverted_index,
            &state.tombstone_ids,
        );

        let encoded = bincode::serialize(&dump)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        let mut file = File::create(&file_path)?;
        file.write_all(&encoded)?;

        let wal_lock = self.wal_path.read().unwrap();
        if let Some(ref path) = *wal_lock {
            let _ = File::create(path);
        }

        Ok(())
    }

    pub fn load_from_disk(&self, file_path: String) -> PyResult<()> {
        let mut state = self.state.write().unwrap();

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

        let wal_lock = self.wal_path.read().unwrap();
        if let Some(ref path) = *wal_lock {
            if let Ok(wal_file) = File::open(path) {
                let reader = BufReader::new(wal_file);
                for line in reader.lines().flatten() {
                    if let Ok(entry) = serde_json::from_str::<WalEntry>(&line) {
                        match entry {
                            WalEntry::Insert { id, vector, metadata } => {
                                state.raw_vectors.push(VectorPoint(vector));
                                state.ids.push(id);
                                state.metadata_store.insert(id, metadata.clone());

                                for (k, v) in &metadata {
                                    state
                                        .inverted_index
                                        .entry(k.clone())
                                        .or_insert_with(HashMap::new)
                                        .entry(v.clone())
                                        .or_insert_with(HashSet::new)
                                        .insert(id);
                                }
                                state.tombstone_ids.remove(&id);
                            }
                            WalEntry::Delete { id } => {
                                if let Some(meta) = state.metadata_store.remove(&id) {
                                    for (k, v) in meta {
                                        if let Some(val_map) = state.inverted_index.get_mut(&k) {
                                            if let Some(id_set) = val_map.get_mut(&v) {
                                                id_set.remove(&id);
                                            }
                                        }
                                    }
                                }
                                state.tombstone_ids.insert(id);
                            }
                        }
                    }
                }
            }
        }

        if !state.raw_vectors.is_empty() {
            let hnsw = Builder::default().build(state.raw_vectors.clone(), state.ids.clone());
            state.hnsw_index = Some(hnsw);
        }

        Ok(())
    }

    pub fn len(&self) -> usize {
        let state = self.state.read().unwrap();
        state.ids.len() - state.tombstone_ids.len()
    }
}
