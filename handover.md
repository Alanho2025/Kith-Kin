# Kith & Kin - 專案交接文檔 (Handover)

本交接文檔總結目前 `Kith-Kin` 專案在 `da0fe6d` 到 `faf2b24` 之間的最新狀態。目標是讓下一個 coding agent / Codex / teammate 能快速理解：現在專案已經修到哪裡、哪些測試是綠的、哪些產品風險已經被鎖住、還有哪些殘留 gap 需要繼續改 code。

---

## 🧭 Git Version 比對範圍

### 1. 比對方向

*   **Base / 舊版**：`da0fe6d19bc32b8d7a1eaf472368fbb6e6c2970d`
*   **Head / 新版**：`faf2b24e3a1e89011bcf96958931acf3c875e3d4`
*   **GitHub compare 結果**：`faf2b24` 比 `da0fe6d` ahead **10 commits**。
*   **重要判斷**：`da0fe6d` 是 `faf2b24` 的 merge-base，所以正確閱讀方向是 `da0fe6d -> faf2b24`，不是反過來。

### 2. 變更規模

本輪 diff 涉及後端 runtime、Gemini TTS、前端 conversation state、E2E、eval、CI、README/docs/specs，以及 `.ai-bridge` 交接資料。

高變更量檔案包括：

*   `backend/app/services/live_runtime_service.py`
*   `frontend/src/features/conversation/runtime/BackendConversationRuntime.ts`
*   `frontend/src/features/conversation/reducer.ts`
*   `frontend/src/features/conversation/reducer.test.ts`
*   `backend/tests/integration/runtime/test_live_translation_flow.py`
*   `backend/tests/integration/runtime/test_gemini_live_transport.py`
*   `frontend/e2e/pharmacy-backend.spec.ts`
*   `frontend/e2e/pharmacy-backend-deterministic.spec.ts`
*   `.github/workflows/ci.yml`
*   `docs/pharmacy_counter_current_tdd_plan.md`

---

## ✅ 當前總體狀態

目前這一版已經不是單純 mock demo。它已經把前一輪真機 QA 暴露出的核心 P0 問題，大部分轉成 runtime、frontend、eval、browser smoke 和 CI 層面的可驗證 contract。

### 已經綠的驗證結果

使用者提供的最新測試結果如下：

```bash
backend/.venv/bin/python -m pytest backend/tests
# 264 passed, 1 skipped

backend/.venv/bin/python -m pytest evals/test_runner.py -q
# 5 passed

backend/.venv/bin/python evals/run.py evals/cases.json --report /tmp/kithkin-eval-report.json
# 24/24 passed, P0 23/23

npm run typecheck
# passed

npm run lint
# passed

npm run test
# 14 files, 54 tests passed
```

### 當前狀態一句話

Kith & Kin 的藥局櫃台主流程已經從「看起來能跑」推進到「有 backend runtime、frontend reducer、eval、E2E 和 CI 多層保護」；但完整 checkout/payment flow、live-provider opt-in eval、debug breadcrumb 測試和 verified profile fact disclosure 產品決策仍需要下一輪收口。

---

## 🛠️ 功能修改與優化詳情

### 1. Gemini TTS 從 Live session 中拆出，改成 Dedicated TTS Path

本輪最重要的修復之一是把 confirmed card 的語音輸出從 Gemini Live 的不穩定文字/音訊混合路徑，改成獨立的 Gemini TTS adapter。

主要檔案：

*   `backend/app/adapters/gemini_tts_adapter.py`
*   `backend/app/services/live_runtime_service.py`
*   `backend/app/core/config.py`
*   `backend/app/main.py`
*   `backend/tests/unit/adapters/test_gemini_tts_adapter.py`
*   `backend/tests/integration/runtime/test_gemini_live_transport.py`

已完成內容：

*   新增 `GeminiTextToSpeechAdapter`。
*   新增 config：
    *   `gemini_tts_model = "gemini-2.5-flash-preview-tts"`
    *   `gemini_tts_voice_name = "charon"`
*   `LiveRuntimeService` 在 confirmed card 後呼叫 `_speak_confirmed_text()`。
*   後端事件順序變成：
    1.   `audio.muted`，避免麥克風收進 KK 自己的聲音。
    2.   `audio.speaking started`。
    3.   `card.action.status started`。
    4.   TTS synthesize。
    5.   WebSocket `send_bytes(speech.audio)`。
    6.   `audio.speaking completed`。
    7.   `card.action.status succeeded`。
    8.   restore listening。
