import { makeEvent } from "./runtime-events";


export const mockPrivacyFlow = [
  makeEvent("guardian.warning", "evt-warning", {
    warningId: "warning-privacy",
    type: "privacy",
    zhTitle: "这个问题涉及个人信息",
    zhMessage: "KK 不会自动说出您的个人信息。",
  }),
];
