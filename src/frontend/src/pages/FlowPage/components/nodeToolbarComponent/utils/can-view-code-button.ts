export type CanViewCodeButtonInput = {
  hasCode: boolean;
  isSuperuser: boolean | undefined;
};

export function canViewCodeButton({
  hasCode,
  isSuperuser,
}: CanViewCodeButtonInput): boolean {
  return hasCode && isSuperuser === true;
}
