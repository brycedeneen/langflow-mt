import { describe, it, expect, beforeEach } from "@jest/globals";
import useAuthStore from "../authStore";

describe("authStore.isPlatformAdmin", () => {
  beforeEach(() => {
    useAuthStore.setState({ isAdmin: false, isPlatformAdmin: false });
  });

  it("defaults to false", () => {
    expect(useAuthStore.getState().isPlatformAdmin).toBe(false);
  });

  it("setIsPlatformAdmin updates the flag", () => {
    useAuthStore.getState().setIsPlatformAdmin(true);
    expect(useAuthStore.getState().isPlatformAdmin).toBe(true);
  });

  it("logout resets isPlatformAdmin to false", async () => {
    useAuthStore.setState({ isPlatformAdmin: true });
    await useAuthStore.getState().logout();
    expect(useAuthStore.getState().isPlatformAdmin).toBe(false);
  });
});
