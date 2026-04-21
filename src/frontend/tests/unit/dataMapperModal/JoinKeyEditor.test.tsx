import { render, screen, fireEvent } from "@testing-library/react";
import { JoinKeyEditor } from "@/modals/dataMapperModal/components/JoinKeyEditor";

const DRIVER_FIELDS = [
  { name: "job_id", type: "str" as const, required: false },
  { name: "org_id", type: "str" as const, required: false },
];
const LOOKUP_FIELDS = [
  { name: "id", type: "str" as const, required: false },
  { name: "org", type: "str" as const, required: false },
];

test("renders one row per key with both dropdowns", () => {
  render(
    <JoinKeyEditor
      keys={[{ driver_field: "job_id", lookup_field: "id" }]}
      driverFields={DRIVER_FIELDS}
      lookupFields={LOOKUP_FIELDS}
      onKeysChange={() => {}}
    />,
  );
  const selects = screen.getAllByRole("combobox");
  expect(selects).toHaveLength(2);
});

test("Add key appends a blank row via onKeysChange", () => {
  const onKeysChange = jest.fn();
  render(
    <JoinKeyEditor
      keys={[{ driver_field: "job_id", lookup_field: "id" }]}
      driverFields={DRIVER_FIELDS}
      lookupFields={LOOKUP_FIELDS}
      onKeysChange={onKeysChange}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /add key/i }));
  expect(onKeysChange).toHaveBeenCalledWith([
    { driver_field: "job_id", lookup_field: "id" },
    { driver_field: "", lookup_field: "" },
  ]);
});

test("changing driver_field calls onKeysChange with updated tuple", () => {
  const onKeysChange = jest.fn();
  render(
    <JoinKeyEditor
      keys={[{ driver_field: "job_id", lookup_field: "id" }]}
      driverFields={DRIVER_FIELDS}
      lookupFields={LOOKUP_FIELDS}
      onKeysChange={onKeysChange}
    />,
  );
  const [driverSelect] = screen.getAllByRole("combobox");
  fireEvent.change(driverSelect, { target: { value: "org_id" } });
  expect(onKeysChange).toHaveBeenCalledWith([
    { driver_field: "org_id", lookup_field: "id" },
  ]);
});

test("remove button is disabled when only one key remains", () => {
  render(
    <JoinKeyEditor
      keys={[{ driver_field: "job_id", lookup_field: "id" }]}
      driverFields={DRIVER_FIELDS}
      lookupFields={LOOKUP_FIELDS}
      onKeysChange={() => {}}
    />,
  );
  const removeBtn = screen.getByRole("button", { name: /−|remove/i });
  expect(removeBtn).toBeDisabled();
});

test("remove button is enabled with 2+ keys and removes by index", () => {
  const onKeysChange = jest.fn();
  render(
    <JoinKeyEditor
      keys={[
        { driver_field: "job_id", lookup_field: "id" },
        { driver_field: "org_id", lookup_field: "org" },
      ]}
      driverFields={DRIVER_FIELDS}
      lookupFields={LOOKUP_FIELDS}
      onKeysChange={onKeysChange}
    />,
  );
  const removeButtons = screen.getAllByRole("button", { name: /−|remove/i });
  expect(removeButtons).toHaveLength(2);
  fireEvent.click(removeButtons[0]); // remove first key
  expect(onKeysChange).toHaveBeenCalledWith([
    { driver_field: "org_id", lookup_field: "org" },
  ]);
});
