import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StatusBar } from "./StatusBar";


describe("StatusBar", () => {
  it("renders white header layout with pill badges and settings button", () => {
    const handleToggle = vi.fn();
    render(<StatusBar status="listening" onToggleDevMode={handleToggle} />);

    // Brand and logo
    expect(screen.getByText("Kith&Kin 药房陪伴助手")).toBeInTheDocument();

    // Pills
    expect(screen.getByText("Current: Pharmacy visit")).toBeInTheDocument();
    expect(screen.getByText("English ↔ 中文")).toBeInTheDocument();
    expect(screen.getByText("Voice Ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Settings" })).toBeInTheDocument();

    // Dev mode toggle
    const logoButton = screen.getByTestId("dev-mode-toggle");
    fireEvent.click(logoButton);
    expect(handleToggle).toHaveBeenCalledOnce();
  });
});
