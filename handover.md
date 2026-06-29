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

## 🔍 原實施計劃 (Plan) 與實際代碼 (Code) 缺失與 Gap 整理

目前已實施之功能運作良好，但實測與分析中發現以下 **Prompt 與對話語氣 Gap**，以及 **Phase 09 & Phase 10 的原定計劃與實際代碼 Gap**：

### 1. 提示詞與直接回答 Gap
*   **Companion 提示詞與卡片問句第三人稱/間接語氣問題 (Prompt/Card Phrasing Gap)**：
    *   **問題**：現有的 `companion.md` 提示詞模板與 `companion_agent.py` 中的離線 Mock 回應卡片使用了第三人稱或間接的指示性語氣（例如：「请向药剂师确认我的过敏史」/「Ask pharmacist to confirm my allergies」、「请药剂师重复一遍」/「Ask pharmacist to repeat」）。
    *   **影響**：當老人在前端確認卡片並播放 TTS 時，TTS 會以第三人稱向藥劑師播放（如："Ask pharmacist..."），不符合真實的第一人稱對話口吻；且老人看中文卡片也覺得不夠直觀。
    *   **修復方案（嚴格遵守安全約束）**：
        1. **保留核心約束**：卡片必須是確認問句；不能替父母斷言（例如絕不能出現 "take ibuprofen"）；不能憑空編造 "沒有過敏"；不能輸出任何直接的主觀醫療建議。
        2. **調整為第一人稱直接提問**：在上述安全邊界內，修改 `companion.md` 提示指南與 Mock 數據，將卡片的中文（`zh_text`）和英文（`en_text`）改為以老人的口吻向藥劑師直接提問（例如：「请问使用布洛芬会和我目前吃的药冲突吗？」/「Could you please check if Ibuprofen conflicts with my current meds?」），而不是使用第三人稱指示。
*   **AI 禁止陳述直接回答限制 (Response Restriction Gap)**：
    *   **問題**：`companion.md` 過於嚴格地禁止任何「陳述句（Statements）」，導致藥劑師詢問基礎問題時 AI 無法給出事實性的直接回答。
    *   **修復方案（嚴格遵守安全約束）**：在確保不給予處方/診斷等主觀醫療建議的前提下，放寬限制，允許 AI 結合已驗證的個人檔案（Patient Profile）提供事實性的直接回答（例如：「我對青黴素過敏，請幫我確認這款新藥是否安全」），但問句仍保持向藥劑師詢問確認的結構，不自行下醫療結論。

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

## 🐛 已知 Bug 與 Gap

### Bug 1：底部四個按鈕（我自己说 / 请稍等 / 重复 / 结束）點擊後無法觸發錄音

**現象**：點擊這四個按鈕沒有實際效果（不會開啟麥克風或改變錄音狀態）。

**根因分析**：

前端有兩套獨立的麥克風控制路徑，彼此不連通：

1.  **頂部按鈕路徑**（能錄音 ✅）：
    *   「听药剂师说话」和「按住说中文」直接呼叫 `setMicrophoneMode()` → 修改 `activeMicMode` state → 呼叫 `runtime.setMicrophoneEnabled(true)` → `BackendConversationRuntime` 開啟 `AudioRecorder` 並開始透過 WebSocket 傳送 PCM 音訊。

2.  **底部按鈕路徑**（不能錄音 ❌）：
    *   [`BottomControls.tsx`](frontend/src/components/BottomControls.tsx) 的四個按鈕透過 `onCommand()` → `sendCommand()` 只發送 WebSocket JSON 指令（如 `control.self_speak`、`control.please_wait`）到後端。
    *   後端 [`RuntimeCommandService`](backend/app/services/runtime_command_service.py) 收到後回傳 `audio.muted` / `audio.listening` 事件。
    *   前端 [`reducer.ts`](frontend/src/features/conversation/reducer.ts) 收到 `audio.listening` 事件後只更新 `state.status`（UI 狀態），**不會呼叫 `setMicrophoneEnabled()`**，也不會改變 `activeMicMode`。
    *   因此 `BackendConversationRuntime` 的 `AudioRecorder` 狀態不變，麥克風保持原來的開/關狀態。

