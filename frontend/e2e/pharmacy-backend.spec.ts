import { test, expect } from "@playwright/test";

test.describe("Kith&Kin 藥局場景 backend smoke", () => {
  test("真实后端 typed pharmacist flow keeps main UI coherent through products and summary", async ({ page }) => {
    page.on("dialog", (dialog) => dialog.accept());
    const browserDebugLines: string[] = [];
    await page.addInitScript(() => {
      window.localStorage.setItem("kk_debug_conversation", "1");
    });
    page.on("console", (message) => {
      const text = message.text();
      if (!text.includes("[KK conversation]")) return;
      browserDebugLines.push(text);
      console.log(`[BrowserConsole] ${text}`);
    });
    let wsReceivedBinaryFrames = 0;
    page.on("websocket", (socket) => {
      socket.on("framereceived", (frame) => {
        if (typeof frame.payload !== "string") wsReceivedBinaryFrames += 1;
      });
    });

    await page.goto("/");
    await page.getByRole("button", { name: "真实后端 (Backend)" }).click();
    await page.getByRole("button", { name: "开始药房对话" }).click();

    await expect(page.getByRole("button", { name: "听药剂师说话" })).toBeVisible();
    const typedPharmacist = page.getByPlaceholder("语音无效时输入医护人员英文");
    const mainTranslation = page.getByLabel("忠实中文翻译");
    const conversationLog = page.getByRole("complementary", { name: "对话记录" }).first();

    await typedPharmacist.fill("Good morning. How are you today?");
    await typedPharmacist.press("Enter");
    await expect(conversationLog).toContainText("Good morning. How are you today?");

    await typedPharmacist.fill("Can you give me your birthday and name?");
    await typedPharmacist.press("Enter");
    await expect(conversationLog).toContainText("Can you give me your birthday and name?");

    await page.getByRole("button", { name: /生日.*点击后确认/ }).first().click();
    await page.getByRole("button", { name: "替我说" }).click();
    await expect.poll(() => wsReceivedBinaryFrames, { timeout: 30000 }).toBeGreaterThan(0);
    const framesAfterIdentityCard = wsReceivedBinaryFrames;
    await expect(conversationLog).not.toContainText("KK 代说");
    await expect(page.getByText("Voice Ready")).toBeVisible({ timeout: 30000 });

    await typedPharmacist.fill(
      "Before I suggest anything, do you have any allergies or do you take blood pressure medicine?",
    );
    await typedPharmacist.press("Enter");
    await expect(conversationLog).toContainText("allergies");
    const allergyDisclosureCard = page
      .getByRole("button", { name: /青霉素|Penicillin|过敏/ })
      .first();
    await expect(allergyDisclosureCard).toBeVisible({ timeout: 45000 });
    await allergyDisclosureCard.click();
    await page.getByRole("button", { name: "替我说" }).click();
    await expect
      .poll(() => wsReceivedBinaryFrames, { timeout: 30000 })
      .toBeGreaterThan(framesAfterIdentityCard);
    await expect(conversationLog).not.toContainText("KK 代说");
    await expect(page.getByText("Voice Ready")).toBeVisible({ timeout: 30000 });

    await typedPharmacist.fill(
      "I can show you three options. Panadol costs eight dollars and is for pain and fever. Nurofen costs twelve dollars and is for pain and inflammation, but please check with me if you take blood pressure medicine. Voltaren gel costs fifteen dollars and is for local muscle pain; do not apply it to broken skin.",
    );
    await typedPharmacist.press("Enter");

    await expect(mainTranslation).not.toContainText("中文翻译会显示在这里");
    await expect(page.getByRole("region", { name: "药师说的产品选项" })).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByRole("region", { name: "药师说的产品选项" })).toContainText("Panadol");
    await expect(page.getByRole("region", { name: "药师说的产品选项" })).toContainText("Nurofen");
    await expect(page.getByRole("region", { name: "药师说的产品选项" })).toContainText("Voltaren");
    await expect(conversationLog).not.toContainText("KK 代说");

    await page.getByRole("button", { name: "结束" }).click();
    await expect(page.getByRole("heading", { name: /今天药局沟通重点/ })).toBeVisible();
    await expect(page.getByText(/Panadol|Nurofen|Voltaren/)).toBeVisible();

    for (const label of [
      "app.start",
      "runtime.websocket.open",
      "page.typed_pharmacist.submit",
      "hook.runtime_event.received",
      "response_card.click",
      "card.confirm",
      "runtime.websocket.audio.in",
      "audio_player.play.scheduled",
      "bottom_controls.end.confirmed",
    ]) {
      expect(
        browserDebugLines.some((line) => line.includes(`[KK conversation] ${label}`)),
      ).toBe(true);
    }
  });
});
