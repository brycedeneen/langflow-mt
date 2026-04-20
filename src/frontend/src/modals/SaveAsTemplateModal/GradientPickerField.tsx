import { gradients } from "@/utils/styleUtils";

type Props = {
  /** Selected index, stringified to match the API payload shape. */
  value: string;
  onChange: (value: string) => void;
};

export default function GradientPickerField({ value, onChange }: Props) {
  const selectedIndex = Number.parseInt(value, 10);
  return (
    <div
      role="radiogroup"
      aria-label="Gradient"
      className="grid grid-cols-4 gap-2"
    >
      {gradients.map((gradientClass, index) => {
        const isSelected = index === selectedIndex;
        return (
          <button
            key={index}
            type="button"
            role="radio"
            aria-checked={isSelected}
            data-testid={`gradient-swatch-${index}`}
            data-selected={isSelected ? "true" : "false"}
            className={`h-10 w-full rounded-md ring-2 ring-offset-1 ${gradientClass} ${
              isSelected ? "ring-primary" : "ring-transparent"
            }`}
            onClick={() => onChange(String(index))}
          />
        );
      })}
    </div>
  );
}
