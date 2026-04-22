import { MembershipRole, ROLE_METADATA, ROLE_ORDER, canAssignRole } from "../roles";

describe("ROLE_METADATA", () => {
  it("has an entry for every role", () => {
    const roles: MembershipRole[] = ["owner", "admin", "member", "operator", "viewer"];
    roles.forEach(r => expect(ROLE_METADATA[r]).toBeDefined());
  });

  it("orders roles owner > admin > member > operator > viewer", () => {
    expect(ROLE_ORDER.owner).toBeGreaterThan(ROLE_ORDER.admin);
    expect(ROLE_ORDER.admin).toBeGreaterThan(ROLE_ORDER.member);
    expect(ROLE_ORDER.member).toBeGreaterThan(ROLE_ORDER.operator);
    expect(ROLE_ORDER.operator).toBeGreaterThan(ROLE_ORDER.viewer);
  });
});

describe("canAssignRole (mirrors backend escalation guard)", () => {
  it("allows owner to assign any role", () => {
    (["owner","admin","member","operator","viewer"] as MembershipRole[]).forEach(target => {
      expect(canAssignRole({ caller: "owner", current: "member", next: target })).toBe(true);
    });
  });

  it("blocks admin from assigning admin or owner", () => {
    expect(canAssignRole({ caller: "admin", current: "member", next: "admin" })).toBe(false);
    expect(canAssignRole({ caller: "admin", current: "member", next: "owner" })).toBe(false);
  });

  it("blocks admin from changing an owner/admin row", () => {
    expect(canAssignRole({ caller: "admin", current: "admin", next: "member" })).toBe(false);
    expect(canAssignRole({ caller: "admin", current: "owner", next: "member" })).toBe(false);
  });

  it("allows admin to move among member/operator/viewer", () => {
    expect(canAssignRole({ caller: "admin", current: "member", next: "viewer" })).toBe(true);
    expect(canAssignRole({ caller: "admin", current: "viewer", next: "operator" })).toBe(true);
  });

  it("blocks member and below from assigning anything", () => {
    (["member","operator","viewer"] as MembershipRole[]).forEach(caller => {
      expect(canAssignRole({ caller, current: "viewer", next: "member" })).toBe(false);
    });
  });
});
