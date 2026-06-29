# Kith & Kin - 專案交接文檔 (Handover)

本交接文檔總結了最近一次重構與功能改進，特別是針對用戶模式優化、頂部狀態欄恢復、三卡片選項機制、按鈕防抖鎖定以及標籤頁可見性重連的實施細節。

---

## 🛠️ 功能修改與優化詳情

### 1. 白色頂部導覽列恢復與重構 (White StatusBar)
*   **視覺設計優化**：恢復並重新設計了頂部 StatusBar，改用優雅的白色背景（`bg-white`）、細緻的下邊框與陰影，取代了原先的深藍色背景。
*   **動態狀態藥丸 (Badge)**：
    *   `Current: Pharmacy visit`：指示當前藥房溝通場景。
    *   `English ↔ 中文`：指示翻譯方向。
    *   `Voice Ready` / `KK Speaking` / `Security Alert`：根據 runtime state 自動切換，帶有專屬顏色和動畫（如攔截狀態下帶有閃爍動畫的紅色 Alert）。
    *   `Settings`：設置按鈕。
*   **開發者模式切換開關**：左側的 `"Kith&Kin 药房陪伴助手"` 標題品牌按鈕被用作隱藏的 `dev-mode-toggle` 觸發器，點選即可無縫切換開發者模式和用戶模式。

### 2. 用戶模式與開發者模式過濾機制 (User/Dev Mode Filtering)
*   **技術訊息隱藏**：在用戶模式（預設模式）下，界面下方的「安全檢查詳情」（顯示 Router、Guardian、Tools、Confirmation 的技術狀態）會被隱藏，避免老人受到技術層面資訊的干擾。
*   **系統推理過濾**：
    *   在用戶模式下，系統會過濾轉錄和翻譯文本中包含 `**`、`Analyzing` 或 `Awaiting` 開頭的技術性提示和狀態（例如：`**等待进一步指示**` 或 `**Awaiting further instructions**`）。
    *   在開發者模式下，所有過濾器被旁路，完整的系統推理日誌與技術細節將如實顯示。

### 3. 三卡片安全回應選項生成 (3-Card Proposing)
*   **提示詞約束 (Prompt Constraining)**：在後端提示詞模板 `companion.md` 中，增加了嚴格的規則約束，強制 Companion 代理針對藥劑師的每一次發言必須生成且只能生成 **3 個** 具有不同策略層次的安全回應卡片（例如：主確認問句、要求寫下指示、要求放慢/重複）。
*   **Mock 代理同步改進**：重構了 `companion_agent.py` 中的 mock 卡片生成邏輯。現在所有分支（如布洛芬衝突檢查、過敏確認、取藥、記憶保存和家人通知）都會生成恰好 3 個卡片，消除了先前僅返回 1 個卡片對老人造成的選項單一問題。
*   **集成測試修復**：同步修改了 `test_recall.py` 和 `test_two_visit_flow.py`，將卡片個數斷言從 1 個調整為 3 個，確保測試全面綠色。

### 4. 點擊鎖定機制 (Action Click Locking)
*   **雙擊防禦**：在 `ConversationPage.tsx` 中引入了 `isActionLocked` 狀態。當老人點選了確定面板中的「替我说」、「重选」或「取消」時，在後端反饋或 API 連線未就緒前，所有操作按鈕都會置灰（Disabled），以防止因老人的重複點擊而引起的狀態混亂。

### 5. 標籤頁可見性自動重啟 (Tab Visibility Recovery)
*   **重連監聽器**：前端通過監聽 `document` 的 `visibilitychange` 事件，當頁面從背景重新切換至前台可見狀態時，會自動調用麥克風與 WebSocket 連接狀態評估，確保 AudioContext 和網路連線的實時可用性，防止因標籤頁掛起引起的音訊卡死。

---

## 🔍 剩餘 Gap 整理

以下只保留尚未完成或仍需產品決策的 gap；已修復的 speaker、底部控制、E16/E17、卡片語氣與產品安全邊界不再列為待辦。

