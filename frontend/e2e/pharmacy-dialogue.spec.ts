import { expect, test } from "@playwright/test";

test.describe("Kith&Kin elder-first conversation UI", () => {
  test("shows voice control, translation, cards, confirmation, and conversation log", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: "开始药房对话" }).click();

    await expect(page.getByRole("button", { name: "听药剂师说话" })).toBeVisible();
    await expect(page.getByRole("button", { name: "按住说中文" })).toBeVisible();
    await expect(page.getByText("听懂药剂师，再安全回应")).toBeVisible();
    await expect(page.getByLabel("忠实中文翻译")).toContainText("您有在服用降压药吗？");
    await expect(page.getByRole("complementary", { name: "对话记录" })).toContainText(
      "Are you taking any blood pressure medicine?",
    );

    const responseCard = page
      .locator('button:has-text("降血压药冲突")')
      .or(page.locator('button:has-text("blood pressure medicine")'))
      .first();
    await expect(responseCard).toBeVisible();
    await responseCard.click();

    await expect(page.locator("#confirmation-title")).toContainText("你要让我用英文说这句吗？");
    await expect(page.getByRole("button", { name: "替我说" })).toBeVisible();
    await expect(page.getByText("安全检查已完成")).toBeVisible();
  });
});
