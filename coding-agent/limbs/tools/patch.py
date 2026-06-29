"""
PATCH-BASED EDITING — Unified diff generation, application, preview, and rollback.
Safer than direct file writes. Supports preview before applying.
"""

import difflib, json, os, re, subprocess
from pathlib import Path
from typing import Optional
from datetime import datetime


class PatchEditor:
    """Safe, diff-based file editing with backup and rollback."""

    def __init__(self, workdir: str = "."):
        self.workdir = str(Path(workdir).resolve())
        self.backup_dir = Path(self.workdir) / ".agent-patches"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._session_backups: dict[str, list[str]] = {}  # file -> [backup paths]

    # ── Public API ──

    def generate_patch(self, file_path: str, new_content: str) -> str:
        """Generate a unified diff between current and new content."""
        path = self._resolve_path(file_path)
        if not path.exists():
            old_lines = []
        else:
            old_lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=str(path),
            tofile=str(path),
            fromfiledate=datetime.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else "",
            tofiledate="(new)",
            n=3,
        )
        return "".join(diff)

    def apply_patch(self, file_path: str, patch: str) -> dict:
        """Apply a unified diff patch to a file.
        Returns: {"ok": bool, "data": "summary", "error": str}
        """
        path = self._resolve_path(file_path)
        
        # Create backup first
        backup = self._backup(path)
        if backup:
            self._session_backups.setdefault(str(path), []).append(backup)
        
        # Apply patch using `patch` command if available, else use internal
        try:
            r = subprocess.run(
                ["patch", "--forward", "-l", str(path)],
                input=patch, capture_output=True, text=True, timeout=10,
                cwd=self.workdir
            )
            if r.returncode == 0:
                return {"ok": True, "data": r.stdout.strip()[:200] or "Patch applied", "error": ""}
            # If patch command fails, try internal method
        except FileNotFoundError:
            pass
        
        # Internal fallback: manual diff application
        result = self._apply_patch_internal(path, patch)
        if not result.get("ok"):
            # Rollback on failure
            self.rollback(str(path))
        return result

    def preview_patch(self, file_path: str, patch: str) -> str:
        """Preview what a patch would do (dry run). Returns the result content."""
        path = self._resolve_path(file_path)
        if not path.exists():
            old = ""
        else:
            old = path.read_text(encoding="utf-8", errors="replace")
        
        # Use `patch --dry-run` if available
        try:
            r = subprocess.run(
                ["patch", "--dry-run", "-f", "-s", str(path)],
                input=patch, capture_output=True, text=True, timeout=10,
                cwd=self.workdir
            )
            if r.returncode == 0:
                # Simulate: apply to a temp copy
                result = self._apply_patch_to_string(old, patch)
                return result if result else "Patch would apply cleanly"
        except FileNotFoundError:
            pass
        
        result = self._apply_patch_to_string(old, patch)
        return result or "Could not preview patch"

    def rollback(self, file_path: str, version: int = -1) -> dict:
        """Rollback a file to a previous backup version.
        Args:
            file_path: Path to the file to rollback
            version: Which backup to restore (-1 = most recent)
        Returns: {"ok": bool, "data": str, "error": str}
        """
        path = self._resolve_path(file_path)
        backups = self._session_backups.get(str(path), [])
        
        if not backups:
            return {"ok": False, "data": "", "error": f"No backups for {file_path}"}
        
        backup_path = backups[version] if backups else ""
        if not backup_path or not Path(backup_path).exists():
            return {"ok": False, "data": "", "error": f"Backup not found: {backup_path}"}
        
        try:
            content = Path(backup_path).read_bytes()
            path.write_bytes(content)
            return {"ok": True, "data": f"Rolled back {file_path} to {Path(backup_path).name}", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def get_backups(self, file_path: str) -> list[str]:
        """List available backups for a file."""
        path = self._resolve_path(file_path)
        return self._session_backups.get(str(path), [])

    def edit_with_rollback(self, file_path: str, old_text: str, new_text: str) -> dict:
        """Find-and-replace with automatic rollback on failure.
        Returns: {"ok": bool, "data": str, "error": str}
        """
        path = self._resolve_path(file_path)
        if not path.exists():
            return {"ok": False, "data": "", "error": f"File not found: {file_path}"}
        
        # Backup
        backup = self._backup(path)
        if backup:
            self._session_backups.setdefault(str(path), []).append(backup)
        
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if old_text not in content:
                self.rollback(str(file_path))
                return {"ok": False, "data": "", "error": f"old_text not found in {file_path}"}
            
            new_content = content.replace(old_text, new_text, 1)
            path.write_text(new_content, encoding="utf-8")
            
            # Verify the file is valid UTF-8
            path.read_text(encoding="utf-8")
            
            return {"ok": True, "data": f"Edited {file_path}", "error": ""}
        except Exception as e:
            self.rollback(str(file_path))
            return {"ok": False, "data": "", "error": str(e)}

    # ── Internal methods ──

    def _resolve_path(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = Path(self.workdir) / path
        return p.resolve()

    def _backup(self, path: Path) -> Optional[str]:
        """Create a timestamped backup of a file."""
        if not path.exists():
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_name = f"{path.name}.{timestamp}.bak"
        backup_path = self.backup_dir / backup_name
        try:
            backup_path.write_bytes(path.read_bytes())
            return str(backup_path)
        except:
            return None

    def _apply_patch_internal(self, path: Path, patch: str) -> dict:
        """Apply patch using internal diff parsing."""
        try:
            content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
            result = self._apply_patch_to_string(content, patch)
            if result is None:
                return {"ok": False, "data": "", "error": "Could not parse patch"}
            path.write_text(result, encoding="utf-8")
            return {"ok": True, "data": f"Applied patch to {path.name}", "error": ""}
        except Exception as e:
            return {"ok": False, "data": "", "error": str(e)}

    def _apply_patch_to_string(self, content: str, patch: str) -> Optional[str]:
        """Apply a unified diff to a string. Returns the new string or None on failure."""
        if not patch.strip():
            return content
        
        # Parse unified diff
        old_lines = content.splitlines(keepends=True)
        new_lines = list(old_lines)  # Start with original
        
        current_line = 0
        hunks = []
        current_hunk = []
        
        for line in patch.split("\n"):
            if line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@ "):
                if line.startswith("@@"):
                    # Parse hunk header
                    m = re.match(r'@@ -(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?', line)
                    if current_hunk:
                        hunks.append(current_hunk)
                    current_hunk = [line]
                continue
            if current_hunk is not None:
                current_hunk.append(line)
        
        if current_hunk:
            hunks.append(current_hunk)
        
        if not hunks:
            return None
        
        # Apply hunks in reverse order to preserve line numbers
        hunks.reverse()
        for hunk in hunks:
            try:
                header = hunk[0]
                m = re.match(r'@@ -(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?', header)
                if not m:
                    continue
                old_start = int(m.group(1))
                old_count = int(m.group(2)) if m.group(2) else 1
                new_start = int(m.group(3))
                new_count = int(m.group(4)) if m.group(4) else 1
                
                # Process hunk body
                old_idx = old_start - 1
                new_idx = new_start - 1
                
                del_count = 0
                add_lines = []
                
                for hunk_line in hunk[1:]:
                    if hunk_line.startswith("---"):
                        continue
                    if hunk_line.startswith("+++"):
                        continue
                    if hunk_line.startswith("-"):
                        del_count += 1
                    elif hunk_line.startswith("+"):
                        add_lines.append(hunk_line[1:])
                    else:  # context line
                        if del_count > 0:
                            # Remove old lines
                            end_idx = min(old_idx + del_count, len(new_lines))
                            new_lines[old_idx:end_idx] = add_lines
                            old_idx = end_idx - len(add_lines) + 1 if add_lines else end_idx - del_count
                            del_count = 0
                            add_lines = []
                        old_idx += 1
                        new_idx += 1
                
                # Handle trailing changes
                if del_count > 0 or add_lines:
                    end_idx = min(old_idx + del_count, len(new_lines))
                    new_lines[old_idx:end_idx] = add_lines
                    
            except Exception:
                continue
        
        return "".join(new_lines)

    def cleanup_old_backups(self, max_age_days: int = 7):
        """Remove backup files older than max_age_days."""
        import time
        now = time.time()
        for f in self.backup_dir.iterdir():
            if f.suffix == ".bak" and (now - f.stat().st_mtime) > max_age_days * 86400:
                try:
                    f.unlink()
                except:
                    pass
