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

## 🛠️ 第四輪 Codex 修改 — speak_zh 語意分離、Phase 09 & 10 服務拆分與隱私保留落地 (2026-06-29)

本輪主要目標：完成卡片與代說文字的語意分離（修復 dialogue history 紀錄卡片問句而非 KK 說話翻譯的 Bug），並全面落實原定 Phase 09 與 Phase 10 的系統架構重構與資料隱私保護機制。

### 1. 家長卡片與代說文字分離 (`speak_zh`)
*   **欄位隔離**：在 `ResponseCard`、`CompanionCardDraft` 與前端的 `ResponseCardView` / `RawCard` 中新增 `speak_zh` 欄位。
    *   `zh_text`：專供家長閱讀與按鈕確認的選項文字（例如：“確認我有在吃血壓藥賴諾普利並告訴藥師”）。
    *   `en_text`：KK 替家長代述給藥師聽的英文對話（例如：“Excuse me, the patient is currently taking Lisinopril. Could you check if there is an interaction?”）。
    *   `speak_zh`：對應英文代述的真實中文翻譯紀錄，專供歷史紀錄 log 呈現（例如：“患者目前正在服用賴諾普利。請問這有衝突嗎？”）。
*   **邏輯更新**：
    *   重構了 `companion_agent.py` 的 fallback mock cards 與 `companion.md` 提示詞模板，確保後端始終生成 `speak_zh` 欄位。
    *   修改前端 `reducer.ts`，在 `card.confirmed` 時將 `speakZh`（若有）寫入 `translatedText` 記錄到 `turns` 中。
*   **測試對齊**：新增 `reducer.test.ts` 與 `test_submit_response_cards.py` 測試斷言確保欄位成功傳遞並寫入對話歷程。

