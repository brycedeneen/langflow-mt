import { render, screen, fireEvent } from "@testing-library/react";
import { SchemaSourceTabs } from "@/modals/dataMapperModal/components/SchemaSourceTabs";

test("renders all three tabs and calls onSourceChange when a tab is clicked", () => {
  const onSourceChange = jest.fn();
  render(<SchemaSourceTabs source="autodetect" onSourceChange={onSourceChange} onSampleChange={() => {}} onJsonSchemaChange={() => {}} />);
  expect(screen.getByText("Autodetect")).toBeInTheDocument();
  expect(screen.getByText("Paste sample")).toBeInTheDocument();
  expect(screen.getByText("JSON Schema")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Paste sample"));
  expect(onSourceChange).toHaveBeenCalledWith("sample");
});

test("autodetect tab shows a hint when fields is null", () => {
  render(
    <SchemaSourceTabs
      source="autodetect"
      fields={null}
      onSourceChange={() => {}}
      onSampleChange={() => {}}
      onJsonSchemaChange={() => {}}
    />,
  );
  expect(screen.getByText(/run this flow once/i)).toBeInTheDocument();
});

test("paste-sample tab renders a textarea", () => {
  render(
    <SchemaSourceTabs
      source="sample"
      onSourceChange={() => {}}
      onSampleChange={() => {}}
      onJsonSchemaChange={() => {}}
    />,
  );
  expect(screen.getByRole("textbox")).toBeInTheDocument();
});
