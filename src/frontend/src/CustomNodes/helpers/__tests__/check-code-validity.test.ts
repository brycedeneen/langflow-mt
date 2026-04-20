import checkCodeValidity from "../check-code-validity";

const fakeNode = (nodeOverrides: Record<string, unknown> = {}) => ({
  id: "n1",
  type: "MyComp",
  node: {
    display_name: "MyComp",
    description: "",
    documentation: "",
    template: { code: { value: "old code" } },
    outputs: [],
    ...nodeOverrides,
  } as any,
});

const template = (latestVersion: number, entries: Array<Record<string, unknown>> = [], code = "new code") => ({
  MyComp: {
    template: { code: { value: code } },
    outputs: [],
    version: latestVersion,
    changelog: entries,
  },
});

describe("checkCodeValidity — version fields", () => {
  it("returns defaults when neither node nor template declare version", () => {
    const result = checkCodeValidity(fakeNode() as any, template(0));
    expect(result?.userVersion).toBe(0);
    expect(result?.latestVersion).toBe(0);
    expect(result?.changelogEntries).toEqual([]);
  });

  it("filters and sorts entries between user and latest, newest first", () => {
    const entries = [
      { version: 1, changes: "c1", notes: null },
      { version: 2, changes: "c2", notes: "n2" },
      { version: 3, changes: "c3", notes: null },
    ];
    const result = checkCodeValidity(
      fakeNode({ version: 1 }) as any,
      template(3, entries),
    );
    expect(result?.userVersion).toBe(1);
    expect(result?.latestVersion).toBe(3);
    expect(result?.changelogEntries.map((e) => e.version)).toEqual([3, 2]);
  });

  it("includes all entries when node has no version (treated as 0)", () => {
    const entries = [
      { version: 1, changes: "c1", notes: null },
      { version: 2, changes: "c2", notes: null },
    ];
    const result = checkCodeValidity(fakeNode() as any, template(2, entries));
    expect(result?.userVersion).toBe(0);
    expect(result?.changelogEntries.map((e) => e.version)).toEqual([2, 1]);
  });

  it("ignores entries past latest version (author mistake)", () => {
    const entries = [
      { version: 1, changes: "c1", notes: null },
      { version: 5, changes: "c5", notes: null },
    ];
    const result = checkCodeValidity(fakeNode() as any, template(2, entries));
    expect(result?.changelogEntries.map((e) => e.version)).toEqual([1]);
  });

  it("returns empty changelog when user version equals latest", () => {
    const entries = [{ version: 2, changes: "c2", notes: null }];
    const result = checkCodeValidity(fakeNode({ version: 2 }) as any, template(2, entries));
    expect(result?.changelogEntries).toEqual([]);
  });
});
