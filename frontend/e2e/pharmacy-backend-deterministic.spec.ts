import { expect, test } from "@playwright/test";

test.describe("Kith&Kin deterministic backend smoke", () => {
  test("uses the real backend with seeded data without the live Gemini provider", async ({
    page,
  }) => {
    page.on("dialog", (dialog) => dialog.accept());
    const browserDebugLines: string[] = [];
    await page.addInitScript(() => {
      window.localStorage.setItem("kk_debug_conversation", "1");
    });
    page.on("console", (message) => {
      const text = message.text();
      if (!text.includes("[KK conversation]")) return;
      browserDebugLines.push(text);
    });

    await page.goto("/");
    await page.getByRole("button", { name: "真实后端 (Backend)" }).click();
    await page.getByRole("button", { name: "开始药房对话" }).click();

    await expect(page.getByRole("button", { name: "听药剂师说话" })).toBeVisible();
    const typedPharmacist = page.getByPlaceholder("语音无效时输入医护人员英文");
    const conversationLog = page.getByRole("complementary", { name: "对话记录" }).first();

    await typedPharmacist.fill("Can you give me your birthday and name?");
    await typedPharmacist.press("Enter");
    await expect(conversationLog).toContainText("Can you give me your birthday and name?");
    await expect(page.getByRole("button", { name: /生日.*点击后确认/ }).first()).toBeVisible({
      timeout: 30000,
    });

    await typedPharmacist.fill(
      "I can show you three options. Panadol costs eight dollars and is for pain and fever. Nurofen costs twelve dollars and is for pain and inflammation, but please check with me if you take blood pressure medicine. Voltaren gel costs fifteen dollars and is for local muscle pain; do not apply it to broken skin.",
    );
    await typedPharmacist.press("Enter");

    const productOptions = page.getByRole("region", { name: "药师说的产品选项" });
    await expect(productOptions).toBeVisible({ timeout: 30000 });
    await expect(productOptions).toContainText("Panadol");
    await expect(productOptions).toContainText("Nurofen");
    await expect(productOptions).toContainText("Voltaren");
    await expect(conversationLog).not.toContainText("KK 代说");

    await page.getByRole("button", { name: "结束" }).click();
    await expect(page.getByRole("heading", { name: /今天药局沟通重点/ })).toBeVisible();
    await expect(page.getByText(/Panadol|Nurofen|Voltaren/)).toBeVisible();

    for (const label of [
      "app.start",
      "runtime.websocket.open",
      "page.typed_pharmacist.submit",
      "runtime.event.emit",
      "bottom_controls.end.confirmed",
    ]) {
      expect(
        browserDebugLines.some((line) => line.includes(`[KK conversation] ${label}`)),
      ).toBe(true);
    }

    expect(
      browserDebugLines.some((line) => line.includes("[KK conversation] mock_runtime")),
    ).toBe(false);
  });
});
