import { test, expect } from "@playwright/test";

test.describe("Kith&Kin 藥局場景 backend smoke", () => {
  test("真实后端 typed pharmacist flow keeps main UI coherent through products and summary", async ({ page }) => {
    page.on("dialog", (dialog) => dialog.accept());

    await page.goto("/");
    await page.getByRole("button", { name: "真实后端 (Backend)" }).click();
    await page.getByRole("button", { name: "开始药房对话" }).click();

    await expect(page.getByRole("button", { name: "听药剂师说话" })).toBeVisible();
    const typedPharmacist = page.getByPlaceholder("语音无效时输入医护人员英文");

    await typedPharmacist.fill("Good morning. How are you today?");
    await typedPharmacist.press("Enter");
    await expect(page.getByLabel("忠实中文翻译")).toContainText("Good morning");

    await typedPharmacist.fill("Can you give me your birthday and name?");
    await typedPharmacist.press("Enter");
    await expect(page.getByRole("complementary", { name: "对话记录" }).first()).toContainText(
      "Can you give me your birthday and name?",
    );

    await typedPharmacist.fill(
      "Before I suggest anything, do you have any allergies or do you take blood pressure medicine?",
    );
    await typedPharmacist.press("Enter");
    await expect(page.getByLabel("忠实中文翻译")).toContainText("allergies");

    await typedPharmacist.fill(
      "I can show you three options. Panadol costs eight dollars and is for pain and fever. Nurofen costs twelve dollars and is for pain and inflammation, but please check with me if you take blood pressure medicine. Voltaren gel costs fifteen dollars and is for local muscle pain; do not apply it to broken skin.",
    );
    await typedPharmacist.press("Enter");

    await expect(page.getByLabel("忠实中文翻译")).toContainText("Panadol");
    await expect(page.getByRole("region", { name: "药师说的产品选项" })).toBeVisible();
    await expect(page.getByRole("region", { name: "药师说的产品选项" })).toContainText("Nurofen");
    await expect(page.getByRole("region", { name: "药师说的产品选项" })).toContainText("Voltaren");
    await expect(page.getByRole("complementary", { name: "对话记录" }).first()).not.toContainText(
      "KK 代说",
    );

    await page.getByRole("button", { name: "结束" }).click();
    await expect(page.getByRole("heading", { name: /今天药局沟通重点/ })).toBeVisible();
    await expect(page.getByText(/Panadol|Nurofen|Voltaren/)).toBeVisible();
  });
});
