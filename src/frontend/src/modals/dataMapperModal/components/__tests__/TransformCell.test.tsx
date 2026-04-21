import { render, screen, fireEvent } from "@testing-library/react";
import { TransformCell } from "@/modals/dataMapperModal/components/TransformCell";
import { InputDef, MappingEntry } from "@/modals/dataMapperModal/types";

const INPUTS: InputDef[] = [
  {
    alias: "workers",
    schema_source: "autodetect",
    schema: {
      fields: [
        { name: "user_id", type: "str", required: false },
        { name: "first_name", type: "str", required: false },
      ],
    },
  },
];

function m(partial: Partial<MappingEntry>): MappingEntry {
  return {
    destination: "Dest",
    transform: "direct",
    sources: [],
    config: {},
    ...partial,
  };
}

test("direct: renders input+field dropdowns and fires onMappingChange with new source", () => {
  const onMappingChange = jest.fn();
  render(<TransformCell mapping={m({ transform: "direct" })} inputs={INPUTS} onMappingChange={onMappingChange} />);
  const selects = screen.getAllByRole("combobox");
  fireEvent.change(selects[0], { target: { value: "workers" } });
  expect(onMappingChange).toHaveBeenCalled();
  const last = onMappingChange.mock.calls.at(-1)![0];
  expect(last.sources[0].input).toBe("workers");
});

test("template: renders textarea with current template and emits config.template on change", () => {
  const onMappingChange = jest.fn();
  render(<TransformCell mapping={m({ transform: "template", config: { template: "{{ name }}" } })} inputs={INPUTS} onMappingChange={onMappingChange} />);
  const ta = screen.getByRole("textbox");
  expect((ta as HTMLTextAreaElement).value).toBe("{{ name }}");
  fireEvent.change(ta, { target: { value: "{{ first }} {{ last }}" } });
  expect(onMappingChange.mock.calls.at(-1)![0].config.template).toBe("{{ first }} {{ last }}");
});

test("expression: renders input and emits config.expression", () => {
  const onMappingChange = jest.fn();
  render(<TransformCell mapping={m({ transform: "expression", config: { expression: "a + b" } })} inputs={INPUTS} onMappingChange={onMappingChange} />);
  const input = screen.getByRole("textbox");
  fireEvent.change(input, { target: { value: "x * 2" } });
  expect(onMappingChange.mock.calls.at(-1)![0].config.expression).toBe("x * 2");
});

test("static: renders textarea with JSON-stringified value; valid JSON updates config.value", () => {
  const onMappingChange = jest.fn();
  render(<TransformCell mapping={m({ transform: "static", config: { value: "EMEA" } })} inputs={INPUTS} onMappingChange={onMappingChange} />);
  const ta = screen.getByRole("textbox");
  fireEvent.change(ta, { target: { value: '"US"' } });
  const last = onMappingChange.mock.calls.at(-1)![0];
  expect(last.config.value).toBe("US");
});

test("variable: renders input and emits config.variable", () => {
  const onMappingChange = jest.fn();
  render(<TransformCell mapping={m({ transform: "variable", config: { variable: "current_timestamp" } })} inputs={INPUTS} onMappingChange={onMappingChange} />);
  const input = screen.getByRole("textbox");
  fireEvent.change(input, { target: { value: "api_key" } });
  expect(onMappingChange.mock.calls.at(-1)![0].config.variable).toBe("api_key");
});

test("array: 'Add source' appends an empty source; 'skip_missing' toggle flips config", () => {
  const onMappingChange = jest.fn();
  render(<TransformCell mapping={m({ transform: "array", sources: [], config: { skip_missing: false } })} inputs={INPUTS} onMappingChange={onMappingChange} />);
  fireEvent.click(screen.getByRole("button", { name: /add source/i }));
  expect(onMappingChange.mock.calls.at(-1)![0].sources).toHaveLength(1);

  onMappingChange.mockClear();
  fireEvent.click(screen.getByRole("checkbox"));
  expect(onMappingChange.mock.calls.at(-1)![0].config.skip_missing).toBe(true);
});