*   若 TTS 失敗，現在會 emit `card.action.status failed`，code 是 `AUDIO_DELIVERY_FAILED`，不會假裝完成。

產品意義：

*   舊問題「後端標記 speaking completed，但 browser 沒有收到任何 binary audio frame」已被修正為 fail-closed。
*   下一個 agent 不應該把 confirmed card 又改回 Live model text path。這會直接回到前一輪大坑，像把已經抓到的 bug 又放生，牠會回來咬人。

---

### 2. Conversation Log Purity：卡片 lifecycle 不再污染真實對話紀錄

前一輪重大問題是：使用者點 confirmed card 之後，frontend 直接把 card text 寫成 `KK 代说` turn。這會造成 conversation log 看起來像 KK 已經真正說話，但實際只是 UI card 被選中。

主要檔案：

*   `frontend/src/features/conversation/reducer.ts`
*   `frontend/src/features/conversation/reducer.test.ts`
*   `frontend/src/features/conversation/mappers/runtimeEventMapper.ts`
*   `frontend/src/features/conversation/runtimeEventMapper.test.ts`
*   `frontend/src/features/conversation/hooks/useCardConfirmation.ts`
*   `frontend/src/components/ResponseCard.tsx`

已完成內容：

*   `card.confirmed` 不應直接新增 conversation turn。
*   卡片 select / confirm / cancel 屬於 action lifecycle，不屬於真實 speech transcript。
*   `KK 代说` 只有在 audio delivery / action succeeded 後才可以被視為可記錄的 delivered speech。
*   reducer tests 已經大量補強，避免把錯行為再次鎖成「正確」。

產品意義：

*   右側聊天欄應該只代表真實對話與翻譯。
*   卡片是決策 UI，不是 transcript。
*   下一個 agent 改 UI 時要守住這條邊界，否則 summary、eval 和使用者信任都會被污染。

---

### 3. 主工作區翻譯語義調整：左側大字區只顯示最新 faithful translation

產品決策已澄清：左側老人主要看的大字中文區不是 append-only history。它應該只顯示最近一段藥師 final translation。完整歷史在右側 log、debug trace 和 turn history。

主要檔案：

*   `frontend/src/components/TwoLayerSubtitle.tsx`
*   `frontend/src/components/TwoLayerSubtitle.test.tsx`
*   `frontend/src/pages/ConversationPage.tsx`
*   `frontend/src/pages/ConversationPage.test.tsx`

已完成內容：

*   大字翻譯區在新 final translation 進來後只保留最新句子。
*   不在 `route.decision`、cards、listening restore 後清空最重要的 final translation。
*   右側 log / reducer turn history 繼續保留完整歷史。

產品意義：

*   老人使用時不用在主區讀一大坨歷史文字。
*   也不會在藥師剛說完重要資訊後，畫面跳回「等待藥師說話」造成資訊消失。

---

### 4. Typed Fallback、Mic State、Speaker Attribution 重新隔離

前一輪實跑發現：typed pharmacist fallback 和 microphone path 會互相污染，甚至 client-declared speaker 可能被 backend current mic speaker 覆蓋。

主要檔案：

*   `frontend/src/features/conversation/runtime/BackendConversationRuntime.ts`
*   `frontend/src/features/conversation/runtime/BackendConversationRuntime.test.ts`
*   `backend/app/services/live_runtime_service.py`
*   `backend/tests/integration/runtime/test_gemini_live_transport.py`

已完成內容：

*   typed fallback submission 不應維持 mic streaming。
*   client-declared typed speaker 不應被 `_speaker_sessions[session_id]` 盲目覆蓋。
*   backend tests 覆蓋 typed pharmacist transcript 在 parent mic state 下仍保持 pharmacist speaker。
*   frontend runtime tests 覆蓋 ticket failure 與 backend-mode edge cases。

產品意義：

*   typed fallback 是 deterministic debugging path，不能混入背景 mic audio。
*   speaker attribution 是 summary、card grounding、translation log 的地基。地基歪了，後面全會歪。

---

### 5. Gemini Live thought/status text 污染問題被移到 adapter/runtime 層處理

前一輪真機發現 Gemini Live 可能回傳類似：

*   `**Interpreting the User's Speech**`
*   `**Analyzing the Role-Play**`
*   `**Awaiting Further Input**`

