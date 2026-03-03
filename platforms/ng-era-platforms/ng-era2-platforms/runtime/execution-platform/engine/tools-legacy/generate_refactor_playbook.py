# @ECO-governed
# @ECO-layer: GL90-99
# @ECO-semantic: archive-tools
# @ECO-audit-trail: ../../engine/governance/GL_SEMANTIC_ANCHOR.json
#
# GL Unified Architecture Governance Framework Activated
#
# @ECO-governed
# @ECO-layer: governance
# @ECO-semantic: generate-refactor-playbook
# @ECO-audit-trail: ../../engine/governance/GL_SEMANTIC_ANCHOR.json
#
#!/usr/bin/env python3
"""
AI Refactor Playbook Generator
AI 重構 Playbook 生成器
Generates actionable refactor playbooks for each directory cluster based on
language governance data, security scans, and hotspot analysis.
專門為大型雲原生平台設計重構計畫的「AI Refactor Playbook Generator」
"""
# MNGA-002: Import organization needs review
import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import yaml
class RefactorPlaybookGenerator:
    """Generate refactor playbooks for directory clusters"""
    # Configuration constants
    MAX_HOTSPOTS_DISPLAY = 10
    MAX_SEMGREP_DISPLAY = 10
    AI_SUGGESTIONS_EXCERPT_LENGTH = 500
    # System prompt for LLM
    SYSTEM_PROMPT = """你是一個專門為大型雲原生平台設計重構計畫的「AI Refactor Playbook Generator」。
你同時扮演三個角色：
- 首席軟體架構師（負責整體架構與模組邊界）
- 語言治理負責人（Language Governance Owner）
- 安全與品質顧問（整合 Semgrep / 靜態分析結果）
專案背景：
- 專案名稱：Unmanned Island System
- 語言策略：
  - TypeScript + Python 為最高階語言（High-Level / 業務邏輯層）
  - Go / C++ / ROS 2 用於底層高性能與自主系統
- 已存在的治理系統：
  - Language Governance Pipeline
  - Hotspot Heatmap
  - Cluster Heatmap
  - Migration Flow Model
  - AI Auto-Fix Bot
你的工作目標：
- 對「每一個目錄群集（cluster）」產生一份可執行的 **Refactor Playbook**（Markdown）
- Playbook 要能直接給工程師 / 架構師 / 自動化 Bot 使用
- 所有建議必須：
  - 符合既有語言政策與架構骨架
  - 具體、可落地、有明確優先順序（P0 / P1 / P2）
  - 明確區分「適合交給 Auto-Fix Bot」與「必須人工審查」的範圍
"""
    USER_PROMPT_TEMPLATE = """我會提供你一個目錄群集（cluster）的所有治理數據，請你產出該 cluster 專屬的「Refactor Playbook」。
請根據以下輸入進行分析與規劃：
---
[1] Cluster 基本資訊
- Cluster 名稱：{cluster_name}
- Cluster Score：{cluster_score}
---
[2] 語言治理違規（從 governance/language-governance-report.md 擷取）
目前屬於該 cluster 的違規檔案與原因如下：
{violations_text}
---
[3] Hotspot 檔案（apps/web/public/data/hotspot.json）
該 cluster 下違規與風險分數最高的檔案如下：
{hotspot_text}
---
[4] Semgrep 安全問題（governance/semgrep-report.json）
該 cluster 相關的 Semgrep 結果如下：
{semgrep_text}
---
[5] Migration Flow Model（apps/web/public/data/migration-flow.json）
在語言遷移流模型中，這個 cluster 扮演的角色：
- Incoming Flows（其他 cluster → 本 cluster）：
{incoming_text}
- Outgoing Flows（本 cluster → 其他 cluster 或 removed）：
{outgoing_text}
---
[6] 全局 AI 建議（governance/ai-refactor-suggestions.md）
以下是對整個儲存庫的全局 AI 建議摘要，供你在制定本 cluster 計畫時參考：
{global_ai_suggestions_excerpt}
---
請依照以下「固定輸出格式」產生 **Markdown** 結果（非常重要）：
## 1. Cluster 概覽
- 這個 cluster 在整個 Unmanned Island System 中的角色（請根據路徑與檔案類型合理推斷）
- 目前主要語言組成與健康狀態（高層 vs 低層語言是否合理）
## 2. 問題盤點
- 語言治理問題分類彙總（例如：forbidden language / layer violation / low-level leak）
- Hotspot 檔案列表（依 score 高→低，附上簡短風險說明）
- Semgrep 安全問題摘要（依 severity 高→低）
- Migration Flow 觀察（本 cluster 是語言違規的「源頭」還是「垃圾場」？）
## 3. 語言與結構重構策略
- 語言層級策略：
  - 應保留哪些語言？（例如：只允許 TS + Python）
  - 應遷出/刪除哪些語言？（例如：PHP / Lua / 雜散 C++）
- 目錄結構策略：
  - 是否應拆分子模組？
  - 是否有應上移/下沉到 core/、services/、autonomous/ 的部分？
- 語言遷移建議：
  - 針對常見 pattern，給出具體路徑建議
## 4. 分級重構計畫（P0 / P1 / P2）
請用條列列出具體「檔案層級」與「動作層級」建議，例如：
- P0（24–48 小時內必須處理）
  - 檔案：...
  - 動作：刪除 / 移動到 X 目錄 / 改寫成 TypeScript / 加上安全檢查 ...
- P1（一週內）
  - 檔案：...
  - 動作：重構模組邊界 / 分離高層 API 與低層控制 / 調整目錄結構 ...
- P2（持續重構）
  - 檔案 / 子目錄：...
  - 動作：技術債清理 / 減少語言混用 / 改善可測試性 ...
## 5. 適合交給 Auto-Fix Bot 的項目
- 列出哪些檔案 / 類型的問題「可以由 Auto-Fix Bot 直接產生 patch」
- 列出哪些項目「必須人工 code review」
## 6. 驗收條件與成功指標
- 對本 cluster 的語言治理 CI 期望值
- 對 Hotspot / Cluster Score 的預期改善
- 對未來開發流程的改善方向
## 7. 檔案與目錄結構（交付視圖）
【強制交付要求】
必須包含以下內容：
1. **受影響目錄清單**
   - 明確列出本次重構涉及的所有目錄路徑
   - 例如：core/, services/gateway/, automation/autonomous/
2. **完整交付檔結構圖**
   - 使用 tree 風格文字（縮排列出目錄與檔案）
   - 或使用 Mermaid 圖表
   - 只需涵蓋本次變更涉及的目錄與檔案，不需要全 repo
   - 必須清楚可讀，展示目錄層級關係
3. **主要檔案與目錄的註解說明**
   - 針對每個重要目錄/檔案，簡短描述用途與角色
   - 格式：`path/to/file.ts` — 一行說明該檔案的職責
   - 格式：`dir/` — 說明該目錄存放什麼類型的內容
範例格式：
### 受影響目錄
- services/gateway/
- core/machinenativenops.softwareos-contracts/
- automation/intelligent/
### 結構示意（僅涵蓋變更區域）
```
services/gateway/
├── router.cpp          # 舊版 C++ gateway 入口（建議遷移）
├── router.ts           # 新版 TypeScript gateway（目標）
├── middleware/
│   ├── auth.ts         # 認證中介層
│   └── logging.ts      # 日誌中介層
└── types/
    └── request.ts      # 請求類型定義
```
### 檔案說明
- `services/gateway/router.cpp` — 現有 C++ 實作的 gateway 路由器，與舊版 core/ 搭配
- `services/gateway/router.ts` — 建議的新 TypeScript 實作，供前端與微服務使用
- `services/gateway/middleware/` — 中介層目錄，包含認證、日誌等橫切關注點
請務必依照上述段落順序與標題輸出 Markdown，且所有建議都要以 **可執行行動** 為導向，而不是抽象原則。
"""
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.clusters = {}
        self.violations = []
        self.hotspots = []
        self.semgrep_results = []
        self.migration_flows = {}
        self.global_suggestions = ""
        # Cache settings
        self.cache_enabled, self.cache_ttl_hours = self._load_cache_settings()
        self.cache_dir = self.repo_root / ".cache" / "refactor"
        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    def load_governance_data(self):
        """Load all governance data files"""
        print("📂 Loading governance data...")
        # Load language governance report
        gov_report_path = (
            self.repo_root / "governance" / "language-governance-report.md"
        )
        if gov_report_path.exists():
            self._parse_governance_report(gov_report_path)
        else:
            print(f"⚠️ Governance report not found: {gov_report_path}")
        # Load hotspot data
        hotspot_path = (
            self.repo_root / "apps" / "web" / "public" / "data" / "hotspot.json"
        )
        if hotspot_path.exists():
            with open(hotspot_path, encoding='utf-8') as f:
                self.hotspots = json.load(f)
        else:
            print(f"⚠️ Hotspot data not found: {hotspot_path}")
        # Load semgrep report
        semgrep_path = self.repo_root / "governance" / "semgrep-report.json"
        if semgrep_path.exists():
            with open(semgrep_path, encoding='utf-8') as f:
                self.semgrep_results = json.load(f)
        else:
            print(f"⚠️ Semgrep report not found: {semgrep_path}")
        # Load migration flow
        migration_path = (
            self.repo_root / "apps" / "web" / "public" / "data" / "migration-flow.json"
        )
        if migration_path.exists():
            with open(migration_path, encoding='utf-8') as f:
                self.migration_flows = json.load(f)
        else:
            print(f"⚠️ Migration flow not found: {migration_path}")
        # Load cluster heatmap
        cluster_path = (
            self.repo_root / "apps" / "web" / "public" / "data" / "cluster-heatmap.json"
        )
        if cluster_path.exists():
            with open(cluster_path, encoding='utf-8') as f:
                self.clusters = json.load(f)
        else:
            print(f"⚠️ Cluster heatmap not found: {cluster_path}")
        # Load global AI suggestions
        ai_suggestions_path = (
            self.repo_root / "governance" / "ai-refactor-suggestions.md"
        )
        if ai_suggestions_path.exists():
            with open(ai_suggestions_path, encoding='utf-8') as f:
                self.global_suggestions = f.read()
        else:
            print(f"⚠️ AI suggestions not found: {ai_suggestions_path}")
    def _load_cache_settings(self) -> tuple:
        """Load cache settings from sync-refactor-config.yaml
        Returns:
            tuple: (enabled: bool, ttl_hours: int)
        """
        config_path = self.repo_root / "config" / "sync-refactor-config.yaml"
        default_enabled = True
        default_ttl = 24
        if config_path.exists():
            try:
                with open(config_path, encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                cache_config = config.get("refactor", {}).get("cache", {})
                enabled = cache_config.get("enabled", default_enabled)
                ttl = cache_config.get("ttl_hours", default_ttl)
                return (enabled, ttl)
            except Exception as e:
                print(f"⚠️ Could not load cache settings: {e}")
                return (default_enabled, default_ttl)
        return (default_enabled, default_ttl)
    def _get_data_hash(self) -> str:
        """Generate hash of all input data sources"""
        hash_content = []
        # Hash all data source files
        data_files = [
            self.repo_root / "governance" / "language-governance-report.md",
            self.repo_root / "governance" / "semgrep-report.json",
            self.repo_root / "apps" / "web" / "public" / "data" / "hotspot.json",
            self.repo_root
            / "apps"
            / "web"
            / "public"
            / "data"
            / "cluster-heatmap.json",
            self.repo_root / "apps" / "web" / "public" / "data" / "migration-flow.json",
            self.repo_root / "governance" / "ai-refactor-suggestions.md",
        ]
        for file_path in data_files:
            if file_path.exists():
                hash_content.append(f"{file_path.name}:{file_path.stat().st_mtime}")
        # Create hash using SHA-256 (more secure than MD5)
        hash_str = "|".join(hash_content)
        return hashlib.sha256(hash_str.encode()).hexdigest()
    def _is_cache_valid(self, cluster_name: str) -> bool:
        """Check if cached playbook is still valid"""
        if not self.cache_enabled:
            return False
        cache_file = self.cache_dir / f"{cluster_name.replace('/', '_')}.cache"
        if not cache_file.exists():
            return False
        try:
            with open(cache_file, encoding='utf-8') as f:
                cache_data = json.load(f)
            # Check if data hash matches
            current_hash = self._get_data_hash()
            if cache_data.get("data_hash") != current_hash:
                return False
            # Check TTL using configured value
            cache_time = datetime.fromisoformat(
                cache_data.get("timestamp", "2000-01-01")
            )
            if datetime.now() - cache_time > timedelta(hours=self.cache_ttl_hours):
                return False
            return True
        except Exception as e:
            print(f"⚠️ Cache validation error for {cluster_name}: {e}")
            return False
    def _load_cached_playbook(self, cluster_name: str) -> str | None:
        """Load cached playbook if valid"""
        if not self._is_cache_valid(cluster_name):
            return None
        cache_file = self.cache_dir / f"{cluster_name.replace('/', '_')}.cache"
        try:
            with open(cache_file, encoding='utf-8') as f:
                cache_data = json.load(f)
            return cache_data.get("playbook")
        except Exception as e:
            print(f"⚠️ Cache load error for {cluster_name}: {e}")
            return None
    def _save_to_cache(self, cluster_name: str, playbook: str):
        """Save playbook to cache"""
        if not self.cache_enabled:
            return
        cache_file = self.cache_dir / f"{cluster_name.replace('/', '_')}.cache"
        try:
            cache_data = {
                "cluster_name": cluster_name,
                "timestamp": datetime.now().isoformat(),
                "data_hash": self._get_data_hash(),
                "playbook": playbook,
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Cache save error for {cluster_name}: {e}")
    def _parse_governance_report(self, report_path: Path):
        """Parse language governance report markdown
        Expected format:
        - **path/to/file.ext** — Reason for violation
        - **path/to/file.ext** - Reason for violation
        """
        import re
        with open(report_path, encoding='utf-8') as f:
            content = f.read()
        # Use regex for more robust parsing
        # Matches: - **file/path** — reason or - **file/path** - reason
        violation_pattern = r"-\s+\*\*([^*]+)\*\*\s+[—-]\s+(.+)"
        for match in re.finditer(violation_pattern, content):
            file_path = match.group(1).strip()
            reason = match.group(2).strip()
            self.violations.append({"file": file_path, "reason": reason})
    def _get_cluster_violations(self, cluster_name: str) -> list[dict]:
        """Get violations for a specific cluster"""
        cluster_violations = []
        for v in self.violations:
            if v["file"].startswith(cluster_name):
                cluster_violations.append(v)
        return cluster_violations
    def _get_cluster_hotspots(self, cluster_name: str) -> list[dict]:
        """Get hotspot files for a specific cluster"""
        cluster_hotspots = []
        if isinstance(self.hotspots, list):
            for h in self.hotspots:
                if isinstance(h, dict) and h.get("file", "").startswith(cluster_name):
                    cluster_hotspots.append(h)
        return cluster_hotspots
    def _get_cluster_semgrep(self, cluster_name: str) -> list[dict]:
        """Get semgrep issues for a specific cluster
        Semgrep data can be in two formats:
        1. Dict with 'results' key: {"results": [...], "summary": {...}}
        2. List of results directly: [...]
        """
        cluster_semgrep = []
        if isinstance(self.semgrep_results, dict):
            results = self.semgrep_results.get("results", [])
        elif isinstance(self.semgrep_results, list):
            results = self.semgrep_results
        else:
            results = []
        for issue in results:
            if isinstance(issue, dict):
                file_path = issue.get("path", "")
                if file_path.startswith(cluster_name):
                    cluster_semgrep.append(issue)
        return cluster_semgrep
    def _get_migration_flows(self, cluster_name: str) -> tuple:
        """Get migration flows for a cluster"""
        incoming = []
        outgoing = []
        if isinstance(self.migration_flows, dict):
            flows = self.migration_flows.get("flows", [])
            for flow in flows:
                if isinstance(flow, dict):
                    source = flow.get("source", "")
                    target = flow.get("target", "")
                    if target.startswith(cluster_name):
                        incoming.append(flow)
                    if source.startswith(cluster_name):
                        outgoing.append(flow)
        return incoming, outgoing
    def generate_cluster_prompt(
        self, cluster_name: str, cluster_score: float = 0
    ) -> str:
        """Generate LLM prompt for a specific cluster"""
        # Get cluster-specific data
        violations = self._get_cluster_violations(cluster_name)
        hotspots = self._get_cluster_hotspots(cluster_name)
        semgrep = self._get_cluster_semgrep(cluster_name)
        incoming, outgoing = self._get_migration_flows(cluster_name)
        # Format violations
        violations_text = (
            "\n".join([f"- {v['file']}: {v['reason']}" for v in violations])
            if violations
            else "無違規"
        )
        # Format hotspots (limited to MAX_HOTSPOTS_DISPLAY)
        hotspot_text = (
            "\n".join(
                [
                    f"- {h.get('file', 'unknown')} (score={h.get('score', 0)})"
                    for h in sorted(
                        hotspots, key=lambda x: x.get("score", 0), reverse=True
                    )[: self.MAX_HOTSPOTS_DISPLAY]
                ]
            )
            if hotspots
            else "無 hotspot"
        )
        # Format semgrep (limited to MAX_SEMGREP_DISPLAY)
        semgrep_text = (
            "\n".join(
                [
                    f"- {s.get('path', 'unknown')} [{s.get('severity', 'UNKNOWN')}] {s.get('rule_id', 'unknown')}: {s.get('message', 'no message')}"
                    for s in sorted(
                        semgrep, key=lambda x: x.get("severity", "LOW"), reverse=True
                    )[: self.MAX_SEMGREP_DISPLAY]
                ]
            )
            if semgrep
            else "無安全問題"
        )
        # Format flows
        incoming_text = (
            "\n".join(
                [
                    f"- {f.get('source', 'unknown')} → {cluster_name} (count={f.get('count', 0)}, type={f.get('type', 'unknown')})"
                    for f in incoming[:5]
                ]
            )
            if incoming
            else "無 incoming flows"
        )
        outgoing_text = (
            "\n".join(
                [
                    f"- {cluster_name} → {f.get('target', 'unknown')} (count={f.get('count', 0)}, type={f.get('type', 'unknown')})"
                    for f in outgoing[:5]
                ]
            )
            if outgoing
            else "無 outgoing flows"
        )
        # Get AI suggestions excerpt (configurable length)
        excerpt_len = self.AI_SUGGESTIONS_EXCERPT_LENGTH
        global_ai_suggestions_excerpt = (
            self.global_suggestions[:excerpt_len] + "..."
            if len(self.global_suggestions) > excerpt_len
            else self.global_suggestions
        )
        if not global_ai_suggestions_excerpt:
            global_ai_suggestions_excerpt = "無全局建議"
        # Generate prompt
        prompt = self.USER_PROMPT_TEMPLATE.format(
            cluster_name=cluster_name,
            cluster_score=cluster_score,
            violations_text=violations_text,
            hotspot_text=hotspot_text,
            semgrep_text=semgrep_text,
            incoming_text=incoming_text,
            outgoing_text=outgoing_text,
            global_ai_suggestions_excerpt=global_ai_suggestions_excerpt,
        )
        return prompt
    def generate_playbook_stub(
        self, cluster_name: str, cluster_score: float = 0
    ) -> str:
        """Generate a stub playbook (without LLM)"""
        violations = self._get_cluster_violations(cluster_name)
        hotspots = self._get_cluster_hotspots(cluster_name)
        semgrep = self._get_cluster_semgrep(cluster_name)
        playbook = f"""# Refactor Playbook: {cluster_name}
#*Generated:** {datetime.now().isoformat()}
#*Cluster Score:** {cluster_score}
#*Status:** Draft (LLM generation required for complete playbook)
---
## 1. Cluster 概覽
#*Cluster Path:** `{cluster_name}`
#*Current Status:** 需要重構與語言治理改進
這個 cluster 在 Unmanned Island System 中的角色：
- 路徑位置：{cluster_name}
- 違規數量：{len(violations)}
- Hotspot 檔案：{len(hotspots)}
- 安全問題：{len(semgrep)}
---
## 2. 問題盤點
### 語言治理違規 ({len(violations)})
"""
        if violations:
            for v in violations[:10]:
                playbook += f"- **{v['file']}** — {v['reason']}\n"
            if len(violations) > 10:
                playbook += f"\n... 和 {len(violations) - 10} 個其他違規\n"
        else:
            playbook += "✅ 無語言治理違規\n"
        playbook += f"\n### Hotspot 檔案 ({len(hotspots)})\n\n"
        if hotspots:
            for h in sorted(hotspots, key=lambda x: x.get("score", 0), reverse=True)[
                :5
            ]:
                playbook += (
                    f"- **{h.get('file', 'unknown')}** (score: {h.get('score', 0)})\n"
                )
        else:
            playbook += "✅ 無 hotspot 檔案\n"
        playbook += f"\n### Semgrep 安全問題 ({len(semgrep)})\n\n"
        if semgrep:
            for s in sorted(
                semgrep, key=lambda x: x.get("severity", "LOW"), reverse=True
            )[:5]:
                playbook += f"- [{s.get('severity', 'UNKNOWN')}] **{s.get('path', 'unknown')}**: {s.get('message', 'no message')}\n"
        else:
            playbook += "✅ 無安全問題\n"
        playbook += """
---
## 3. 語言與結構重構策略
#*注意：** 此部分需要使用 LLM 生成完整建議。
預期內容：
- 語言層級策略（保留/遷出語言）
- 目錄結構優化建議
- 語言遷移路徑
---
## 4. 分級重構計畫（P0 / P1 / P2）
#*注意：** 此部分需要使用 LLM 生成具體行動計畫。
### P0（24–48 小時內必須處理）
- 待 LLM 生成
### P1（一週內）
- 待 LLM 生成
### P2（持續重構）
- 待 LLM 生成
---
## 5. 適合交給 Auto-Fix Bot 的項目
#*可自動修復：**
- 待 LLM 分析
#*需人工審查：**
- 待 LLM 分析
---
## 6. 驗收條件與成功指標
#*語言治理目標：**
- 違規數 < 5
- 安全問題 HIGH severity = 0
- Cluster score < 20
#*改善方向：**
- 待 LLM 生成具體建議
---
## 7. 檔案與目錄結構（交付視圖）
### 受影響目錄
"""
        # Add affected directories
        playbook += f"- {cluster_name}\n\n"
        # Add directory tree structure
        playbook += "### 結構示意（變更範圍）\n\n```\n"
        playbook += self._generate_directory_tree(cluster_name)
        playbook += "\n```\n\n"
        # Add file annotations
        playbook += "### 檔案說明\n\n"
        annotations = self._generate_file_annotations(cluster_name)
        playbook += "\n".join(annotations)
        playbook += "\n\n---\n\n"
        playbook += """## 如何使用本 Playbook
1. **立即執行 P0 項目**：處理高優先級問題
2. **規劃 P1 重構**：安排一週內執行
3. **持續改進**：納入 P2 到長期技術債計畫
4. **交給 Auto-Fix Bot**：自動化可修復項目
5. **人工審查**：關鍵架構調整需要工程師參與
"""
        return playbook
    def generate_all_playbooks(self, use_llm: bool = False):
        """Generate playbooks for all clusters"""
        if not self.clusters:
            print(
                "⚠️  No clusters found. Creating default clusters from directory structure..."
            )
            self._detect_clusters()
        output_dir = self.repo_root / "docs" / "refactor_playbooks"
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n🚀 Generating playbooks for {len(self.clusters)} clusters...\n")
        generated_count = 0
        cached_count = 0
        for cluster_name, cluster_data in self.clusters.items():
            cluster_score = (
                cluster_data.get("score", 0) if isinstance(cluster_data, dict) else 0
            )
            print(f"  📝 {cluster_name} (score: {cluster_score})")
            # Check cache first
            playbook = self._load_cached_playbook(cluster_name)
            if playbook:
                print("     ⚡ Using cached playbook")
                cached_count += 1
            else:
                if use_llm:
                    # Generate LLM prompt
                    prompt = self.generate_cluster_prompt(cluster_name, cluster_score)
                    # Save prompt for manual LLM processing
                    prompt_file = (
                        output_dir / f"{cluster_name.replace('/', '_')}_prompt.txt"
                    )
                    with open(prompt_file, "w", encoding="utf-8") as f:
                        f.write(f"System Prompt:\n{self.SYSTEM_PROMPT}\n\n")
                        f.write(f"User Prompt:\n{prompt}\n")
                    print(f"     💡 LLM prompt saved to {prompt_file}")
                    # For now, generate stub (actual LLM integration would go
                    # here)
                    playbook = self.generate_playbook_stub(cluster_name, cluster_score)
                else:
                    # Generate stub playbook
                    playbook = self.generate_playbook_stub(cluster_name, cluster_score)
                # Save to cache
                self._save_to_cache(cluster_name, playbook)
                generated_count += 1
            # Save playbook (sanitize cluster name for filename)
            safe_cluster_name = (
                cluster_name.replace("/", "_").replace("\\", "_").replace("..", "_")
            )
            playbook_file = output_dir / f"{safe_cluster_name}_playbook.md"
            with open(playbook_file, "w", encoding="utf-8") as f:
                f.write(playbook)
            print(f"     ✅ Playbook saved to {playbook_file}")
        print(f"\n✨ Generated {len(self.clusters)} playbooks in {output_dir}")
        print(f"   📊 Stats: {generated_count} generated, {cached_count} from cache")
        if self.cache_enabled:
            cache_hit_rate = (
                (cached_count / len(self.clusters) * 100)
                if len(self.clusters) > 0
                else 0
            )
            print(f"   ⚡ Cache hit rate: {cache_hit_rate:.1f}%")
    def _generate_directory_tree(self, cluster_name: str, max_depth: int = 3) -> str:
        """Generate directory tree structure for a cluster
        Args:
            cluster_name: Name of the cluster (e.g., "core/", "services/")
            max_depth: Maximum depth to traverse (default: 3)
        Returns:
            String representation of directory tree
        """
        cluster_path = self.repo_root / cluster_name.rstrip("/")
        if not cluster_path.exists():
            return f"{cluster_name}\n  (目錄不存在)"
        def build_tree(
            path: Path, prefix: str = "", depth: int = 0, is_last: bool = True
        ) -> list[str]:
            """Recursively build tree structure"""
            if depth >= max_depth:
                return []
            lines = []
            items = []
            try:
                items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except PermissionError:
                return [f"{prefix}(無法訪問)"]
            # Filter out common ignore patterns
            ignore_patterns = {
                ".git",
                "node_modules",
                "__pycache__",
                ".venv",
                "dist",
                "build",
                ".next",
            }
            items = [item for item in items if item.name not in ignore_patterns]
            for i, item in enumerate(items[:20]):  # Limit to 20 items per directory
                is_last_item = i == len(items) - 1
                connector = "└── " if is_last_item else "├── "
                if item.is_dir():
                    lines.append(f"{prefix}{connector}{item.name}/")
                    if depth < max_depth:
                        extension = "    " if is_last_item else "│   "
                        lines.extend(
                            build_tree(
                                item, prefix + extension, depth + 1, is_last_item
                            )
                        )
                else:
                    # Show file with extension
                    lines.append(f"{prefix}{connector}{item.name}")
            if len(items) > 20:
                # Always use corner connector for the "more items" indicator
                lines.append(f"{prefix}└── ... ({len(items) - 20} more items)")
            return lines
        tree_lines = [f"{cluster_name}"]
        tree_lines.extend(build_tree(cluster_path, "", 0))
        return "\n".join(tree_lines)
    def _generate_file_annotations(self, cluster_name: str) -> list[str]:
        """Generate annotations for important files in a cluster
        Args:
            cluster_name: Name of the cluster
        Returns:
            List of annotation strings
        """
        annotations = []
        cluster_path = self.repo_root / cluster_name.rstrip("/")
        if not cluster_path.exists():
            return ["（目錄不存在，無法生成註解）"]
        # Common important files to annotate
        important_patterns = {
            "README.md": "說明文檔",
            "package.json": "Node.js 專案配置",
            "tsconfig.json": "TypeScript 編譯配置",
            "pyproject.toml": "Python 專案配置",
            "Cargo.toml": "Rust 專案配置",
            "go.mod": "Go 模組定義",
            "__init__.py": "Python 套件初始化",
            "index.ts": "模組入口點",
            "main.py": "Python 主程式",
            "main.go": "Go 主程式",
        }
        # Scan cluster for important files
        try:
            for item in cluster_path.rglob("*"):
                if item.is_file() and item.name in important_patterns:
                    rel_path = item.relative_to(self.repo_root)
                    desc = important_patterns[item.name]
                    annotations.append(f"- `{rel_path}` — {desc}")
                    if len(annotations) >= 10:  # Limit to 10 annotations
                        break
        except (PermissionError, OSError) as e:
            # Log error but continue - some directories may not be accessible
            print(f"⚠️ Warning: Could not scan {cluster_path}: {e}", file=sys.stderr)
        if not annotations:
            annotations.append("（未發現重要檔案需要特別註解）")
        return annotations
    def _detect_clusters(self):
        """Detect clusters from directory structure"""
        # Default clusters based on Unmanned Island structure
        default_clusters = [
            "core/",
            "services/",
            "automation/",
            "autonomous/",
            "governance/",
            "apps/",
            "tools/",
            "infrastructure/",
        ]
        for cluster in default_clusters:
            cluster_path = self.repo_root / cluster
            if cluster_path.exists():
                self.clusters[cluster] = {"score": 0, "exists": True}
def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Generate AI Refactor Playbooks for directory clusters"
    )
    parser.add_argument("--repo-root", default=".", help="Repository root directory")
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Generate LLM prompts (for future LLM integration)",
    )
    parser.add_argument("--cluster", help="Generate playbook for specific cluster only")
    args = parser.parse_args()
    print("🏝️  Unmanned Island System - AI Refactor Playbook Generator")
    print("=" * 70)
    # Create generator
    generator = RefactorPlaybookGenerator(args.repo_root)
    # Load governance data
    generator.load_governance_data()
    # Generate playbooks
    if args.cluster:
        # Single cluster
        cluster_score = generator.clusters.get(args.cluster, {}).get("score", 0)
        if args.use_llm:
            prompt = generator.generate_cluster_prompt(args.cluster, cluster_score)
            print("\nSystem Prompt:")
            print(generator.SYSTEM_PROMPT)
            print("\nUser Prompt:")
            print(prompt)
        else:
            playbook = generator.generate_playbook_stub(args.cluster, cluster_score)
            output_file = (
                Path("docs")
                / "refactor_playbooks"
                / f"{args.cluster.replace('/', '_')}_playbook.md"
            )
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(playbook)
            print(f"\n✅ Playbook saved to {output_file}")
    else:
        # All clusters
        generator.generate_all_playbooks(use_llm=args.use_llm)
    print("\n✨ Done!")
if __name__ == "__main__":
    main()
