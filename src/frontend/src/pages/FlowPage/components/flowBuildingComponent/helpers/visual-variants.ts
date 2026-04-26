export const getTimeVariants = (
  buttonRef: React.RefObject<HTMLDivElement | null>,
) => {
  const errorButtonsWidth = buttonRef.current?.offsetWidth ?? 0;
  return {
    single: { x: 0, width: "auto" },
    double: { x: -errorButtonsWidth - 15, width: "auto" },
  };
};
