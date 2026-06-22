import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RuntimeCommandView } from "../features/conversation/viewModels";
import { BottomControls } from "./BottomControls";


describe("BottomControls", () => {
  it("self speak sends escape only", () => {
    const commands: RuntimeCommandView[] = [];
    render(<BottomControls onCommand={(command) => commands.push(command)} />);

    fireEvent.click(screen.getByRole("button", { name: "我自己说" }));

    expect(commands).toEqual([{ eventType: "control.self_speak", payload: {} }]);
  });
});