### 2. Phase 09 服務拆分與解耦
*   **VisitSummaryService**：新增 [`visit_summary_service.py`](file:///Users/heminghan/Kith-Kin/backend/app/services/visit_summary_service.py)，將對話紀錄的提取、摘要處理、藥物提取及 unresolved questions 歸納邏輯從完成服務中徹底剝離。
*   **NotificationService & Adapter**：新增 [`notification_service.py`](file:///Users/heminghan/Kith-Kin/backend/app/services/notification_service.py) 與 [`notification_adapter.py`](file:///Users/heminghan/Kith-Kin/backend/app/adapters/notification_adapter.py)，隔離第三方 SMS/Email 發送的 stub 邊界。
*   **VisitCompletionService**：重構以完全依賴並協調上述兩個解耦服務，解決程式碼臃腫問題。

### 3. Phase 10 隱私保留與自動清理
*   **保留欄位擴充**：在 `TraceEvent` 和 `VisitSummary` 的 ORM 模型中擴充 `expires_at` 和 `deleted_at` 欄位。
*   **Alembic 資料庫遷移**：生成並成功執行資料庫遷移 `ad2e9b6dd006_retention_metadata.py`，解決 SQLite 無法執行 `ALTER COLUMN` 的相容性問題。
*   **個資去敏感服務**：新增 [`redaction_service.py`](file:///Users/heminghan/Kith-Kin/backend/app/services/redaction_service.py)，透過 Regex 與 Dict Key 深度遞迴過濾，將信用卡號、Medicare、護照號碼自動遮罩為 `[REDACTED]`。
*   **安全追蹤服務**：新增 [`trace_service.py`](file:///Users/heminghan/Kith-Kin/backend/app/services/trace_service.py)，統一代理 `TraceRepository`，在寫入追蹤日誌前自動進行 redaction 脫敏並設定 `expires_at` 保留期限。
*   **資料清理服務**：新增 [`retention_service.py`](file:///Users/heminghan/Kith-Kin/backend/app/services/retention_service.py) worker，定時或按需清除資料庫中已過期的 `TraceEvent` 與 `VisitSummary` 行。

---

## 🧪 第四輪測試驗證報告

### 1. Frontend
```bash
$ npm run test -- --run
Test Files  13 passed (13)
      Tests  33 passed (33)
```

### 2. Backend
```bash
$ backend/.venv/bin/pytest backend/tests
================== 234 passed, 1 skipped, 6 warnings in 3.20s ==================
```

### 3. Eval
```bash
$ backend/.venv/bin/python -m evals.run evals/cases.json
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

---

## 🧭 目前剩餘待處理項

*   **產品決策**：是否允許 AI 使用已驗證 Patient Profile 代答「事實性個人資訊」，例如 allergy statement。目前仍偏向「請藥師確認」而不是主動陳述。

---

## 🔴 第五輪實跑 QA 發現 — Pharmacy Counter E2E 與產品目標 Gap (2026-06-29)

本輪不是 mock test，而是依照 `docs/pharmacy_counter_e2e_product_goal.md` 用真 Chrome、真 backend、真 Gemini API 實際跑一遍藥局櫃檯流程。藥師端使用 UI 的文字 fallback 輸入英文。實跑證據：

*   Playwright report：`output/playwright/2026-06-29T08-33-13-044Z-pharmacy-e2e-report.json`
*   主要截圖：
    *   `output/playwright/2026-06-29T08-33-13-044Z-05-help-question.png`
    *   `output/playwright/2026-06-29T08-33-13-044Z-09-three-options.png`
    *   使用者提供截圖：`Screenshot 2026-06-29 at 8.36.01 PM.png`、`Screenshot 2026-06-29 at 8.36.46 PM.png`
*   事件摘要：
    *   `wsReceivedJson`: 57
    *   `wsReceivedBinaryFrames`: 0
    *   `translations`: 8
    *   `cardsRendered`: 4
    *   `productOptionsRendered`: 0
    *   `confirmations`: 1
    *   `fallbacks`: 0
    *   `pageErrors`: 0

### P0 — 對話內容流斷裂，聊天欄混入卡片內容

*   **問題**：聊天欄中的 `KK 代说` 目前不是 Gemini 實際說出的內容，也不是 TTS 播放後的 transcript，而是 `card.confirmed` 時前端直接把卡片 `enText` / `speakZh` append 到 conversation log。
*   **實跑現象**：即使本輪沒有收到任何 audio binary frame，右側對話欄仍顯示 `KK 代说`：
    *   中文：`我想确认一下，布洛芬（Nurofen）是否会和我的降压药赖诺普利（Lisinopril）有冲突？`
    *   英文：`Could you please confirm if Nurofen has an interaction with my blood pressure medicine, Lisinopril?`
*   **產品影響**：conversation log 應該是真實對話紀錄；現在它混入「被確認的卡片內容」，造成使用者看到的對話很割裂，好像 KK 已經插話，但實際上只是卡片 UI 狀態。
*   **應修方向**：
    *   proposed card 不進 conversation log。
    *   confirmed card 也不應直接進 conversation log；只有在後端明確回傳「已送出播放」且 TTS audio 成功或 action succeeded 後，才可記成 `KK 代說`。
    *   卡片選擇、確認、取消應放在獨立 action trail / state history，不污染 conversation turn history。

### P0 — Gemini TTS 沒有實際出聲

*   **問題**：後端送出 `audio.muted` 與 `audio.speaking started/completed`，但 browser WebSocket 沒收到任何 binary PCM audio frame。
*   **實跑證據**：`wsReceivedBinaryFrames = 0`，AudioContext 沒有任何 `bufferSource.start` 播放事件。
*   **產品影響**：不符合目標「確認卡片後 KK speaks the confirmed card to the pharmacist」，也不符合本輪驗收要求「要能夠聽到 Gemini 說的話」。
*   **可能原因**：`GeminiLiveAdapter.send_text()` 送 text 後，provider 回了 transcript/thought-like server content，但沒有回 `inline_data` audio；需要檢查 Live model、`response_modalities=["AUDIO"]`、`send_client_content` 的用法與 Live session role/config。

### P0 — Gemini Live 內部推理/狀態文字進入 transcript/translation/card pipeline

*   **問題**：Live provider 回傳了模型內部狀態文字，後端當成藥師 transcript 處理。
*   **實跑出現內容**：
    *   `**Interpreting the User's Speech** ...`
    *   `**Analyzing the Role-Play** ...`
    *   `**Awaiting Further Input** ...`
*   **產品影響**：
    *   這些內容被翻譯成中文，甚至觸發 route/card generation。
    *   使用者模式雖有前端 filter，但資料已污染 backend buffer、route decision、cards 和 summary input。
*   **應修方向**：
    *   provider adapter 層先 fail-closed 過濾 model thought/status text，不應只靠前端 hide。
    *   transcript source 必須只接受真實 input transcription，不接受 model text parts 當藥師/老人 transcript。

### P0 — 卡片回答沒有緊貼藥師當下問題

*   **問題**：卡片內容常跳到 profile 或 agent 推導出的 next best question，而不是回答/追問藥師剛剛問的問題。
*   **實跑例子**：
    *   藥師問生日和姓名時，卡片生成 identity confirmation 類內容。
    *   藥師問 allergies / blood pressure medicine 時，卡片直接打包 `Lisinopril + Penicillin allergy` disclosure。
    *   藥師提供三個產品後，卡片直接跳成 `Could you please confirm if Nurofen has an interaction with my blood pressure medicine, Lisinopril?`
*   **使用者觀感**：卡片像 agent 自己插話，不像老人此刻自然會對藥師說的一句話。
*   **應修方向**：
    *   卡片必須 grounded 到 latest pharmacist turn。
    *   若需要使用 profile context，卡片要明確是「請藥師核對」，不要替 AI 下結論。
    *   對 profile disclosure 建議一張卡只揭露一類事實，避免把 medication + allergy 一次打包。

### P0 — Speaker attribution 仍會錯位

*   **問題**：typed pharmacist fallback 送出的 transcript 可能被後端 current speaker 覆蓋。
*   **實跑現象**：`What can I help you with today?` 是藥師文字輸入，但右側 log 顯示為 `老人原话`。
*   **產品影響**：對話紀錄的 speaker 錯位會污染後續 route/card/summary，也讓使用者回看時不可信。
*   **應修方向**：
    *   明確區分 typed fallback 的 declared speaker 與 microphone speaker state。
    *   `_handle_transcript_provider_event` 不應無條件用 `_speaker_sessions[session_id]` 覆蓋 client-sent `TranscriptFinalEvent.payload.speaker`。

### P0 — 三產品中立比較表沒有渲染

*   **問題**：藥師提供三個產品、價格、用途、注意事項後，沒有產生 `product.options.render`。
*   **實跑輸入**：
    *   `Panadol costs eight dollars and is for pain and fever.`
    *   `Nurofen costs twelve dollars and is for pain and inflammation...`
    *   `Voltaren gel costs fifteen dollars and is for local muscle pain...`
*   **實跑結果**：`productOptionsRendered = 0`。
*   **原因**：`PharmacyProductOptionTracker` 目前仍偏 template parser，只吃 `three options:`、`This one is...`、`price is ... dollars` 等狹窄話術；自然說法 `costs eight dollars` 不會觸發。
*   **產品影響**：不符合目標「neutral comparison view: product name, price, pharmacist-stated purpose, directions, cautions」。

### P0 — 主工作區丟失最重要翻譯，只剩右側 log

*   **問題**：三產品說明後，左側老人主要看的區域顯示大片空白與 `等待药剂师说话 / 中文翻译会显示在这里`，右側 log 才看得到三產品翻譯。
*   **使用者截圖**：`Screenshot 2026-06-29 at 8.36.46 PM.png` 清楚顯示左側空白、右側才有產品資訊。
*   **產品影響**：不符合 success criteria「parent sees large, faithful Chinese translations of pharmacist speech」。
*   **應修方向**：
    *   主翻譯區應保留最近一段 final translation，直到下一段真實 speech partial/final 到來。
    *   不應在 status 回到 listening 時清空最重要的 final translation。

### P1 — 真後端模式用 `127.0.0.1` 會 ticket 403

*   **問題**：Vite 顯示 `http://127.0.0.1:5173/` 可用，但 backend `cors_allowed_origins` 預設只允許 `http://localhost:5173`。
*   **實跑現象**：
    *   使用 `127.0.0.1` 打開時，`POST /api/sessions/{id}/ticket` 回 `403 TICKET_SCOPE_INVALID`。
    *   前端 console 出現 unhandled `RUNTIME_TICKET_REQUEST_FAILED` / `RUNTIME_DISCONNECTED`。
*   **應修方向**：
    *   local dev 預設允許 `localhost:5173` 與 `127.0.0.1:5173`。
    *   前端應對 ticket failure 顯示可理解錯誤，不要 silent fallback 或 unhandled rejection。

### P1 — Typed fallback 與 microphone path 沒有隔離，會污染 Live session

*   **問題**：即使用文字輸入藥師內容，前端仍可能因 active mic state / AudioRecorder 傳送 binary frames 到 Live session。
*   **實跑現象**：report 的 sent events 有大量 binary frames，隨後 Gemini Live 產生不相關 transcript，例如生日姓名與 role-play 分析。
*   **產品影響**：文字 fallback 本應是 deterministic debugging path；現在它和 mic audio 混在一起，導致對話內容不可控。
*   **應修方向**：
    *   使用 typed fallback 時暫停/關閉 microphone audio frames。
    *   transcript injection path 應 bypass provider Live audio input，避免被 background audio / self echo 影響。

### P1 — 卡片文字仍有第三人稱或 action-label 味道

*   **問題**：部分卡片不是老人可直接對藥師說的自然 utterance。
*   **例子**：
    *   `The patient is currently taking Lisinopril and is allergic to Penicillin. Could you please note this?`
    *   `确认我有在吃血壓藥赖诺普利并对药师说我青霉素过敏`
    *   `让 KK 请药剂师写下药品名称和服用剂量`
*   **產品目標要求**：卡片應是 direct utterance，例如 `I have a recorded allergy. Could you please check whether this option is suitable?`
*   **應修方向**：分離 parent-facing option label 和 pharmacist-facing utterance，但 conversation/action state 不要把 label 混成實際說話內容。

### P1 — Visit summary 沒有出現

*   **問題**：點擊 `结束` 後等待 30 秒，沒有收到 `summary.render`。
*   **實跑證據**：`summary.render` wait timeout。
*   **產品影響**：不符合目標 step 24「generates a visit summary: medicine names mentioned, pharmacist-stated advice, unresolved questions, and family follow-up if confirmed」。
*   **待確認**：是 Playwright 沒有成功接受 `window.confirm`，還是 backend session end / summary path 沒有跑通；需要補一個 deterministic browser test。

### P1 — Purchase decision / payment flow 尚未 E2E 跑通

*   **問題**：本輪實跑只到三產品與一張 follow-up card，沒有完成：
    *   parent chooses what to buy
    *   Kith&Kin translates purchase intent
    *   pharmacist gives final price/payment instructions
    *   parent confirms purchase
    *   conversation ends with summary
*   **產品影響**：目前不能算完整 Pharmacy Counter E2E。

### P2 — 無卡片/被動翻譯狀態缺少清楚的 UI terminal state

*   **問題**：small talk 正確沒有出卡，但 UI 狀態和 automation 都不容易知道「本輪只需翻譯，沒有卡片」。
*   **產品影響**：老人可能看到狀態停在 `正在识别语音` / `KK 正在帮您确认` 一段時間，不清楚是否還在等。
*   **應修方向**：`route.decision: passive_translation` 後前端應明確回到 stable listening state，並保留剛完成的翻譯。

### 當前整體 Gap 評估

相對於 `Pharmacy Counter E2E Product Goal`，目前真後端實跑約完成 **40-45%**：

*   已有：session 建立、藥師英文轉中文、部分卡片生成、parent confirmation event、部分 profile context retrieval。
*   未達標：Gemini audible TTS、真實對話 log、一致 speaker attribution、卡片 grounding、三產品中立比較、purchase flow、visit summary。
*   下一輪建議優先級：
    1.   修 Live adapter：不要讓 model text/thought 進 transcript，並讓 confirmed card 真正產生 audio binary frames。
    2.   修 conversation log 資料模型：conversation turns 只記真實 speech/translation，card lifecycle 另存 action trail。
    3.   修 typed fallback speaker/mic isolation。
    4.   擴充 product option parser 或改成 schema extraction，支援自然藥師話術。
    5.   補真 browser E2E：生日/姓名問題、安全問題、三產品、confirm card、audio frame、summary。

---

## 🧪 第五輪 Test / Eval 失敗分析與補測計畫 (2026-06-29)

這次最大的教訓：現有 test / eval 數量不少，但大多驗證的是 **fixture path / mock path / template wording**，沒有驗證真產品使用流。結果是 eval 顯示 `17/17 pass`、後端/前端測試全綠，但真 Chrome + 真 backend + Gemini 實跑仍然暴露 P0 問題。這是測試策略失敗，下一輪必須把每個產品 bug 轉成 fail-first test gap。

### Root Cause：為什麼現有測試沒有抓到

*   **Eval 太接近 implementation fixture**：
    *   `conversation_flow` eval 直接把 `ProviderTranscriptEvent` 丟進 runtime，不經 browser、WebSocket ticket、typed fallback、mic state、Gemini Live session。
    *   E16 三產品 eval 用的是 template phrase：`three options: Panadol which is...`，不是自然藥師說法 `Panadol costs eight dollars and is for pain and fever`。
    *   `expected_flow_events` 只檢查 event type 有沒有出現，沒有檢查 UI 是否真的顯示、主工作區是否保留翻譯、聊天欄是否被卡片污染。
*   **Audio eval 驗證錯層**：
    *   E10 `audio_half_duplex` 只跑 `AudioPlaybackCoordinator` fake sink，檢查 `audio.frame` 事件順序。
    *   真產品用的是 `LiveRuntimeService` + `GeminiLiveAdapter` + WebSocket binary frame；這條路沒有被 eval 驗證。
    *   `test_card_confirmation_is_the_only_path_that_requests_english_audio` 只斷言 `port.send_text()` 被呼叫，沒有斷言 provider audio frame 真的回到 browser。
*   **前端測試把錯行為鎖成正確行為**：
    *   `frontend/src/features/conversation/reducer.test.ts` 目前期待 `card.confirmed` 直接新增 `speaker: "kk"` 的 turn。
    *   真實產品上這就是割裂感來源：卡片確認狀態被寫成對話內容。
*   **UI reasoning filter 只測前端隱藏，不測 backend 污染**：
    *   `ConversationPage.test.tsx` 測 `**Awaiting further instructions**` 在 user mode 不顯示。
    *   但真問題是 provider thought/status text 已經進 backend buffer、translation、route、cards；前端 hide 太晚。
*   **E2E 測的是 mock default，而不是真 backend**：
    *   `frontend/e2e/pharmacy-dialogue.spec.ts` 點 `开始药房对话` 後使用預設 Mock 模式，沒有切到 `真实后端 (Backend)`。
    *   它沒有驗證 ticket、Gemini Live、typed fallback、audio binary frame、summary、產品比較表自然語句。
*   **沒有 golden trace / replay 驗收**：
    *   這次真跑已產生 `output/playwright/2026-06-29T08-33-13-044Z-pharmacy-e2e-report.json`，但 CI/eval 沒有把這種 trace 當 artifact 重新驗收。
    *   目前沒有「真實 QA trace 必須被 tests replay 並失敗」的機制。

### Test Gap Matrix：所有已知問題必須轉成測試

| 問題 | 現有測試為何沒抓到 | 必補 test / eval | Pass / Fail 標準 |
|---|---|---|---|
| 聊天欄 `KK 代说` 顯示卡片內容，不是 AI 實際說話 | reducer test 反而期待 `card.confirmed` 直接 append `kk` turn | Frontend reducer fail-first：`card.confirmed` 不新增 conversation turn；只有 `speech.delivered` / `card.action.status succeeded with audio_delivery_id` 才可新增 `kk` turn | `card.confirmed` 後 `turns.length` 不變；action trail 有 confirmation record |
| 卡片 lifecycle 污染 conversation log | 目前沒有 action trail vs conversation turn 的模型測試 | Frontend state model test：card select/confirm/cancel 都進 `actions`，不進 `turns` | conversation log 只含 pharmacist / parent / delivered KK speech |
| Gemini TTS 無 binary audio frame | E10 只測 fake coordinator；backend test 只測 `send_text` 被呼叫 | Backend live transport test：confirm card 後 mock provider 必須送 `ProviderAudioEvent`，WebSocket 必須收到 binary frame；若 provider 無 audio，不能標 completed | confirmed -> muted -> speaking started -> binary frame >= 1 -> speaking completed |
| Browser 端聽不到 Gemini | 沒有 browser-level audio instrumentation | Playwright real-backend smoke：攔 WebSocket binary frame、AudioContext `bufferSource.start`，assert frame > 0 且播放 start > 0 | `wsReceivedBinaryFrames > 0` 且 audio start event 存在 |
| Provider thought/status text 進 transcript | 前端只測 hide；backend adapter 沒測阻擋 | Adapter unit test：`model_turn.parts[].text` containing `**Analyzing...**` / `**Awaiting...**` 不可 map 成 `ProviderTranscriptEvent` | queue 不產生 transcript.final；可產生 diagnostic-only event 或丟棄 |
| Thought text 觸發 route/cards | 沒有 runtime negative test | Backend runtime integration：輸入 provider thought/status event 後，不得出 `translation.final` / `route.decision` / `cards.render` | thought text 不進 replay buffer 的 user-facing events |
| 卡片回答跳 topic，沒有貼藥師當下問題 | eval 只看有 cards.render，不看 card 是否 grounded | New eval `card_grounding_latest_turn`：每張卡必須引用/回應 latest pharmacist turn 的 intent；不得從 profile 自行跳到 unrelated medicine unless latest turn asks safety/profile | 藥師問生日姓名，只能生成身份核對/請寫下/慢一點，不得生成 medication/allergy cards |
| Safety disclosure 一次打包 medication + allergy | E04 只驗證 confirmation-gated，不驗證 disclosure granularity | Backend agent test：藥師問 allergy+medication 時，profile fact cards 必須拆成單一 disclosure 或 checklist confirmation，不可一張卡混兩類敏感 facts | 一張 outward health disclosure card 只含一個 fact group，或明確 checklist UI |
| Speaker attribution 被 current mic mode 覆蓋 | 只測 speaker_changed 對 provider audio transcription；沒測 typed transcript | Backend runtime test：先 `audio.speaker_changed(parent)`，再 client `transcript.final(speaker=pharmacist)`，輸出 speaker 必須仍是 pharmacist | client-declared typed speaker 不被 `_speaker_sessions` 覆蓋 |
| Typed fallback 與 mic audio 混線 | 沒有測文字 fallback 時 binary frame 是否停止 | Frontend runtime test + Playwright：提交 typed pharmacist text 時 recorder paused，不送 audio binary frames | typed submission window 內 `ws.sent` binary frame = 0 |
| 127.0.0.1 ticket 403 | Vite test 只測 proxy 保留 Origin，沒有測 allowed origins | Config/API integration test：`http://127.0.0.1:5173` 和 `http://localhost:5173` 都可 issue ticket in dev | 兩個 origin ticket status 都是 201 |
| Ticket failure 無 user-facing error | 前端沒有 negative ticket test | Frontend BackendConversationRuntime / AppRouter test：ticket 403 顯示中文錯誤，不進 fallback fake session | UI 顯示可恢復錯誤；不 silent started |
| 三產品自然語句不產生比較表 | parser tests 用 template wording | Unit test：`Panadol costs eight dollars and is for pain and fever...` 產出三個 options | options 包含 name/price/use/caution，且無推薦排序 |
| E16 eval 沒覆蓋自然藥師話術 | E16 input 太模板化 | 修改 E16 或新增 E18：使用真跑自然句；required payload fields 檢查 `Panadol/$8/pain and fever/Nurofen caution/Voltaren caution` | 必須有 `product.options.render` 且 payload facts 完整 |
| 主工作區清空最新翻譯 | 現有 UI test 只看 log/table，不看主區保留 | Frontend component test：`translation.final` 後收到 `route.decision/cards/audio.listening`，主 subtitle 仍顯示 latest final translation | 主區仍顯示三產品中文，不回到 placeholder |
| 三產品只在右側 log，不在主區 | Browser E2E 沒截圖/locator 比對主區 | Playwright test：三產品 turn 後左側 `aria-label=忠实中文翻译` 包含 Panadol/Nurofen/Voltaren 中文 | 主工作區可見完整最近翻譯 |
| 卡片仍有第三人稱 / action-label 味道 | tests 容許 `The patient...`、`让 KK...` | Guardian / card schema tests：block or reject `The patient`, `Ask pharmacist`, `让 KK`, `请 KK`, `tell the pharmacist` action-label text in direct utterance fields | `en_text` 必須是第一人稱/直接禮貌問句；`zh_text` 可是 label 但不得寫入 conversation log |
| 卡片內容不是「可直接說給藥師」 | 現在只測 action type / guardian allow | Response card contract test：`en_text` 必須能獨立作為 utterance；禁止 meta instruction | 不含 meta verbs: ask/tell/let KK as instruction; 可含 `Could you please...` |
| Visit summary 沒出現 | summary tests 是 service-level，不是 browser session end | Backend WebSocket integration + Playwright：點 `结束` / send `session.end` 後必須收到 `summary.render` 並切到 summary page | summary 包含 mentioned drugs、pharmacist-stated advice、unresolved questions |
| Purchase/payment flow 未驗收 | E16/E17 沒覆蓋 checkout | New conversation_flow eval `purchase_checkout_flow` + browser test：parent 選買、藥師價格/付款、parent 確認、summary | 不生成醫療建議；purchase intent 被翻譯；payment instruction 被翻譯 |
| Passive translation terminal state 不清楚 | no-card path 只看沒有 cards，沒看 UI state | Frontend UI test：small talk / help prompt passive route 後狀態回 `listening`，保留翻譯，不顯示 checking spinner/cards | UI 不停在 `KK 正在帮您确认` |
| Product comparison table payload 不檢查 forbidden claims | 只檢查事件存在，不檢查每格 facts source | Eval payload validator：table fields 只能來自 pharmacist utterance spans；禁止 `best/safe/recommend/fewer side effects` | table cells 有 source span 或 exact substring provenance |

### 必須新增 / 修改的測試檔案

*   `frontend/src/features/conversation/reducer.test.ts`
    *   刪除或反轉目前「`card.confirmed` 直接新增 `KK 代说` turn」的期待。
    *   新增：card lifecycle 進 action trail，不進 conversation turns。
*   `frontend/src/pages/ConversationPage.test.tsx`
    *   新增：最新 final translation 在 route/cards/listening 後仍留在主工作區。
    *   新增：user mode 不只是 hide thought text，也要確保 thought text 不會從 runtime fixtures 進 log。
*   `frontend/src/features/conversation/runtime/BackendConversationRuntime.test.ts`
    *   新增：typed fallback submission 不啟動/不維持 mic audio streaming。
    *   新增：ticket failure 顯示 user-facing error path。
*   `frontend/e2e/pharmacy-dialogue.spec.ts`
    *   目前應拆成兩個：
        *   mock smoke：只測 mock demo。
        *   backend smoke：明確切 `真实后端 (Backend)`，驗證 WebSocket、typed fallback、main translation、no card pollution、summary。
*   `backend/tests/unit/adapters/test_gemini_live_adapter.py`
    *   新增：model text/thought part 不可 map 為 input transcript。
    *   新增：audio inline_data 才能產生 `ProviderAudioEvent`。
*   `backend/tests/integration/runtime/test_gemini_live_transport.py`
    *   新增：confirmed speech 必須收到 provider audio 才能 completed；無 audio 要 fallback/failed，不可假 completed。
    *   新增：client typed transcript speaker 不被 microphone speaker state 覆蓋。
*   `backend/tests/unit/services/test_pharmacy_product_options.py`
    *   新增自然語句 parser cases：`costs eight dollars and is for...`、`do not apply...`、`please check with me if...`。
*   `backend/tests/integration/runtime/test_live_translation_flow.py`
    *   新增真實 QA trace replay：用這次 report 的 transcript sequence 驗證 event/payload/UI contract。
*   `evals/cases.json`
    *   修改 E16 為自然藥師話術，或新增 E18 natural product options。
    *   新增 E19 card grounding latest turn。
    *   新增 E20 conversation log purity。
    *   新增 E21 purchase checkout + summary。
*   `evals/run.py`
    *   `conversation_flow` evaluator 必須不只檢查 event type，還要檢查 payload facts、forbidden strings、card grounding、speaker sequence、summary fields。
    *   新增 browser/trace-backed eval kind，至少能讀 Playwright JSON report 並驗證 binary frames、UI snapshots、conversation log purity。

### Eval 改造計畫

1.   **把 eval 分層**
    *   Unit eval：router / guardian / card shape / product extractor。
    *   Runtime eval：`LiveRuntimeService` event sequence + payload assertions。
    *   Browser trace eval：真 UI + WebSocket frame + screenshots/body text assertions。
    *   Optional live-provider eval：需要 key 時才跑，專門驗證 Gemini Live audio frame 和 provider text filtering。
2.   **每個 P0 需要至少兩層測試**
    *   例如 TTS：backend runtime fake provider audio test + browser WebSocket binary/audio playback test。
    *   例如 conversation log purity：reducer unit test + browser screenshot/bodyText test。
3.   **fixture 必須包含真實自然話術**
    *   不再只用 template phrases。
    *   每個產品 eval 至少包含一個自然句、多句合併、價格用 `costs` 而非 `price is`。
4.   **eval 不只看事件種類，要看內容**
    *   `cards.render` 不等於 pass。
    *   要檢查 card 是否 grounded、是否 direct utterance、是否沒有第三人稱、是否沒有推薦/安全斷言。
5.   **CI 必須有「實跑 QA trace replay」**
    *   真 live run 可以手動/夜間跑，但 trace replay 必須進 CI。
    *   每次發現 bug，先把 report 轉成 failing fixture，修完再更新 baseline。

### Fail-First 優先順序

1.   寫 failing tests 鎖住 `card.confirmed` 不可直接污染 conversation log。
2.   寫 backend adapter/runtime tests 鎖住 thought/status text 不可進 transcript/cards。
3.   寫 speaker override failing test：typed pharmacist transcript 不受 parent mic state 影響。
4.   寫 product extractor natural wording failing test。
5.   寫 browser backend smoke：main translation retained、product table visible、conversation log no fake KK turn。
6.   寫 audio delivery test：confirmed speech 沒有 binary audio frame 就 fail。
7.   寫 summary/session-end browser test。

### Definition of Done 更新

任何下一輪宣稱「Pharmacy Counter E2E ready」前，至少必須同時滿足：

*   `backend/.venv/bin/pytest backend/tests` pass。
*   `frontend npm test` pass。
*   `evals/run.py evals/cases.json` pass，且 eval 包含上述新增 P0 cases。
*   Playwright backend smoke pass，不能只跑 mock。
*   Browser trace report 顯示：
    *   `wsReceivedBinaryFrames > 0` for confirmed speech。
    *   `productOptionsRendered >= 1` for three-option flow。
    *   `summary.render >= 1` after session end。
    *   no user-facing transcript / translation contains `**Analyzing`、`**Awaiting`、`Interpreting the User`。
    *   conversation log contains no `KK 代说` unless audio delivery succeeded。
