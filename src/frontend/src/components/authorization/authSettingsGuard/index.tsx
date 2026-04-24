export const AuthSettingsGuard = ({ children }) => {
  // Previously hidden under auto-login; now always visible.
  return children;
};