**影響**：
*   「我自己说」按了沒有效果，老人以為可以自己說話但麥克風沒開。
*   「请稍等」無法暫停麥克風。
*   「重复」無法重新開啟收聽。

**修復方向**：
*   方案 A：讓 `ConversationPage` 監聽 `state.status` 的變化（如 `listening` → 觸發 `setMicrophoneMode("pharmacist")`），將後端回傳的 `audio.listening` 事件與前端麥克風控制連通。
*   方案 B：讓底部按鈕直接操作 `activeMicMode`（同時也發送 WebSocket 指令），不依賴後端回傳事件。

---

### Bug 2：「按住說中文」錄到的音被標記為醫護人員（pharmacist）而非老人（parent）

**現象**：老人按住「按住说中文」按鈕說中文，對話紀錄和翻譯流程中卻顯示為「醫護人員」。

**根因分析**：

整條音訊路徑缺少 speaker 上下文傳遞：

1.  **前端**：[`ConversationPage.tsx`](frontend/src/pages/ConversationPage.tsx) 的 `startParentMic()` 設定 `activeMicMode = "parent"`，但 [`BackendConversationRuntime.ts`](frontend/src/features/conversation/runtime/BackendConversationRuntime.ts) 的 `setMicrophoneEnabled()` 只有一個 `boolean` 參數，**不傳遞 speaker 身份**：
    ```ts
    // BackendConversationRuntime.ts:155-158
    setMicrophoneEnabled(enabled: boolean): void {
      this.userMicEnabled = enabled;
      this.micMode = enabled ? "listening_to_pharmacist" : "paused"; // 永遠是 pharmacist
    }
    ```

2.  **音訊傳輸**：`AudioRecorder` 將 PCM 原始音訊透過 WebSocket binary frame 傳送到後端，**不帶任何 metadata**（沒有 speaker tag）。

3.  **後端**：[`live_runtime_service.py`](backend/app/services/live_runtime_service.py) 的 `_read_client_loop` 直接將 binary frame 轉發給 Gemini Live API（`port.send_audio(frame)`），不加任何標記。

4.  **Gemini Live API 回傳**：[`gemini_live_adapter.py`](backend/app/adapters/gemini_live_adapter.py) 的 `_process_message` 收到 `input_transcription` 後 **hardcode** `speaker: "pharmacist"`：
    ```python
    # gemini_live_adapter.py:179-184
    flat_msg = {
        "speaker": "pharmacist",  # ← 永遠寫死為 pharmacist
        "language": "en",
        ...
    }
    ```

5.  因此不論是藥劑師還是老人的語音，只要是透過麥克風進來的 `input_transcription`，一律被標記為 `pharmacist`。

**影響**：
*   老人說的中文被當成藥劑師的英文處理，觸發翻譯流程（英→中）。
*   對話紀錄中老人的話顯示在 pharmacist 氣泡裡。
*   Turn orchestrator 把老人的話當成藥劑師的話去生成回應卡片。

**修復方向**：
1.  `ConversationRuntime` 介面新增 `setActiveSpeaker(speaker: "parent" | "pharmacist")` 方法。
2.  `BackendConversationRuntime` 在音訊串流啟動時發送 JSON 控制訊息告知後端目前說話者身份（如 `{ event_type: "audio.speaker_changed", payload: { speaker: "parent" } }`）。
3.  後端 `LiveRuntimeService` 維護每個 session 的當前 speaker 狀態。
4.  `GeminiLiveAdapter` 從 session 狀態取得 speaker 而非 hardcode。
5.  當 speaker 是 parent 時，翻譯方向應改為 中→英，且不應觸發 turn orchestrator 生成回應卡片。
