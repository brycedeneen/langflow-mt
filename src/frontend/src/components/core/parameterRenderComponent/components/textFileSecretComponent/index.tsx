// STUB — Task 17 replaces this with a Paste/Upload tab toggle renderer.
// For now this lets the dispatch case in index.tsx compile.

import type { InputProps } from "../../types";

export type TextFileSecretComponentType = {
  file_types?: string[];
};

export default function TextFileSecretComponent({
  id,
  value,
  handleOnNewValue,
  disabled,
}: InputProps<string, TextFileSecretComponentType>) {
  return (
    <input
      id={id}
      type="text"
      value={value ?? ""}
      onChange={(e) => handleOnNewValue({ value: e.target.value })}
      disabled={disabled}
    />
  );
}