舊做法只靠前端 user mode filter 隱藏，太晚了。因為資料已經進 backend buffer、translation、route、cards 和 summary。

主要檔案：

*   `backend/app/adapters/gemini_live_adapter.py`
*   `backend/app/adapters/provider_schemas.py`
*   `backend/app/services/live_runtime_service.py`
*   `backend/tests/integration/runtime/test_live_translation_flow.py`

已完成方向：

*   model thought/status text 不應被 map 成 user-facing transcript。
*   provider audio / transcript / diagnostic 應被區分。
*   runtime 層不應把 provider internal status 當成藥師或老人說的話。

產品意義：

*   使用者模式 filter 只能是最後防線，不是資料污染防線。
*   下一個 agent 如果看到前端 filter test，不要以為問題已經只在 UI。真正要守的是 adapter/runtime input boundary。

---

### 6. Product Option Tracker 支援更自然的藥師三選一話術

前一輪失敗原因是 parser 太 template，只吃 `three options:` 或 `price is ... dollars` 這種固定句。真藥師更可能說：

```text
Panadol costs eight dollars and is for pain and fever.
Nurofen costs twelve dollars and is for pain and inflammation.
Voltaren gel costs fifteen dollars and is for local muscle pain.
```

主要檔案：

*   `backend/app/services/pharmacy_product_options.py`
*   `backend/tests/unit/services/test_pharmacy_product_options.py`
*   `backend/tests/integration/runtime/test_live_translation_flow.py`
*   `evals/cases.json`
*   `evals/fixtures/pharmacy_counter_gap_trace.json`

已完成內容：

*   `PharmacyProductOptionTracker` 擴充自然句 parser。
*   表格只整理藥師明確說出的 facts：name、price、purpose、directions、cautions。
*   不做推薦、不排序、不推論「更安全 / 副作用更少」。
*   eval payload validator 需要檢查 forbidden claims，不只是檢查有沒有 `product.options.render`。

產品意義：

*   Kith & Kin 在藥局場景中是翻譯與安全確認助手，不是醫療建議 agent。
*   產品表格只能是 pharmacist-stated facts 的中立整理。

---

### 7. Seeded Demo Data 和 Profile Lookup 可觀測化

舊問題是：看起來像 AI 沒讀 DB，但其實不清楚是 DB 沒 seed、lookup 沒跑、還是 card review 擋掉。

主要檔案：

*   `scripts/seed_demo_data.py`
*   `backend/tests/integration/mcp/test_seed_demo_data.py`
*   `backend/app/adapters/mcp_tool_adapter.py`
*   `backend/app/services/turn_orchestrator.py`
*   `backend/app/core/conversation_debug.py`
*   `frontend/src/features/conversation/debugLog.ts`

已完成內容：

*   Demo seed data 包含 Lisinopril、Penicillin allergy、prior follow-up、overseas medicine active-ingredient note、OTC brand knowledge。
*   Debug log 現在能觀察：
    *   `tool.memory_search.result record_count=4`
    *   `turn.profile_lookup.result allergy_count=1 medication_count=1`
*   `mcp_tool_adapter.py` 和 seed tests 強化資料可用性。

產品意義：

*   之後不要再靠肉眼猜「AI 有沒有讀 database」。
*   下一個 agent 應該先看 debug breadcrumbs，再改 prompt 或 runtime。

---

### 8. Frontend Backend Mode / E2E 拆分

舊的 `pharmacy-dialogue.spec.ts` 偏 mock path，會讓 E2E 綠但真 backend 爆炸。

主要檔案：

*   `frontend/e2e/pharmacy-backend.spec.ts`
*   `frontend/e2e/pharmacy-backend-deterministic.spec.ts`
*   `frontend/e2e/pharmacy-dialogue.spec.ts`（已移除）
*   `frontend/playwright.config.ts`
*   `frontend/src/playwright-config.test.ts`
*   `.github/workflows/ci.yml`

已完成內容：

*   拆出 real backend smoke。
*   新增 deterministic backend mode smoke，讓 CI 可以不用真 Gemini key 也跑核心流程。
*   Playwright config 加強 database path、webServer、backend mode split。
*   CI workflow 加入更完整的 backend/frontend/eval/deterministic-e2e verification。

注意：