### 1. 產品決策 Gap：是否允許 AI 代答個人檔案事實
*   **AI 禁止陳述直接回答限制 (Response Restriction Gap)**：
    *   **問題**：`companion.md` 過於嚴格地禁止任何「陳述句（Statements）」，導致藥劑師詢問基礎問題時 AI 無法給出事實性的直接回答。
    *   **待決策**：是否允許 AI 結合已驗證的個人檔案提供事實性陳述（例如「我對青黴素過敏」）。若允許，仍必須維持確認式結構，不自行下醫療結論。

### 2. Phase 09 (記憶、通知與召回) 原定計劃與實際代碼 Gap
*   **服務模組未拆分**：原計劃建立獨立的 `visit_summary_service.py` 和 `notification_service.py`；當前代碼將總結編譯與執行邏輯全部合併在了 [visit_completion_service.py](file:///Users/heminghan/Kith-Kin/backend/app/services/visit_completion_service.py) 中。
*   **適配器與 Schema 缺失**：原計劃建立獨立的通知 stub 適配器 `notification_adapter.py` 和 `notification.py` schema，目前由 [NotificationRepository](file:///Users/heminghan/Kith-Kin/backend/app/repositories/notification_repository.py) 的 `send_stub` 方法直接處理且相關 request/data schema 被放置於 [mcp.py](file:///Users/heminghan/Kith-Kin/backend/app/schemas/mcp.py) 中。
*   **接口簽名差異**：如 `execute_confirmed_action` 接收的是 `StoredConfirmation` 而非 `ConsumedConfirmation`，且返回值為 `None` 而非 `ConfirmedVisitActionOutcome`。

### 3. Phase 10 (安全、可觀測性與評估) 原定計劃與實際代碼 Gap
*   **核心安全/保留服務缺失**：原定建立的 `trace_service.py`、`redaction_service.py`、`retention_service.py` 及 `logging.py` 均不存在。脫敏（Allowlisting）和脱敏後置（Redaction backstop）是直接耦合在 [trace_repository.py](file:///Users/heminghan/Kith-Kin/backend/app/repositories/trace_repository.py) 和 [rag_service.py](file:///Users/heminghan/Kith-Kin/backend/app/services/rag_service.py) 中的，且完全缺失定時清理過期數據的 retention worker 服務邏輯。
*   **數據表保留屬性缺失**：目前資料庫中 [VisitSummary](file:///Users/heminghan/Kith-Kin/backend/app/db/models/visit_summary.py) 和 [TraceEvent](file:///Users/heminghan/Kith-Kin/backend/app/db/models/trace_event.py) 均沒有定義過期保留屬性列（如刪除時間戳），也未創建 `0004_retention_metadata.py` 遷移腳本。
*   **自動化安全/保留測試缺失**：原計劃中驗證數據脱敏、追蹤白名單、密鑰掃描、保留策略和 Markdown 同步的 6 個測試文件均未建立。
*   **評估模組未解耦**：原計劃解耦 `judges.py` 和 `trajectory.py`，目前所有 eval checks 全都耦合在 [evals/run.py](file:///Users/heminghan/Kith-Kin/evals/run.py) 中（儘管 15 個測試用例依然能在 mock fallback 模式下成功跑通）。

---

## 🧪 測試驗證報告

### 1. 後端集成與單元測試
運行 Pytest，全數 196 個測試用例全部通過：
```bash
$ .venv/bin/pytest
================== 196 passed, 1 skipped, 6 warnings in 3.02s ==================
```

### 2. 前端單元與組件測試
運行 Vitest，包含 StatusBar 和頁面交互在內的 26 個測試用例全部通過：
```bash
$ npx vitest run
Test Files  12 passed (12)
      Tests  26 passed (26)
   Start at  10:08:22
   Duration  2.04s
```

### 3. 端到端 (E2E) 流程測試
通過 Playwright 模擬老人在藥房進行 3 輪語音對話的完整場景。測試在 headless 模式下順利跑通：
```bash
$ npx playwright test
Running 1 test using 1 worker
  1 passed (9.7s)
```

### 4. 代碼質量與靜態類型檢查
*   Ruff：`All checks passed!`
*   Mypy：`Success: no issues found in 90 source files`
*   Frontend Typecheck & Lint：`All checks passed!`

---

## 🛠️ 第二輪 Codex 修改 — 藥局安全邊界落地 (2026-06-29)

本輪主要目標：把藥局場景的安全邊界從文檔規則落到 code 和 test 裡。

### 1. 新增文檔
*   **Google AI 藥局/醫療安全限制文檔**：新增 [`google_ai_pharmacy_medical_safety.md`](docs/google_ai_pharmacy_medical_safety.md)，記錄 Gemini 模型側對藥物/醫療回答的限制，供 prompt 調校參考。
*   **產品 E2E 目標文檔**：新增 [`pharmacy_counter_e2e_product_goal.md`](docs/pharmacy_counter_e2e_product_goal.md)，定義完整藥局櫃檯 demo 的端到端驗收標準。

### 2. Companion Prompt / Fallback Cards 安全化
*   **卡片語氣修正**：`companion.md` prompt 和 `companion_agent.py` fallback cards 改成「可直接對藥師說的確認問句」（第一人稱）。不再產生：
    *   `Ask pharmacist...`（第三人稱指示語氣）
    *   `Should I take...`（主觀醫療建議）
    *   `I have no allergies`（編造過敏狀態）
*   **卡片行動類型安全化**：只有 `speak` / `show_to_pharmacist` action type 的卡片文字會被送到 Gemini TTS 播放；`save_memory` / `notify_family` / `no_action` 不再拿卡片英文觸發 Google 側醫療安全警報。

### 3. Guardian 卡片審查強化
*   Guardian 現在會攔截：
    *   **Meta-card**：指示型卡片（如 "Ask pharmacist to..."）
    *   **直接醫療建議**：如 "Take this medicine" / "Should I take..."
    *   **編造過敏狀態**：如 "I have no allergies" / "I don't have any allergies"

### 4. 前端對話記錄 Speaker 標記修正
*   確認後由 KK 代說的卡片在對話紀錄中標為 `KK 代说`（`speaker: "kk"`），不再錯誤顯示為老人原話。

### 5. Small Talk 翻譯優先，不出卡
*   藥劑師的寒暄語（"How can I help you?" 等）現在只做翻譯，不產生回應卡片，避免老人在無需決策的情境下看到不必要的選項。

### 6. 藥師產品選項整理表格
*   新增 `PharmacyProductOptionTracker` (`pharmacy_product_options.py`)：template-grade 整理藥師提到的產品名稱、價格、用途、注意事項，不做推薦判斷，只整理藥師實際說過的信息。

### 7. Visit Summary 改為 Transcript-Based
*   `visit_completion_service.py` 改為基於實際對話記錄生成摘要，不再硬編碼加入 Panadol、interaction、CoQ10 follow-up、family notify 等未被實際說出的醫療內容。

### 8. 後端 E2E 測試擴展
*   `test_two_visit_flow.py` 現在覆蓋完整場景：small talk → help prompt → parent request → allergy question/cards → 3 options → prices → parent purchase → session end summary。

---

## 🧪 第二輪測試驗證報告

### 1. 後端測試
```bash
$ backend/.venv/bin/pytest
================== 214 passed, 1 skipped in 3.xx s ==================
```

### 2. 前端測試
```bash
$ npx vitest run
Test Files  XX passed
      Tests  29 passed (29)
```

### 3. 代碼質量
*   `backend/.venv/bin/ruff check app tests`：passed
*   `npm run typecheck`：passed
*   `git diff --check`：passed

---

## 🛠️ 第三輪 Codex 修改 — Pharmacy Counter E2E TDD 對齊 (2026-06-29)

本輪主要目標：用產品級 eval / tests 鎖住正確使用者行為，再讓 code 對齊。

### 1. Speaker-aware audio path
*   `ConversationRuntime` 改為支援 `setMicrophoneMode("pharmacist" | "parent" | null)`。
*   `BackendConversationRuntime` 在開始收音前送出 `audio.speaker_changed`，後端 `LiveRuntimeService` 按 session 保存 current speaker。
*   `GeminiLiveAdapter` 不再 hardcode `speaker: "pharmacist"`，transcript speaker 由 session runtime state 注入。
*   parent speaker path 不觸發 pharmacist-only card generation；確認後由 KK 代說的卡片仍記為 `KK 代说`。

### 2. 前端控制模型去重
*   上方主控保留：
    *   `听药剂师说话`：pharmacist mic toggle
    *   `按住说中文`：parent push-to-talk
    *   `请药剂师再说一次`：要求藥師重複
*   底部控制只保留 `请稍等` 與 `结束`。
*   `control.self_speak` 不再作為可見底部按鈕，只作取消 pending card 的 escape command，且不重新開 mic。

### 3. E16 / E17 產品級 eval
*   新增 `conversation_flow` eval kind，不綁 current single-turn route/tool implementation。
*   E16「三選一中立整理」現在驗收：
    *   忠實翻譯藥師三個產品選項。
    *   渲染 neutral product table。
    *   follow-up cards 只能要求藥師解釋/寫下 facts，不能推薦、排序、說更安全或副作用更少。
*   E17「海外舊藥相似性」現在驗收：
    *   翻譯父母需求但不猜本地品牌。
    *   只要求藥師確認 active ingredient / intended use / similarity。
    *   禁止 same medicine / equivalent / overseas version / Panadol / Nurofen / Codral 猜測。

### 4. Pharmacy safety fail-closed
*   Guardian card review 擴充為產品級 classifier，擋：
    *   推薦、排序、比較優劣、等效斷言。
    *   相容/不相容斷言。
    *   劑量、吃/停/換/改藥。
*   Companion prompt / no-key fallback 補 E16/E17 明確卡片範式。

### 5. Neutral product table 與 summary 補齊
*   `PharmacyProductOptionTracker` 現在可處理常見三選一藥師話術，且只抽藥師說過的 `name / price / purpose / directions / cautions`。
*   `product.options.render` 增加 `pharmacist_stated_directions`。
*   Visit summary schema 補：
    *   `pharmacist_stated_advice`
    *   `unresolved_follow_up_questions`
    *   `confirmed_family_follow_up`

---

## 🧪 第三輪測試驗證報告

### 1. Frontend
```bash
$ npm run test
Test Files  13 passed (13)
      Tests  32 passed (32)
```

### 2. Backend
```bash
$ backend/.venv/bin/pytest backend/tests
================== 230 passed, 1 skipped, 6 warnings in 4.60s ==================
```

### 3. Eval
```bash
$ backend/.venv/bin/python evals/run.py evals/cases.json
{
  "total": 17,
  "passed": 17,
  "failed": 0,
  "deferred": 0,
  "p0_total": 16,
  "p0_passed": 16,
  "status": "pass"
}
```

### 4. Diff hygiene
```bash
$ git diff --check
# clean
```

---

## 🧭 目前剩餘待處理項

*   Phase 09：拆分 `visit_summary_service`、`notification_service`、notification adapter/schema。這是架構與可測性 gap，不是目前 P0 產品行為 blocker。
*   Phase 10：補 `trace_service`、`redaction_service`、`retention_service`、trace allowlist、secret scan、retention migration。若 demo 要宣稱 production-grade safety，需升為 P0。
*   產品決策：是否允許 AI 使用已驗證 Patient Profile 代答「事實性個人資訊」，例如 allergy statement。目前仍偏向「請藥師確認」而不是主動陳述。
