import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { VisitSummaryPage } from "./VisitSummaryPage";


describe("VisitSummaryPage", () => {
  it("shows exactly what can be sent and requires an explicit action", () => {
    const onSend = vi.fn();
    render(
      <VisitSummaryPage
        summary={{
          titleZh: "今天药局沟通重点",
          mentionedDrugs: ["降压药"],
          pharmacistAdviceSummaryZh: "请核对完整用药清单。",
          unresolvedQuestionsZh: ["请家人确认药名。"],
          followUpNeeded: true,
        }}
        onSend={onSend}
        onSave={() => undefined}
        onCancel={() => undefined}
      />,
    );

    expect(screen.getByText("降压药")).toBeInTheDocument();
    expect(screen.getByText("请核对完整用药清单。")).toBeInTheDocument();
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "发送给家人" }));
    expect(onSend).toHaveBeenCalledOnce();
  });
});