*   `docs/pharmacy_counter_current_tdd_plan.md` 提到本地 deterministic e2e 曾因 Codex escalated-command usage limit 被阻擋，預期由 GitHub Actions 的 `deterministic-e2e` job 跑。
*   如果下一個 agent 在本地能跑，應優先補一次 deterministic Playwright 實跑結果。

---

### 9. Eval 從 17 cases 擴展到 24 cases，P0 變成 23 個

主要檔案：

*   `evals/cases.json`
*   `evals/test_runner.py`
*   `evals/run.py`
*   `evals/fixtures/pharmacy_counter_gap_trace.json`
*   `backend/tests/eval/`

目前結果：

```bash
backend/.venv/bin/python evals/run.py evals/cases.json --report /tmp/kithkin-eval-report.json
# 24/24 passed, P0 23/23
```

已完成方向：

*   Eval 不只看 event type，也要看 payload facts、forbidden strings、speaker sequence、summary fields、card grounding。
*   產品 option eval 使用更自然的藥師說法。
*   Conversation flow eval 開始向 runtime behavior 靠近，而不是只驗 fixture path。

下一步注意：

*   Eval 仍不能完全取代 browser smoke。
*   Browser trace replay 應進 CI，live provider eval 則適合 opt-in 或 nightly。

---

### 10. README / Architecture / Writeup / Specs 同步更新

主要檔案：

*   `README.md`
*   `docs/architecture_diagram.svg`
*   `docs/writeup_draft.md`
*   `specs/runtime-event-contract.md`
*   `docs/pharmacy_counter_current_tdd_plan.md`

本輪不只是 code 變了，文檔也已經跟著調整：

*   README 更新為目前 pharmacy counter / backend / frontend / eval 狀態。
*   架構圖更新 runtime, TTS, eval, frontend state 的關係。
*   writeup_draft 同步專案敘述。
*   runtime event contract 加強 audio / card / summary / product options 事件語義。
*   current TDD plan 記錄最新 verification baseline 和下一輪 gap。

---

## 🧪 測試驗證報告

### 1. Backend unit / integration tests

```bash
backend/.venv/bin/python -m pytest backend/tests
# 264 passed, 1 skipped
```

涵蓋重點：

*   Live runtime event flow。
*   Gemini TTS adapter。
*   typed fallback speaker isolation。
*   product options extractor。
*   seed demo data。
*   MCP tool / memory search。
*   repository hygiene。

---

### 2. Eval runner tests

```bash
backend/.venv/bin/python -m pytest evals/test_runner.py -q
# 5 passed
```

涵蓋重點：

*   Eval runner 本身的解析與 pass/fail contract。
*   Conversation flow evaluator 的基礎行為。

---

### 3. Eval cases

```bash
backend/.venv/bin/python evals/run.py evals/cases.json --report /tmp/kithkin-eval-report.json
# 24/24 passed, P0 23/23
```

目前 eval 已經比前一輪強很多，但仍不要把它當成完整真機證明。它證明 runtime/eval contract 綠，不等於真 Gemini provider 和 browser audio 每次都穩。

---

### 4. Frontend static checks

```bash
npm run typecheck
# passed

npm run lint
# passed
```

若在本地 repo 操作，通常應在 `frontend/` 目錄執行上述 npm commands。

---

### 5. Frontend unit/component tests

```bash
npm run test
# 14 files, 54 tests passed
```

涵蓋重點：

*   reducer state model。
*   card lifecycle 不污染 conversation turns。
*   main translation latest-only display。
*   runtime event mapping。
*   BackendConversationRuntime。
*   ConversationPage。
*   subtitle / response card / summary page。

---

## 🔍 已修復的前一輪 P0 Gap

以下是前一版 handover 中最嚴重的問題，以及目前狀態。

### 1. Gemini TTS 沒有 binary audio frame

*   **舊狀態**：`wsReceivedBinaryFrames = 0`，browser 沒聽到 Gemini。
*   **新狀態**：confirmed card 走 dedicated Gemini TTS，backend 會 `send_bytes(speech.audio)`，並有 `live.card_tts.audio_sent` / frontend audio player scheduling evidence。
*   **仍需補強**：live provider opt-in eval 和 browser console/audio assertions。

### 2. Conversation log 混入 confirmed card text

*   **舊狀態**：`card.confirmed` 直接 append `KK 代说` turn。
*   **新狀態**：card lifecycle 和 conversation turns 分離。
*   **仍需補強**：browser-level regression test 應繼續鎖住 no fake KK turn。

### 3. Provider thought/status text 污染 transcript pipeline

