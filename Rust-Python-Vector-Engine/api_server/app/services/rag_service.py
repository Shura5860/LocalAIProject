import os
import re
import math
import json
from collections import defaultdict
from typing import List, Dict, Optional, Tuple, Any
import numpy as np

from api_server.app.core.config import db, allocate_doc_ids, BM25_FILE
from api_server.app.services.llm_bridge import RustLLMBridge


class RagService:
    """
    RAG 2.0: Hibrit Arama (Dense Vektör HNSW + Sparse BM25/TF-IDF)
    ve Reciprocal Rank Fusion (RRF) destekli yeni nesil yerel RAG motoru.
    """
    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.embedding_model_name = model_name
        self._embedder = None
        self.llm_bridge = RustLLMBridge()

        # Sparse Inverted Index (Doküman Metinleri & Anahtar Kelime Haritası)
        self._doc_store: Dict[int, Dict[str, Any]] = {}
        self._inverted_index: Dict[str, Dict[int, int]] = defaultdict(dict)  # term -> {doc_id: term_frequency}
        self._doc_lengths: Dict[int, int] = {}
        self._avg_doc_len: float = 0.0

    @property
    def embedder(self):
        if self._embedder is None:
            if os.environ.get("TESTING", "0") == "1":
                # Test ortamında model indirmesini atla
                class DummyEmbedder:
                    _STOP = {"ve", "ile", "bir", "bu", "su", "ben", "sen", "nasıl", "nedir", "ne", "için", "çok", "mi", "mı", "mu", "mü", "the", "and", "is", "of", "to", "in", "a"}

                    def _vec_for_text(self, s: str) -> np.ndarray:
                        import zlib
                        vec = np.zeros(384, dtype=np.float32)
                        tokens = set(t for t in re.findall(r"[\w\d]+", str(s).lower()) if t not in self._STOP and len(t) > 1)
                        for tok in tokens:
                            h = zlib.crc32(tok.encode("utf-8"))
                            vec[h % 384] += 1.0 if (h & 1) else -1.0
                            for i in range(max(0, len(tok) - 3)):
                                gh = zlib.crc32(tok[i:i+4].encode("utf-8"))
                                vec[gh % 384] += 0.8 if (gh & 1) else -0.8
                        norm = float(np.linalg.norm(vec))
                        return (vec / norm) if norm > 0.0 else np.full(384, 0.05, dtype=np.float32)

                    def encode(self, texts, convert_to_numpy=True):
                        if isinstance(texts, list):
                            return np.vstack([self._vec_for_text(t) for t in texts]).astype(np.float32)
                        return self._vec_for_text(texts)
                self._embedder = DummyEmbedder()
            else:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer(self.embedding_model_name)
        return self._embedder

    def _tokenize(self, text: str) -> List[str]:
        """Metni küçük harfli terimlere ayıklar."""
        return re.findall(r"[\w\d]+", text.lower())

    @staticmethod
    def chunk_code(content: str, filename: str = "", max_chunk_lines: int = 50) -> List[Dict[str, Any]]:
        """
        Yapı-Farkındalıklı (AST/Sözdizimi) Akıllı Kod Bölücü.
        Fonksiyon, sınıf, struct ve impl sınırlarını tespit eder; dosya ve kapsam
        metadata'sını koruyarak semantik bütünlüğü sağlar.
        """
        lines = content.splitlines()
        if not lines:
            return []

        chunks = []
        current_chunk_lines = []
        current_scope = "module"
        start_line = 1

        boundary_pattern = re.compile(
            r"^(?:pub\s+)?(?:async\s+)?(?:def\s+|class\s+|fn\s+|impl\b|struct\s+|enum\s+|trait\s+|function\s+|interface\s+|#+\s+)"
        )

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            is_boundary = bool(boundary_pattern.match(stripped))

            if is_boundary and len(current_chunk_lines) >= 15:
                chunk_text = "\n".join(current_chunk_lines)
                chunks.append({
                    "text": chunk_text,
                    "filename": filename,
                    "scope": current_scope,
                    "start_line": start_line,
                    "end_line": i - 1
                })
                current_chunk_lines = []
                start_line = i
                current_scope = stripped[:50]
            elif len(current_chunk_lines) >= max_chunk_lines:
                chunk_text = "\n".join(current_chunk_lines)
                chunks.append({
                    "text": chunk_text,
                    "filename": filename,
                    "scope": current_scope,
                    "start_line": start_line,
                    "end_line": i - 1
                })
                current_chunk_lines = []
                start_line = i

            current_chunk_lines.append(line)
            if is_boundary and len(current_chunk_lines) == 1:
                current_scope = stripped[:50]

        if current_chunk_lines:
            chunks.append({
                "text": "\n".join(current_chunk_lines),
                "filename": filename,
                "scope": current_scope,
                "start_line": start_line,
                "end_line": len(lines)
            })

        return chunks

    def ingest_file(self, file_path: str) -> int:
        """Belirtilen kaynak kod dosyasını akıllı AST parçalama ile indeksler."""
        if not os.path.exists(file_path):
            return 0
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        filename = os.path.basename(file_path)
        chunks = self.chunk_code(content, filename=filename)
        texts = [c["text"] for c in chunks]
        metas = [
            {"filename": c["filename"], "scope": c["scope"], "lines": f"{c['start_line']}-{c['end_line']}"}
            for c in chunks
        ]
        return self.ingest_documents(texts, metas)

    def ingest_documents(self, documents: List[str], metadatas: Optional[List[Dict[str, str]]] = None) -> int:
        if not documents:
            return 0

        embeddings = self.embedder.encode(documents, convert_to_numpy=True).astype(np.float32)

        ids = allocate_doc_ids(len(documents))

        prepared_metas = []
        for i, text in enumerate(documents):
            raw_meta = metadatas[i].copy() if (metadatas and i < len(metadatas)) else {}
            raw_meta["text"] = text
            meta = {str(k): str(v) for k, v in raw_meta.items()}
            prepared_metas.append(meta)

            # Sparse Index Güncellemesi (BM25 / Keyword)
            doc_id = ids[i]
            self._doc_store[doc_id] = meta
            tokens = self._tokenize(text)
            self._doc_lengths[doc_id] = len(tokens)

            tf_map: Dict[str, int] = defaultdict(int)
            for t in tokens:
                tf_map[t] += 1
            for t, count in tf_map.items():
                self._inverted_index[t][doc_id] = count

        if self._doc_lengths:
            self._avg_doc_len = sum(self._doc_lengths.values()) / len(self._doc_lengths)

        db.add_batch_with_metadata(ids, embeddings, prepared_metas)
        db.build_hnsw_index()
        if os.environ.get("TESTING", "0") != "1":
            self.save_sparse_index(BM25_FILE)
        return len(documents)

    def remove_from_sparse_index(self, doc_id: int) -> None:
        """Silinen bir dokümanı BM25 seyrek indeksinden temizler."""
        self._doc_store.pop(doc_id, None)
        self._doc_lengths.pop(doc_id, None)
        empty_terms = []
        for term, postings in self._inverted_index.items():
            postings.pop(doc_id, None)
            if not postings:
                empty_terms.append(term)
        for term in empty_terms:
            self._inverted_index.pop(term, None)
        if self._doc_lengths:
            self._avg_doc_len = sum(self._doc_lengths.values()) / len(self._doc_lengths)
        else:
            self._avg_doc_len = 0.0

    def save_sparse_index(self, file_path: str = BM25_FILE) -> None:
        """BM25 seyrek indeksini ve doküman metin deposunu diske kalıcı olarak yazar."""
        try:
            payload = {
                "doc_store": {str(k): v for k, v in self._doc_store.items()},
                "inverted_index": {term: {str(k): v for k, v in postings.items()} for term, postings in self._inverted_index.items()},
                "doc_lengths": {str(k): v for k, v in self._doc_lengths.items()},
                "avg_doc_len": self._avg_doc_len
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            pass

    def load_sparse_index(self, file_path: str = BM25_FILE) -> None:
        """BM25 seyrek indeksini diskten belleğe geri yükler."""
        if not os.path.exists(file_path):
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self._doc_store = {int(k): v for k, v in payload.get("doc_store", {}).items()}
            self._doc_lengths = {int(k): int(v) for k, v in payload.get("doc_lengths", {}).items()}
            self._avg_doc_len = float(payload.get("avg_doc_len", 0.0))
            inv = defaultdict(dict)
            for term, postings in payload.get("inverted_index", {}).items():
                inv[term] = {int(k): int(v) for k, v in postings.items()}
            self._inverted_index = inv
        except Exception:
            pass

    def _sparse_bm25_search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Basitleştirilmiş Okapi BM25 Sparse Skorlama."""
        q_tokens = self._tokenize(query)
        if not q_tokens or not self._doc_lengths:
            return []

        scores: Dict[int, float] = defaultdict(float)
        k1 = 1.5
        b = 0.75
        n_docs = len(self._doc_lengths)

        for term in q_tokens:
            posting = self._inverted_index.get(term)
            if not posting:
                continue

            df = len(posting)
            idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))

            for doc_id, tf in posting.items():
                doc_len = self._doc_lengths.get(doc_id, 1)
                norm = 1.0 - b + b * (doc_len / (self._avg_doc_len or 1.0))
                term_score = idf * (tf * (k1 + 1.0)) / (tf + k1 * norm)
                scores[doc_id] += term_score

        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_docs[:top_k]

    def query(
        self,
        user_query: str,
        top_k: int = 3,
        filter_key: Optional[str] = None,
        filter_value: Optional[str] = None,
        mode: str = "hybrid",
        max_tokens: int = 256
    ) -> Dict:
        if db.len() == 0:
            return {
                "query": user_query,
                "answer": "Veritabanında henüz indekslenmiş belge bulunmuyor. Lütfen önce `/rag/ingest` ile belge yükleyin.",
                "retrieved_chunks": [],
                "llm_engine": "Rust-LLM-Engine (AVX2/FMA SIMD CPU)"
            }

        # 1. Dense (Semantik HNSW Vektör) Araması
        query_vector = self.embedder.encode(user_query, convert_to_numpy=True).astype(np.float32)
        raw_dense = db.search_filtered(
            query_vector,
            top_k=top_k * 2,
            filter_key=filter_key,
            filter_value=filter_value,
            operator="==" if filter_key else None
        )

        dense_ranked_ids = [doc_id for doc_id, _, _ in raw_dense]
        dense_meta_map = {doc_id: (dist, meta) for doc_id, dist, meta in raw_dense}

        # 2. Sparse (BM25 Anahtar Kelime) Araması
        raw_sparse = self._sparse_bm25_search(user_query, top_k=top_k * 2)
        if filter_key and filter_value is not None:
            raw_sparse = [
                (doc_id, sc)
                for doc_id, sc in raw_sparse
                if str(self._doc_store.get(doc_id, {}).get(filter_key, "")) == str(filter_value)
            ]
        sparse_ranked_ids = [doc_id for doc_id, _ in raw_sparse]

        # 3. Reciprocal Rank Fusion (RRF) - Skor Füzyonu
        # RRF Skoru = 1 / (k + rank_dense) + 1 / (k + rank_sparse)
        rrf_k = 60.0
        rrf_scores: Dict[int, float] = defaultdict(float)

        for rank, doc_id in enumerate(dense_ranked_ids):
            rrf_scores[doc_id] += 1.0 / (rrf_k + rank + 1)

        for rank, doc_id in enumerate(sparse_ranked_ids):
            rrf_scores[doc_id] += 1.0 / (rrf_k + rank + 1)

        # En yüksek RRF skoruna göre sırala
        fused_ranking = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        retrieved_chunks = []
        context_parts = []

        for doc_id, score in fused_ranking:
            meta = dense_meta_map.get(doc_id, (0.0, self._doc_store.get(doc_id, {})))[1]
            dist = dense_meta_map.get(doc_id, (1.0 - score, {}))[0]
            text = meta.get("text", "")

            retrieved_chunks.append({
                "id": doc_id,
                "distance": float(dist),
                "rrf_score": round(float(score), 5),
                "text": text,
                "metadata": meta
            })
            if text:
                context_parts.append(f"- {text}")

        context_str = "\n".join(context_parts) if context_parts else "İlgili belge bulunamadı."

        from api_server.app.services.memory_service import memory_service
        memory_ctx = memory_service.build_memory_prompt(user_query)

        prompt = (
            f"<|im_start|>system\n"
            f"Sen yüksek performanslı bir yapay zeka asistanısın. Aşağıdaki bağlam ve kullanıcı hafıza bilgilerini dikkatle incele ve kullanıcının sorusunu bu bilgilere dayanarak yanıtla. Eğer cevap bağlamda yoksa uydurma yapma, bunu açıkça belirt.\n\n"
            f"{memory_ctx}\n"
            f"BAĞLAM:\n{context_str}<|im_end|>\n"
            f"<|im_start|>user\n"
            f"{user_query}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        answer = self.llm_bridge.generate(prompt=prompt, max_tokens=max_tokens)

        return {
            "query": user_query,
            "answer": answer,
            "retrieved_chunks": retrieved_chunks,
            "llm_engine": "Rust-LLM-Engine (AVX2/FMA SIMD CPU)",
            "retrieval_mode": "hybrid_rrf_bm25_hnsw"
        }

    @staticmethod
    def generate_repo_map(workspace_path: Optional[str] = None, max_files: int = 60) -> str:
        """
        AST ve Sözdizimi Tabanlı Token-Etkin Repo Haritası (Aider stili Repo Map).
        Python ve Rust kaynak kodlarının gövdelerini atmadan sadece class, def, struct, fn
        imzalarını derleyerek LLM'e minimum tokenle projenin bütünsel mimarisini sunar.
        """
        import ast

        from api_server.app.tools.devops import _get_base_workspace
        ws = workspace_path or _get_base_workspace()
        if not os.path.exists(ws):
            return "Çalışma alanı bulunamadı."

        repo_tree = []
        file_count = 0

        # Taranmayacak kalabalık dizinler
        ignore_dirs = {".git", ".venv", "__pycache__", "target", "node_modules", "dist", "build", ".idea"}

        for root, dirs, files in os.walk(ws):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
            for file in sorted(files):
                if file_count >= max_files:
                    break
                if not (file.endswith(".py") or file.endswith(".rs")):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, ws)
                file_count += 1

                file_summary = []
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()

                    if file.endswith(".py"):
                        try:
                            tree = ast.parse(content)
                            for node in tree.body:
                                if isinstance(node, ast.ClassDef):
                                    bases = [b.id for b in node.bases if hasattr(b, "id")]
                                    base_str = f"({', '.join(bases)})" if bases else ""
                                    file_summary.append(f"  class {node.name}{base_str}:")
                                    for sub in node.body:
                                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                            args = [a.arg for a in sub.args.args if a.arg != "self"]
                                            file_summary.append(f"    def {sub.name}({', '.join(args[:4])})")
                                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    args = [a.arg for a in node.args.args]
                                    file_summary.append(f"  def {node.name}({', '.join(args[:4])})")
                        except Exception:
                            for line in content.splitlines()[:60]:
                                if line.strip().startswith(("def ", "class ")):
                                    file_summary.append(f"  {line.strip()[:60]}")

                    elif file.endswith(".rs"):
                        for line in content.splitlines():
                            st = line.strip()
                            if st.startswith(("pub fn ", "fn ", "pub struct ", "struct ", "pub enum ", "enum ", "impl ", "pub trait ", "trait ", "pub mod ", "mod ")):
                                sig = st.split("{")[0].strip()
                                file_summary.append(f"  {sig[:75]}")
                except Exception:
                    pass

                if file_summary:
                    repo_tree.append(f"📄 {rel_path}\n" + "\n".join(file_summary[:12]))

        if not repo_tree:
            return "Haritalandırılacak kaynak kod dosyası bulunamadı."

        header = f"# 🗺️ PROJE MİMARİ HARİTASI (Toplam {len(repo_tree)} Kaynak Dosya)\n"
        return header + "\n\n".join(repo_tree)

    @staticmethod
    def extract_call_graph(content: str, filename: str = "") -> Dict[str, List[str]]:
        """
        Canlı AST Çağrı Grafiği (Call-Graph Indexer).
        Fonksiyonların birbirini nasıl çağırdığını (caller -> callee) analiz eder.
        """
        import ast
        import re

        graph = {}

        if filename.endswith(".py") or "def " in content:
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        caller = node.name
                        callees = set()
                        for sub in ast.walk(node):
                            if isinstance(sub, ast.Call):
                                if isinstance(sub.func, ast.Name):
                                    callees.add(sub.func.id)
                                elif isinstance(sub.func, ast.Attribute):
                                    callees.add(sub.func.attr)
                        graph[caller] = sorted(list(callees))
                if graph:
                    return graph
            except Exception:
                pass

        # Rust veya Fallback Regex
        current_fn = None
        for line in content.splitlines():
            fn_match = re.search(r"(?:pub\s+)?fn\s+([a-zA-Z0-9_]+)\s*\(", line)
            if fn_match:
                current_fn = fn_match.group(1)
                graph[current_fn] = []
            elif current_fn:
                calls = re.findall(r"([a-zA-Z0-9_]+)\s*\(", line)
                for call in calls:
                    if call not in ("if", "for", "while", "match", "Some", "Ok", "Err", "vec", "println", current_fn):
                        if call not in graph[current_fn]:
                            graph[current_fn].append(call)

        return graph


rag_service = RagService()
