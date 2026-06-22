import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GuardianWarningCard } from "./GuardianWarningCard";


describe("GuardianWarningCard", () => {
  it("warning is not translation", () => {
    render(
      <GuardianWarningCard
        warning={{
          warningId: "warning-1",
          type: "privacy",
          zhTitle: "这个问题涉及个人信息",
          zhMessage: "KK 不会自动说出您的个人信息。",
        }}
      />,
    );

    const warning = screen.getByRole("alert");
    expect(warning).toHaveTextContent("隐私提醒");
    expect(warning).toHaveTextContent("这个问题涉及个人信息");
    expect(screen.queryByLabelText("忠实中文翻译")).not.toBeInTheDocument();
  });
});
