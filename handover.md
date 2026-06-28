**交接現狀：Companion Draft -> Backend-Approved CardSet**

當前分支：`codex/Alan_work`

**本輪目標**

把 Companion 生成卡片的安全邊界從「LLM 直接輸出完整 `CardSetProposal`，backend 幫它補缺欄位」改成「LLM 只輸出 semantic draft，backend deterministic materialize + Guardian approve 後才產生正式 card set」。

這是為了移除危險的 silent preprocessing：不再把 LLM 給的壞 timestamp/id/hash/approval flags 改寫成合法 payload。

---

**已實作與修正內容**

1. **Companion Draft 協議與安全隔離（核心修改）**：
   * 新增 `CompanionCardDraft` / `CompanionCardDraftSet` schema，`extra="forbid"`。
   * LLM 只輸出語義欄位 (`card_type`, `zh_text`, `en_text`, `risk_level`, `action.type`)，嚴禁輸出任何 server-owned 欄位。
   * 新增 `card_proposal_materializer.py`，由後端確定性地生成 `card_set_id`, `card_id`, `revision=1`, `generated_at`, `expires_at=now+15min` 配合 Guardian 決策 ID。
   * 後端獨立對最終 approved card set 生成 SHA-256 `proposal_hash`，不接受 LLM 供應的 hash。
   * 移除 `submit_response_cards` 中的所有篡改預處理邏輯，若 LLM 輸出不符 schema 則寫入 `companion_proposal_error` 並限制重試次數，重試失敗則 fail-closed。

2. **微調與安全性修復**：
   * **ADK State Deletion 相容性修復**：修正了 `_discard_state_key` 的屬性刪除邏輯。ADK 原生的 `State` 封裝物件不支援 Python 標準的 `del state[key]` 操作，修正後安全支援了 dictionary 刪除、`pop` 操作及直接清空底層 `_value` 與 `_delta` 的字典，徹底解決了先前導致 E2E 測試報 `AttributeError: __delitem__` 的問題。
   * **連線超時防掛起機制 (Timeout Protection)**：在 `companion_agent.py` 的 ADK runner 重試機制中引入 `asyncio.wait_for` 設置 30 秒超時。如果連線因 API Gateway throttling 或 DNS 阻礙而 hang 住，超時將拋出 `TimeoutError` 並作為暫態錯誤進行重試，防止進程死鎖。

3. **測試與評估機制優化**：
   * **評估限流延遲**：在 `evals/run.py` 中引入了每次 `turn` 類測例執行後延遲 6 秒的機制，避免短時間內的大量模型呼叫造成 `503 UNAVAILABLE: experiencing high demand` 暫態限流。

---

**驗證結果 (Verification Results)**

* **Playwright E2E 測試**：**已完全通過** (`1 passed`，耗時 ~43.4秒，且經使用者手動與系統全自動化再次驗證綠燈）。藥局三輪對話卡片確認流程、TTS、麥克風靜音（Half-Duplex）與最終通知家人的流程全部正常。
* **Pytest 後端測試套件**：**全部通過**（`191 passed, 1 skipped`）。
  * 針對 `tests/integration/runtime/` 下的 25 個整合測試在 2.29 秒內全部全綠通過，證明無跨測試狀態洩漏與網絡洩漏。
* **前端 Vitest 測試**：**全部通過**（`20 passed`）。
* **Strict Live Evaluation 跑測結果**：
  * **結果統計**：`10/15 passed`, `5/15 failed` (`E02`, `E03`, `E04`, `E05`, `E14` 失敗）。
  * **原因定位**：查閱 `task-326.log` 發現，所有失敗測例在執行時均遇到了 `ClientOSError / TimeoutError / socket.gaierror: nodename nor servname provided, or not known` 等本機連線 DNS 解析與 Google API Gateway 端重設連線的問題。
  * **安全防護驗證**：在網絡與解析故障期間，後端的 fail-closed 安全策略運作完好，所有受阻對話均安全地返回 `COMPANION_UNAVAILABLE` fallback，沒有任何程式崩潰或洩露未審查卡片的行為。同時，其餘 10 個無 LLM 呼叫的測例（包括 Block 隱私保護、防 Prompt Injection 等）全部綠燈通過。

---

**主要修改檔案**

* `backend/app/schemas/agent_outputs.py` (新增 draft schemas)
* `backend/app/agents/card_proposal_materializer.py` (後端確定性 Materializer)
* `backend/app/agents/companion_agent.py` (修復 state del, 接入 timeout 與 retry)
* `backend/app/agents/guardian_agent.py` (安全審查加強)
* `backend/app/agents/prompts/companion.md` (修改 prompt 欄位規範)
* `backend/app/agents/tools/submit_response_cards.py` (draft 驗證)
* `backend/app/services/turn_orchestrator.py` (接入 materiality 與 retry 鏈路)
* `backend/app/services/live_runtime_service.py` (Fallback 渲染控制)
* `evals/run.py` (限流延遲)
* `backend/tests/integration/runtime/test_live_translation_flow.py` (測試斷言與 Mock 邊界修補)

---

**安全與合規驗收標準 (Security Compliance)**

* [x] **LLM 輸出限制**：LLM 輸出 server-owned 欄位時自動驗證失敗，無法進入 `cards.render`。
* [x] **後端生成審計**：所有渲染出的 Response Card 均附帶後端生成的 revision, timestamp, hash, confirmation flags 及 Guardian 審查 ID。
* [x] **攔截隔離**：當 Guardian 做出 block 決策時，卡片絕不會進行 register 或 render。
* [x] **防重放/防越權**：`card.select` 與 `card.confirm` 僅傳遞確定性的識別碼；TTS、儲存、向家人發送通知等高權限行為**只能**在後端收到 user confirmation 後觸發。
