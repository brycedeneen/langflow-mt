import { render, screen, fireEvent } from "@testing-library/react";
import { MetadataEditForm } from "../metadata-edit-form";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

describe("MetadataEditForm", () => {
  it("renders two textareas labeled 'Agent summary' and 'Agent usage notes'", () => {
    render(
      <MetadataEditForm
        initial={{ agent_summary: null, agent_usage_notes: null }}
        onSave={jest.fn()}
        onCancel={jest.fn()}
      />,
    );
    expect(screen.getByLabelText(/agent summary/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/agent usage notes/i)).toBeInTheDocument();
  });

  it("submits the entered values", () => {
    const onSave = jest.fn();
    render(
      <MetadataEditForm
        initial={{ agent_summary: null, agent_usage_notes: null }}
        onSave={onSave}
        onCancel={jest.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/agent summary/i), {
      target: { value: "Short summary" },
    });
    fireEvent.change(screen.getByLabelText(/agent usage notes/i), {
      target: { value: "Detailed notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    expect(onSave).toHaveBeenCalledWith({
      agent_summary: "Short summary",
      agent_usage_notes: "Detailed notes",
    });
  });

  it("shows a Delete button only when the row already exists and onDelete is provided", () => {
    const { rerender } = render(
      <MetadataEditForm
        initial={{ agent_summary: null, agent_usage_notes: null }}
        onSave={jest.fn()}
        onCancel={jest.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: /delete metadata/i })).toBeNull();

    rerender(
      <MetadataEditForm
        initial={{ agent_summary: "s", agent_usage_notes: "n" }}
        onSave={jest.fn()}
        onCancel={jest.fn()}
        onDelete={jest.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /delete metadata/i }),
    ).toBeInTheDocument();
  });
});
