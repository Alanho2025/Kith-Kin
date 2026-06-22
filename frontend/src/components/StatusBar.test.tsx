import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBar } from "./StatusBar";


describe("StatusBar", () => {
  it("shows status from runtime events", () => {
    render(<StatusBar status="listening" />);

    expect(screen.getByText("KK 正在聆听")).toBeInTheDocument();
  });
});