*   **舊狀態**：`**Analyzing...**` 類文字進 backend route/cards。
*   **新狀態**：adapter/runtime 層已改為阻擋或區分 internal model text。
*   **仍需補強**：live provider opt-in trace eval。

### 4. Speaker attribution 錯位

*   **舊狀態**：typed pharmacist text 可能顯示成老人原話。
*   **新狀態**：client-declared typed speaker 不應被 mic state 覆蓋，已有 backend/runtime test。

### 5. 三產品中立比較表沒有渲染

*   **舊狀態**：自然說法 `costs eight dollars` 不觸發。
*   **新狀態**：parser / eval / tests 已加自然語句。
*   **仍需補強**：完整 purchase/payment browser flow。

### 6. 主工作區丟失重要翻譯

*   **舊狀態**：左側大字區回到 placeholder，重要資訊只在右側 log。
*   **新狀態**：主區保留 latest faithful translation，但不是 append-only。

### 7. Visit summary 沒出現

*   **舊狀態**：點 `结束` 後等待 timeout。
*   **新狀態**：backend smoke / summary path 已被驗證。
*   **仍需補強**：完整 checkout 後 summary browser test。

---

## 🧭 目前剩餘待處理項

以下是下一個 agent 應優先看的殘留問題。不要把它們當成小修小補。這些都是產品級交互穩定性問題。

### P0 / P1：完整 Purchase / Payment Flow 尚未 browser-verified

目前 backend smoke 已覆蓋 product comparison 和 summary，但完整 flow 還需要更明確地跑到：

1.   parent chooses what to buy。
2.   KK translates purchase intent。
3.   pharmacist gives final price / payment instruction。
4.   parent confirms purchase。
5.   conversation ends with summary。

建議新增：

*   `frontend/e2e/pharmacy-checkout-backend.spec.ts`
*   對應 conversation_flow eval：`purchase_checkout_flow`

Pass 標準：

*   不生成醫療建議。
*   purchase intent 被忠實翻譯。
*   payment instruction 被忠實翻譯。
*   summary 包含 mentioned drugs、pharmacist-stated advice、unresolved questions、family follow-up if confirmed。

---

### P1：Console diagnostics 仍偏 manual-only

目前 debug breadcrumbs 已經存在，但還需要 Playwright console-capture test 證明每個關鍵階段都有 log。

建議測試：

*   Session create。
*   Ticket request / ticket success。
*   WebSocket open。
*   typed fallback submit。
*   runtime event receive。
*   reducer state transition。
*   card select / confirm。
*   audio inbound。
*   audio playback scheduled。
*   summary render。

目的：

*   讓下一次真機爆炸時，不需要靠截圖通靈。

---

### P1：Live Gemini provider opt-in eval 尚未正式落地

目前 mandatory CI 應走 fake provider / deterministic backend。真 Gemini provider 因為 key、rate limit、成本、穩定性問題，不適合每次 CI 必跑。

但需要 opt-in eval：

*   `live_gemini_pharmacy_smoke`
*   產出 sanitized provider/runtime/browser trace。
*   驗證：
    *   no thought/status text enters transcript。
    *   confirmed card produces audio bytes。
    *   speaker attribution correct。
    *   no fake KK turn。
    *   summary render。

如果沒有 key，應 skip 並明確說明原因，不應 fail silently。

---

### P1：Verified profile fact disclosure 仍是產品決策點

目前仍需要產品層決策：AI 是否可以用已驗證 Patient Profile 幫老人直接說出事實性個人資訊？

例子：

*   `I have a recorded penicillin allergy. Could you please check whether this option is suitable?`
*   `I am taking Lisinopril. Could you please check if this medicine is suitable with it?`

安全邊界：

*   可以分享 verified fact。
*   必須請 pharmacist check。
*   不可自己下醫療結論。
*   不可說「safe」、「compatible」、「recommended」、「equivalent」。
*   一張 outward health disclosure card 不要同時混 allergy + medication，除非 UI 是 checklist confirmation。

建議新增 paired agent/eval tests。

---

### P1：`.ai-bridge` 是否應進 repo 需要確認

Git compare 顯示 `.ai-bridge` 新增了大量交接資料，尤其：

*   `.ai-bridge/current-plan.md`
*   `.ai-bridge/pro-context.md`
*   `.ai-bridge/session-log.jsonl`
*   `.ai-bridge/execution-log.jsonl`
*   `.ai-bridge/implementation-diff.patch`

