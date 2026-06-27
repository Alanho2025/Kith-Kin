**Handoff Summary**

当前本地分支 `origin/alan_workplace` 包含四项核心 Bug 的修复（卡片選擇、語音路由、日常問候語以及底欄控制按鈕與麥克風狀態），所有修改尚未提交（Uncommitted）與推送（Unpushed）。

**1. 卡片選擇與模型驗證修復**

- 在 `companion_agent.py` 的 `submit_response_cards` 中加入健全的安全欄位與時間戳覆寫預處理，防止 LLM（Gemini）因為輸出的卡片提案 JSON 中漏掉必要布林欄位（例如 `requires_guardian_approval`）或編造過期時間戳而引發 Pydantic 驗證失敗及 `CARD_EXPIRED` 錯誤。
- 在 `reducer.ts` 中更新 `"cards.render"` 與 `"card.selected"` 處理器，使其能夠同時相容並正確映射後端輸出的 `actionType` 與嵌套的 `action.type` 欄位。
- 在 `companion.md` 系統提示詞範本中，明確規定 `card_type` 的選用規則，引導 LLM 在用戶忘記藥名或音近混淆時百分之百選用 `ask_to_write_down` 類型，解決 `E03` 測試案例抖動不穩定的問題。

**2. 語音路由、問候語與底欄按鈕修復**

- 擴展 `router_agent.py` 的多種標記常數，納入中文字詞與英文音近關鍵字，確保能正確處理語音翻譯流模型輸出的中文轉寫。
- 修改 `_classify` 邏輯，將藥劑師的日常問候（如 "Hello", "How can I help you"）與中文问候語路由至 `RESPONSE_NEEDED`，進而執行 Companion 代理人以生成首輪對話卡片。
- 在 `runtime_command_service.py` 中完整實作底欄控制按鈕事件（`PleaseWaitEvent`、`RepeatEvent`、`SessionEndEvent`）的後端處理程序。
- 修正 `SelfSpeakEvent`，使其在發送 `audio.listening: true` 的同時也發送 `audio.muted: false`，解決用戶點擊「我自己說」後麥克風仍然保持靜音的 Bug。
- 在 `conftest.py` 中將測試客戶端的 `live_transport` 強制限制在 `backend_proxy` 模擬層，防止整合測試在測試期間連線真實 API 而卡死。

**验证结果**

- Eval gate：`15/15 pass`
- 后端测试：`171 passed, 1 skipped`
- 前端测试：`19 passed`
- 前端 typecheck：通过
- 前端 build：通过
- Ruff targeted：通过

**当前状态**

- 当前分支：`origin/alan_workplace`
- 代码状态：已完成 `ruff format` 格式化，變更尚未 commit
- 没有 push 远程

**注意事项**

- **真實語音端到端驗證**：在非測試環境（例如部署或實際運行）下，Gemini Live 仍需要人工端到端驗證其語音輸入、轉寫、翻譯與 Guardian 安全攔截之串接流程。
- **上下文範圍**：當前修復引入了 Session 級最近對話上下文（透過 Event Buffer），但並非完整長期記憶；長期記憶的寫入仍需依賴確認後的 `memory_write`。
