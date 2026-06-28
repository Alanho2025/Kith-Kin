import { test, expect } from "@playwright/test";
import { execSync } from "child_process";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe("Kith&Kin 藥局場景 3 輪對話測試", () => {
  test.beforeAll(() => {
    // 重新 Seed 數據庫確保數據一致性，並在 backend/kithkin.db 寫入 Demo 資料
    console.log("正在重新 Seed 後端數據庫...");
    let pythonCmd = "python";
    const localVenv = path.join(__dirname, "../../backend/.venv/bin/python");
    const winVenv = path.join(__dirname, "../../backend/.venv/Scripts/python.exe");
    if (fs.existsSync(localVenv)) {
      pythonCmd = localVenv;
    } else if (fs.existsSync(winVenv)) {
      pythonCmd = winVenv;
    }
    execSync(
      `${pythonCmd} -m scripts.seed_demo_data --database-url sqlite+aiosqlite:///backend/kithkin.db`,
      {
        cwd: "../",
        stdio: "inherit",
      }
    );
  });

  test("跑通老人在藥局的三輪對話且正常播放聲音", async ({ page }) => {
    // 1. 打開首頁
    await page.goto("/");

    await page.getByRole("button", { name: "开始药房对话" }).click();

    await expect(page.getByRole("button", { name: "听药剂师说话" })).toBeVisible();
    await expect(page.getByRole("button", { name: "按住说中文" })).toBeVisible();
    await expect(page.getByText("听懂药剂师，再安全回应")).toBeVisible();
    await expect(page.getByLabel("忠实中文翻译")).toContainText("您有在服用降压药吗？");
    await expect(page.getByRole("complementary", { name: "对话记录" }).first()).toContainText(
      "Are you taking any blood pressure medicine?",
    );

    await expect(page.getByText("安全检查已完成")).toBeVisible();

    const responseCard = page
      .locator('button:has-text("降血压药冲突")')
      .or(page.locator('button:has-text("blood pressure medicine")'))
      .first();
    await expect(responseCard).toBeVisible();
    await responseCard.click();

    await expect(page.locator("#confirmation-title")).toContainText("你要让我用英文说这句吗？");
    await expect(page.getByRole("button", { name: "替我说" })).toBeVisible();
  });
});
