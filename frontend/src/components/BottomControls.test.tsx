import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RuntimeCommandView } from "../features/conversation/viewModels";
import { BottomControls } from "./BottomControls";


describe("BottomControls", () => {
  it("renders only global controls that are not duplicated by the main voice controls", () => {
    const commands: RuntimeCommandView[] = [];
    render(<BottomControls onCommand={(command) => commands.push(command)} />);

    expect(screen.queryByRole("button", { name: "我自己说" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重复" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "请稍等" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "结束" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "请稍等" }));

    expect(commands).toEqual([{ eventType: "control.please_wait", payload: {} }]);
  });
});