注意：

*   這些是 agent handoff / CodexPro context 檔，不是產品功能。
*   `.ai-bridge/pro-context.md` 很大，容易污染 PR review。
*   下一個 agent 在提交前應確認 team 是否要保留 `.ai-bridge` 在 git 裡。
*   若只是本地協作資料，建議改成 `.gitignore` 或移出 final PR。

---

### P2：Test hygiene warning cleanup

目前 tests 是 pass，但還有 warning cleanup 值得處理：

*   backend `AsyncMock` unawaited warning。
*   frontend Vitest localStorage warning。
*   Playwright teardown `ECONNRESET` noise。

這些不是現在阻塞項，但長期會讓 CI output 變吵，真正 regression 會被淹沒。

---

## 🧩 下一個 Agent 的 Code Entry Points

### Backend 優先入口

*   `backend/app/services/live_runtime_service.py`
    *   WebSocket runtime 主控。
    *   audio mute / speaking / card action status / summary / product options 都在這附近。
*   `backend/app/adapters/gemini_tts_adapter.py`
    *   confirmed card speech 的 dedicated TTS path。
*   `backend/app/adapters/gemini_live_adapter.py`
    *   Live provider transcript/audio/status boundary。
*   `backend/app/services/turn_orchestrator.py`
    *   profile lookup、router、companion、guardian 的 turn orchestration。
*   `backend/app/services/pharmacy_product_options.py`
    *   三產品中立整理 parser。
*   `backend/app/adapters/mcp_tool_adapter.py`
    *   memory search / MCP tool result 邊界。
*   `backend/app/core/conversation_debug.py`
    *   backend conversation breadcrumb。

### Backend tests 優先入口

*   `backend/tests/integration/runtime/test_live_translation_flow.py`
*   `backend/tests/integration/runtime/test_gemini_live_transport.py`
*   `backend/tests/unit/adapters/test_gemini_tts_adapter.py`
*   `backend/tests/unit/services/test_pharmacy_product_options.py`
*   `backend/tests/integration/mcp/test_seed_demo_data.py`

---

### Frontend 優先入口

*   `frontend/src/features/conversation/runtime/BackendConversationRuntime.ts`
    *   backend mode、ticket、WebSocket、typed fallback、audio recorder/player bridge。
*   `frontend/src/features/conversation/reducer.ts`
    *   conversation turns、card lifecycle、summary、product options、translation state。
*   `frontend/src/features/conversation/mappers/runtimeEventMapper.ts`
    *   backend runtime event 到 frontend action 的 mapping。
*   `frontend/src/features/conversation/hooks/useCardConfirmation.ts`
    *   card select / confirm / cancel。
*   `frontend/src/features/conversation/hooks/useLiveConversation.ts`
    *   runtime lifecycle hook。
*   `frontend/src/pages/ConversationPage.tsx`
    *   主頁 UI state。
*   `frontend/src/components/TwoLayerSubtitle.tsx`
    *   left large-print translation。
*   `frontend/src/components/ResponseCard.tsx`
    *   card rendering。
*   `frontend/src/pages/VisitSummaryPage.tsx`
    *   summary page。
*   `frontend/src/features/conversation/debugLog.ts`
    *   frontend debug breadcrumb。

### Frontend tests 優先入口

*   `frontend/src/features/conversation/reducer.test.ts`
*   `frontend/src/features/conversation/runtime/BackendConversationRuntime.test.ts`
*   `frontend/src/features/conversation/runtimeEventMapper.test.ts`
*   `frontend/src/pages/ConversationPage.test.tsx`
*   `frontend/src/components/TwoLayerSubtitle.test.tsx`
*   `frontend/e2e/pharmacy-backend.spec.ts`
*   `frontend/e2e/pharmacy-backend-deterministic.spec.ts`

---

### Eval / CI 優先入口

*   `evals/cases.json`
*   `evals/test_runner.py`
*   `evals/run.py`
*   `evals/fixtures/pharmacy_counter_gap_trace.json`
*   `.github/workflows/ci.yml`
*   `frontend/playwright.config.ts`

---

## 🚦 下一輪建議優先順序

### 1. 先確認 deterministic backend E2E 在本地或 CI 真正跑過

建議命令：

```bash
cd frontend
PLAYWRIGHT_BACKEND_MODE=deterministic npx playwright test e2e/pharmacy-backend-deterministic.spec.ts
```

