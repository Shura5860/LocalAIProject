import os
import json
import uuid
import difflib
import datetime
import threading
from typing import Dict, Any, List, Optional

from api_server.app.tools.devops import _validate_safe_path, _get_base_workspace


FILE_EDIT_TOOLS = {"write_file", "apply_diff", "apply_multi_diff"}


def _compute_file_diff(rel_path: str, old_text: str, new_text: str, is_new_file: bool = False) -> Dict[str, Any]:
    """İki metin arasındaki satır bazlı unified diff ve yapısal satır listesini üretir."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff_iter = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{rel_path}" if not is_new_file else "/dev/null",
            tofile=f"b/{rel_path}",
            n=3,
        )
    )

    hunks: List[Dict[str, Any]] = []
    additions = 0
    deletions = 0
    old_line_no = 0
    new_line_no = 0

    for line in diff_iter:
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            # Parse @@ -old_start,old_count +new_start,new_count @@
            try:
                header_part = line.split("@@")[1].strip()
                parts = header_part.split(" ")
                old_start = int(parts[0].split(",")[0].lstrip("-"))
                new_start = int(parts[1].split(",")[0].lstrip("+"))
                old_line_no = old_start
                new_line_no = new_start
            except Exception:
                pass
            hunks.append({
                "type": "header",
                "old_line": None,
                "new_line": None,
                "text": line.rstrip("\r\n"),
            })
        elif line.startswith("+"):
            additions += 1
            hunks.append({
                "type": "add",
                "old_line": None,
                "new_line": new_line_no,
                "text": line[1:].rstrip("\r\n"),
            })
            new_line_no += 1
        elif line.startswith("-"):
            deletions += 1
            hunks.append({
                "type": "del",
                "old_line": old_line_no,
                "new_line": None,
                "text": line[1:].rstrip("\r\n"),
            })
            old_line_no += 1
        else:
            content = line[1:] if line.startswith(" ") else line
            hunks.append({
                "type": "context",
                "old_line": old_line_no,
                "new_line": new_line_no,
                "text": content.rstrip("\r\n"),
            })
            old_line_no += 1
            new_line_no += 1

    return {
        "path": rel_path,
        "is_new_file": is_new_file,
        "additions": additions,
        "deletions": deletions,
        "unified_diff": "".join(diff_iter),
        "hunks": hunks,
    }


def _simulate_apply_diff(old_content: str, search_block: str, replace_block: str) -> str:
    """apply_diff aracının üreteceği yeni içeriği diske yazmadan önizleme için simüle eder."""
    if search_block in old_content:
        return old_content.replace(search_block, replace_block, 1)

    old_lines = old_content.splitlines(keepends=True)
    search_lines = search_block.splitlines(keepends=True)
    if not search_lines:
        return old_content

    n_search = len(search_lines)
    best_ratio = 0.0
    best_idx = -1
    search_joined = "".join(line.strip() for line in search_lines)

    for i in range(max(1, len(old_lines) - n_search + 1)):
        window = old_lines[i : i + n_search]
        window_joined = "".join(line.strip() for line in window)
        ratio = difflib.SequenceMatcher(None, search_joined, window_joined).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = i

    if best_ratio >= 0.85 and best_idx != -1:
        replace_lines = replace_block.splitlines(keepends=True)
        if replace_lines and not replace_lines[-1].endswith("\n") and old_lines[best_idx + n_search - 1].endswith("\n"):
            replace_lines[-1] += "\n"
        new_lines = old_lines[:best_idx] + replace_lines + old_lines[best_idx + n_search :]
        return "".join(new_lines)

    return old_content


class DiffSnapshotService:
    """
    Cursor / Codex Composer tarzı görsel Unified Diff önizlemesi ve
    tek tıkla geri alma (Undo / Snapshot Revert) motoru.
    """

    def __init__(self, max_snapshots: int = 50):
        self._lock = threading.RLock()
        self.max_snapshots = max_snapshots
        self.snapshots: Dict[str, Dict[str, Any]] = {}
        self.history: List[str] = []

    def _extract_file_operations(self, tool_name: str, tool_args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Araç parametrelerinden etkilenecek dosya operasyonlarını normalize eder."""
        ops: List[Dict[str, Any]] = []
        if tool_name == "write_file":
            path = tool_args.get("path")
            content = tool_args.get("content", "")
            if path:
                ops.append({"type": "write", "path": path, "content": content})
        elif tool_name == "apply_diff":
            path = tool_args.get("path")
            if path:
                ops.append({
                    "type": "diff",
                    "path": path,
                    "search_block": tool_args.get("search_block", ""),
                    "replace_block": tool_args.get("replace_block", ""),
                })
        elif tool_name == "apply_multi_diff":
            raw_edits = tool_args.get("edits", [])
            if isinstance(raw_edits, str):
                try:
                    raw_edits = json.loads(raw_edits)
                except Exception:
                    raw_edits = []
            if isinstance(raw_edits, list):
                for item in raw_edits:
                    if isinstance(item, dict) and item.get("path"):
                        ops.append({
                            "type": "diff",
                            "path": item["path"],
                            "search_block": item.get("search_block") or item.get("search") or "",
                            "replace_block": item.get("replace_block") if "replace_block" in item else item.get("replace", ""),
                        })
        return ops

    def build_diff_preview(self, tool_name: str, tool_args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Dosya düzenleme araçları için satır bazlı kırmızı/yeşil diff önizlemesi oluşturur.
        Dosya düzenleme aracı değilse None döner.
        """
        if tool_name not in FILE_EDIT_TOOLS:
            return None

        ops = self._extract_file_operations(tool_name, tool_args)
        if not ops:
            return None

        base_ws = _get_base_workspace()
        file_diffs: List[Dict[str, Any]] = []
        total_add = 0
        total_del = 0

        # Aynı dosyaya birden fazla edit varsa kümülatif önizleme yap
        simulated_contents: Dict[str, str] = {}
        existed_map: Dict[str, bool] = {}
        original_map: Dict[str, str] = {}
        rel_map: Dict[str, str] = {}

        for op in ops:
            try:
                abs_path = _validate_safe_path(op["path"])
            except Exception:
                continue

            if abs_path not in simulated_contents:
                existed = os.path.exists(abs_path) and os.path.isfile(abs_path)
                existed_map[abs_path] = existed
                if existed:
                    try:
                        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                            orig = f.read()
                    except Exception:
                        orig = ""
                else:
                    orig = ""
                original_map[abs_path] = orig
                simulated_contents[abs_path] = orig
                try:
                    rel_map[abs_path] = os.path.relpath(abs_path, base_ws)
                except Exception:
                    rel_map[abs_path] = op["path"]

            if op["type"] == "write":
                simulated_contents[abs_path] = op["content"]
            elif op["type"] == "diff":
                simulated_contents[abs_path] = _simulate_apply_diff(
                    simulated_contents[abs_path],
                    op["search_block"],
                    op["replace_block"],
                )

        for abs_path, new_text in simulated_contents.items():
            old_text = original_map[abs_path]
            is_new = not existed_map[abs_path]
            diff_obj = _compute_file_diff(rel_map[abs_path], old_text, new_text, is_new_file=is_new)
            total_add += diff_obj["additions"]
            total_del += diff_obj["deletions"]
            file_diffs.append(diff_obj)

        if not file_diffs:
            return None

        return {
            "tool": tool_name,
            "files": file_diffs,
            "total_files": len(file_diffs),
            "total_additions": total_add,
            "total_deletions": total_del,
        }

    def capture_snapshot(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        action_id: Optional[str] = None,
        diff_preview: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Dosya değişikliği diske yazılmadan hemen önce orijinal dosya durumlarını yedekler.
        """
        if tool_name not in FILE_EDIT_TOOLS:
            return None

        ops = self._extract_file_operations(tool_name, tool_args)
        if not ops:
            return None

        preview = diff_preview or self.build_diff_preview(tool_name, tool_args)
        base_ws = _get_base_workspace()
        captured_files: Dict[str, Dict[str, Any]] = {}

        for op in ops:
            try:
                abs_path = _validate_safe_path(op["path"])
            except Exception:
                continue

            if abs_path in captured_files:
                continue

            existed = os.path.exists(abs_path) and os.path.isfile(abs_path)
            original_content = None
            if existed:
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        original_content = f.read()
                except Exception:
                    original_content = ""

            try:
                rel_path = os.path.relpath(abs_path, base_ws)
            except Exception:
                rel_path = op["path"]

            captured_files[abs_path] = {
                "abs_path": abs_path,
                "rel_path": rel_path,
                "existed": existed,
                "original_content": original_content,
            }

        if not captured_files:
            return None

        snapshot_id = action_id or str(uuid.uuid4())
        snapshot = {
            "snapshot_id": snapshot_id,
            "tool": tool_name,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "applied",
            "files": list(captured_files.values()),
            "diff_preview": preview,
        }
        with self._lock:
            self.snapshots[snapshot_id] = snapshot
            if snapshot_id not in self.history:
                self.history.append(snapshot_id)
            while len(self.history) > self.max_snapshots:
                oldest = self.history.pop(0)
                self.snapshots.pop(oldest, None)
        return snapshot

    def undo_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Kaydedilen bir snapshot'ı geri yükleyerek yapılan dosya değişikliklerini geri alır."""
        with self._lock:
            if snapshot_id not in self.snapshots:
                return {
                    "status": "ERROR",
                    "snapshot_id": snapshot_id,
                    "restored_files": [],
                    "message": "Geri alınacak değişiklik kaydı (snapshot) bulunamadı.",
                }

            snap = self.snapshots[snapshot_id]
            if snap["status"] == "reverted":
                return {
                    "status": "ALREADY_REVERTED",
                    "snapshot_id": snapshot_id,
                    "restored_files": [f["rel_path"] for f in snap["files"]],
                    "message": "Bu değişiklik zaten geri alınmış.",
                }

            restored: List[str] = []
            errors: List[str] = []

            for file_entry in snap["files"]:
                abs_path = file_entry["abs_path"]
                rel_path = file_entry["rel_path"]
                try:
                    _validate_safe_path(abs_path)
                    if file_entry["existed"]:
                        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                        with open(abs_path, "w", encoding="utf-8") as f:
                            f.write(file_entry["original_content"] or "")
                        restored.append(rel_path)
                    else:
                        if os.path.exists(abs_path):
                            os.remove(abs_path)
                        restored.append(f"{rel_path} (silindi)")
                except Exception as e:
                    errors.append(f"{rel_path}: {str(e)}")

            if errors:
                return {
                    "status": "PARTIAL_ERROR",
                    "snapshot_id": snapshot_id,
                    "restored_files": restored,
                    "message": f"Bazı dosyalar geri alınamadı: {'; '.join(errors)}",
                }

            snap["status"] = "reverted"
            return {
                "status": "REVERTED",
                "snapshot_id": snapshot_id,
                "restored_files": restored,
                "message": f"Değişiklik başarıyla geri alındı ({', '.join(restored)}).",
            }

    def list_changes(self) -> List[Dict[str, Any]]:
        """Oturum boyunca yapılan tüm dosya değişikliklerini özet olarak döner."""
        result: List[Dict[str, Any]] = []
        for sid in reversed(self.history):
            snap = self.snapshots.get(sid)
            if not snap:
                continue
            preview = snap.get("diff_preview") or {}
            files_summary = []
            for f in preview.get("files", []):
                files_summary.append({
                    "path": f["path"],
                    "is_new_file": f.get("is_new_file", False),
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                })
            if not files_summary:
                for f in snap.get("files", []):
                    files_summary.append({
                        "path": f["rel_path"],
                        "is_new_file": not f["existed"],
                        "additions": 0,
                        "deletions": 0,
                    })
            result.append({
                "snapshot_id": snap["snapshot_id"],
                "tool": snap["tool"],
                "timestamp": snap["timestamp"],
                "status": snap["status"],
                "files": files_summary,
                "total_additions": preview.get("total_additions", 0),
                "total_deletions": preview.get("total_deletions", 0),
            })
        return result


diff_snapshot_service = DiffSnapshotService()

