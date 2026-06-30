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
    const conversationLog = page.getByRole("complementary", { name: "对话记录" }).first();

    // 1. Pharmacist asks for name and birthday
    await typedPharmacist.fill("Can you give me your birthday and name?");
    await typedPharmacist.press("Enter");
    await expect(conversationLog).toContainText("Can you give me your birthday and name?");
    
    // 2. Click the birthday confirmation card and submit
    const identityCard = page.getByRole("button", { name: /生日.*点击后确认/ }).first();
    await expect(identityCard).toBeVisible({ timeout: 30000 });
    await identityCard.click();
    await page.getByRole("button", { name: "替我说" }).click();
    await expect(page.getByText("Voice Ready")).toBeVisible({ timeout: 30000 });
    expect(wsReceivedBinaryFrames).toBeGreaterThan(0);
    const framesAfterIdentityCard = wsReceivedBinaryFrames;

    // 3. Pharmacist suggests three product options
    await typedPharmacist.fill(
      "I can show you three options. Panadol costs eight dollars and is for pain and fever. Nurofen costs twelve dollars and is for pain and inflammation, but please check with me if you take blood pressure medicine. Voltaren gel costs fifteen dollars and is for local muscle pain; do not apply it to broken skin.",
    );
    await typedPharmacist.press("Enter");

    const productOptions = page.getByRole("region", { name: "药师说的产品选项" });
    await expect(productOptions).toBeVisible({ timeout: 30000 });
    await expect(productOptions).toContainText("Panadol");
    await expect(productOptions).toContainText("Nurofen");
    await expect(productOptions).toContainText("Voltaren");

    // 4. Pharmacist asks which option to buy
    await typedPharmacist.fill("Which option would you like to buy? We have all of them in stock.");
    await typedPharmacist.press("Enter");

    // 5. Parent clicks "确认购买 Nurofen 并告诉药师" and clicks "替我说"
    const buyCard = page.getByRole("button", { name: /确认购买 Nurofen/ }).first();
    await expect(buyCard).toBeVisible({ timeout: 30000 });
    await buyCard.click();
    await page.getByRole("button", { name: "替我说" }).click();
    await expect(page.getByText("Voice Ready")).toBeVisible({ timeout: 30000 });
    expect(wsReceivedBinaryFrames).toBeGreaterThan(framesAfterIdentityCard);
    const framesAfterBuyCard = wsReceivedBinaryFrames;

    // 6. Pharmacist gives final price and payment instructions
    await typedPharmacist.fill("That will be 12 dollars. Would you like to pay with cash or card?");
    await typedPharmacist.press("Enter");

    // 7. Parent clicks "确认支付（用卡支付）" and clicks "替我说"
    const payCard = page.getByRole("button", { name: /确认支付.*卡支付/ }).first();
    await expect(payCard).toBeVisible({ timeout: 30000 });
    await payCard.click();
    await page.getByRole("button", { name: "替我说" }).click();
    await expect(page.getByText("Voice Ready")).toBeVisible({ timeout: 30000 });
    expect(wsReceivedBinaryFrames).toBeGreaterThan(framesAfterBuyCard);

    // 8. End the conversation and check summary
    await page.getByRole("button", { name: "结束" }).click();
    await expect(page.getByRole("heading", { name: /今天药局沟通重点/ })).toBeVisible();
    await expect(page.getByText(/Panadol|Nurofen|Voltaren/)).toBeVisible();

    // 9. Assert required debug labels in order
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

    expect(
      browserDebugLines.some((line) => line.includes("[KK conversation] mock_runtime")),
    ).toBe(false);
  });
});
