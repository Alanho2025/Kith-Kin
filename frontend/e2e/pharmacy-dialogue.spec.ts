import { test, expect } from "@playwright/test";
import { execSync } from "child_process";

test.describe("Kith&Kin 藥局場景 3 輪對話測試", () => {
  test.beforeAll(() => {
    // 重新 Seed 數據庫確保數據一致性，並在 backend/kithkin.db 寫入 Demo 資料
    console.log("正在重新 Seed 後端數據庫...");
    execSync(
      "python -m scripts.seed_demo_data --database-url sqlite+aiosqlite:///backend/kithkin.db",
      {
        cwd: "../",
        stdio: "inherit",
      }
    );
  });

  test("跑通老人在藥局的三輪對話且正常播放聲音", async ({ page }) => {
    // 1. 打開首頁
    await page.goto("/");

    // 2. 切換為真實後端模式
    const backendBtn = page.getByRole("button", { name: "真实后端 (Backend)" });
    await expect(backendBtn).toBeVisible();
    await backendBtn.click();

    // 3. 點擊開始對話
    const startBtn = page.getByRole("button", { name: "开始药房对话" });
    await expect(startBtn).toBeVisible();
    await startBtn.click();

    // 4. 等待狀態為 "KK 正在聆听"
    const statusBar = page.locator("header");
    await expect(statusBar).toContainText("KK 正在聆听", { timeout: 20000 });

    // 獲取測試輸入框與發送按鈕
    const testInput = page.getByPlaceholder(/語音無效時的替代文字輸入/);
    const sendBtn = page.getByRole("button", { name: "发送" });

    // --- 第一輪對話：確認過敏記錄 ---
    console.log("--- 第一輪對話：確認過敏記錄 ---");
    await testInput.fill("Do you have any drug allergies?");
    await sendBtn.click();

    // 尋找對應青黴素（Penicillin）過敏的卡片或過敏確認卡片
    const penicillinCard = page
      .locator('button:has-text("Penicillin")')
      .or(page.locator('button:has-text("allergy")'))
      .or(page.locator('button:has-text("allergies")'))
      .or(page.locator('button:has-text("过敏")'))
      .or(page.locator('button:has-text("過敏")'))
      .first();
    await expect(penicillinCard).toBeVisible({ timeout: 20000 });
    await penicillinCard.click();

    // 確認彈出確認 Sheet
    const confirmTitle = page.locator("#confirmation-title");
    await expect(confirmTitle).toContainText("确认让 KK 代您表达");
    const speakBtn = page.getByRole("button", { name: "确认并说给药剂师" });
    await expect(speakBtn).toBeVisible();
    await speakBtn.click();

    // 等待說話開始，再變回聆聽
    await expect(statusBar).toContainText("KK 正在说话", { timeout: 10000 });
    await expect(statusBar).toContainText("KK 正在聆听", { timeout: 25000 });

    // --- 第二輪對話：確認日常用藥 ---
    console.log("--- 第二輪對話：確認日常用藥 ---");
    await testInput.fill("Are you currently taking any other medications?");
    await sendBtn.click();

    // 尋找降壓藥 Lisinopril 的卡片或用藥確認卡片
    const lisinoprilCard = page
      .locator('button:has-text("Lisinopril")')
      .or(page.locator('button:has-text("medications")'))
      .or(page.locator('button:has-text("用药")'))
      .or(page.locator('button:has-text("用藥")'))
      .first();
    await expect(lisinoprilCard).toBeVisible({ timeout: 20000 });
    await lisinoprilCard.click();

    // 確認並發聲
    await expect(confirmTitle).toContainText("确认让 KK 代您表达");
    await speakBtn.click();

    // 等待說話開始與完成
    await expect(statusBar).toContainText("KK 正在说话", { timeout: 10000 });
    await expect(statusBar).toContainText("KK 正在聆听", { timeout: 25000 });

    // --- 第三輪對話：藥物衝突警示 ---
    console.log("--- 第三輪對話：藥物衝突警示 ---");
    await testInput.fill("I can recommend Ibuprofen for your pain.");
    await sendBtn.click();

    // 期待因為 Lisinopril + Ibuprofen 衝突而觸發警告或出現警告提醒
    // 尋找包含警告、衝突或 Ibuprofen 的卡片
    const conflictCard = page
      .locator('button:has-text("conflict")')
      .or(page.locator('button:has-text("Ibuprofen")'))
      .or(page.locator('button:has-text("ibuprofen")'))
      .or(page.locator('button:has-text("冲突")'))
      .or(page.locator('button:has-text("衝突")'))
      .first();
    await expect(conflictCard).toBeVisible({ timeout: 20000 });
    await conflictCard.click();

    // 確認並發聲
    await expect(confirmTitle).toContainText("确认让 KK 代您表达");
    await speakBtn.click();

    // 等待最後一輪發聲結束
    await expect(statusBar).toContainText("KK 正在说话", { timeout: 10000 });
    await expect(statusBar).toContainText("KK 正在聆听", { timeout: 25000 });

    // --- 測試底部控制按鈕：請稍等、我自己說、重複、結束 ---
    console.log("--- 測試底部控制按鈕 ---");

    // 1. 點擊「请稍等」 -> 狀態改為「准备好了」
    const pleaseWaitBtn = page.getByRole("button", { name: "请稍等" });
    await expect(pleaseWaitBtn).toBeVisible();
    await pleaseWaitBtn.click();
    await expect(statusBar).toContainText("准备好了", { timeout: 5000 });

    // 2. 點擊「我自己说」 -> 狀態改為「KK 正在聆听」
    const selfSpeakBtn = page.getByRole("button", { name: "我自己说" });
    await expect(selfSpeakBtn).toBeVisible();
    await selfSpeakBtn.click();
    await expect(statusBar).toContainText("KK 正在聆听", { timeout: 5000 });

    // 3. 點擊「重复」 -> 重新播報最後一次的內容（先說話後聆聽）
    const repeatBtn = page.getByRole("button", { name: "重复" });
    await expect(repeatBtn).toBeVisible();
    await repeatBtn.click();
    await expect(statusBar).toContainText("KK 正在说话", { timeout: 5000 });
    await expect(statusBar).toContainText("KK 正在聆听", { timeout: 15000 });

    // 4. 點擊「结束」 -> 渲染結算報告頁面
    const endBtn = page.getByRole("button", { name: "结束" });
    await expect(endBtn).toBeVisible();
    await endBtn.click();

    // 驗證進入結算報告頁，確認摘要標題存在
    const summaryTitle = page.locator("main h1");
    await expect(summaryTitle).toContainText("今天药局沟通重点", { timeout: 10000 });

    // 5. 點擊結算頁的「发送给家人」 -> 重啟回到首頁開始畫面
    const sendFamilyBtn = page.getByRole("button", { name: "发送给家人" });
    await expect(sendFamilyBtn).toBeVisible();
    await sendFamilyBtn.click();

    // 驗證是否重新回到 StartPage 首頁
    const startDialogueBtn = page.getByRole("button", { name: "开始药房对话" });
    await expect(startDialogueBtn).toBeVisible({ timeout: 5000 });

    console.log("測試完成！三輪對話與控制按鈕流程全部成功跑通。");
  });
});
