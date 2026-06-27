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
    const testInput = page.getByPlaceholder(/测试输入：模拟药剂师的英文发言/);
    const sendBtn = page.getByRole("button", { name: "发送" });

    // --- 第一輪對話：確認過敏記錄 ---
    console.log("--- 第一輪對話：確認過敏記錄 ---");
    await testInput.fill("Do you have any drug allergies?");
    await sendBtn.click();

    // 尋找對應青黴素（Penicillin）過敏的卡片或過敏確認卡片
    const penicillinCard = page
      .locator('button:has-text("Penicillin")')
      .or(page.locator('button:has-text("allergy")'))
      .or(page.locator('button:has-text("过敏")'))
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
      .first();
    await expect(conflictCard).toBeVisible({ timeout: 20000 });
    await conflictCard.click();

    // 確認並發聲
    await expect(confirmTitle).toContainText("确认让 KK 代您表达");
    await speakBtn.click();

    // 等待最後一輪發聲結束
    await expect(statusBar).toContainText("KK 正在说话", { timeout: 10000 });
    await expect(statusBar).toContainText("KK 正在聆听", { timeout: 25000 });

    console.log("測試完成！三輪對話流程成功跑通。");
  });
});