目的：

*   驗證 CI browser smoke 不是紙面設定。
*   確認 seeded DB、backend mode、frontend UI、WebSocket、summary 都能在 deterministic path 跑通。

---

### 2. 補完整 checkout/payment browser flow

建議新增：

```text
frontend/e2e/pharmacy-checkout-backend.spec.ts
```

測試路徑：

1.   開 backend mode。
2.   typed pharmacist greeting。
3.   parent ask for medicine / product help。
4.   pharmacist gives three options。
5.   product table visible。
6.   parent chooses one product。
7.   pharmacist gives payment instruction。
8.   parent confirms。
9.   session end。
10.  summary render。

---

### 3. 補 console breadcrumb Playwright assertions

不要只靠 manual console 看 log。

Pass 標準：

*   Browser test 能 assert required `[KK conversation]` labels。
*   若 ticket fail / WebSocket fail / no audio / no summary，console trace 能定位是哪一段斷。

---

### 4. 補 live provider opt-in eval

建議設計：

```bash
LIVE_GEMINI_SMOKE=1 backend/.venv/bin/python evals/run.py evals/cases.json --live-provider --report output/evals/live-gemini-report.json
```

無 key 時：skip with reason。

有 key 時：產出 sanitized trace。

---

### 5. 收斂 verified profile fact disclosure 產品規則

決策後同步改：

*   `companion.md` prompt。
*   `guardian_agent.py`。
*   `response-card-contract.md`。
*   eval cases。
*   frontend card label / utterance display。

---

### 6. 決定 `.ai-bridge` 是否保留

如果要給 agent 本地接手，可以保留。

如果要 clean PR，建議移出 git tracked files 或加入 ignore。這不是產品邏輯，別讓 reviewer 被 10k 行 pro-context 打到眼神失焦。

---

## 🧱 不可回退的產品安全規則

下一個 agent 改 code 時必須守住以下規則：

1.   **不要生成醫療建議**：不能推薦、排序、比較安全性、比較副作用、說某藥適合/不適合。
2.   **產品表格只整理藥師說過的 facts**：name、price、purpose、directions、cautions。
3.   **Profile facts 只能作為請 pharmacist check 的材料**：不能由 AI 自行下結論。
4.   **Card lifecycle 不等於 conversation transcript**：card select/confirm/cancel 不可直接寫入 turns。
5.   **`KK 代说` 只能在真正 speech delivery 成功後出現**。
6.   **主工作區只顯示最新 faithful translation**，歷史留在右側 log/debug trace。
7.   **Provider internal thought/status text 不可進 user-facing transcript / translation / cards / summary**。
8.   **TTS 沒有 audio bytes 就不能標記 succeeded**。
9.   **typed fallback 是 deterministic debug path**，不能混 mic audio。
10.  **Eval 綠不等於 browser 真流程綠**，產品 ready 必須有 browser backend smoke。

---

## ✅ Definition of Done for 下一輪

任何下一輪宣稱「Pharmacy Counter E2E Ready」前，至少必須滿足：

```bash
backend/.venv/bin/python -m pytest backend/tests
backend/.venv/bin/python -m pytest evals/test_runner.py -q
backend/.venv/bin/python evals/run.py evals/cases.json --report /tmp/kithkin-eval-report.json
cd frontend && npm run typecheck
cd frontend && npm run lint
cd frontend && npm run test
cd frontend && PLAYWRIGHT_BACKEND_MODE=deterministic npx playwright test e2e/pharmacy-backend-deterministic.spec.ts
```

並且 browser / trace 證明：

*   confirmed card speech 有 binary frame delivery。
*   frontend audio player 有 playback scheduling evidence。
*   product options table 至少 render 一次。
*   purchase/payment flow 完整跑通。
*   session end 後收到 `summary.render`。
*   no user-facing text contains `**Analyzing` / `**Awaiting` / `Interpreting the User`。
*   conversation log 沒有 fake `KK 代说`。
*   main large-print area 顯示最新 faithful Chinese translation。

---

## 📌 給下一個 Agent 的一句話任務

不要再從零理解整個專案。先跑現有 verification，再從 `docs/pharmacy_counter_current_tdd_plan.md` 的 TDD-01 / TDD-03 / TDD-05 / TDD-07 / TDD-08 開始。這版的核心已經從「救 P0」變成「把剩餘產品流程和真 provider 評估收口」。
