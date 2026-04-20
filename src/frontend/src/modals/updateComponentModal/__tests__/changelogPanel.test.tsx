import { render, screen } from "@testing-library/react";
import ChangelogPanel from "../changelogPanel";

// react-markdown and remark-gfm are ESM-only; mock them for jest/jsdom
jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children: string }) => <span>{children}</span>,
}));
jest.mock("remark-gfm", () => ({ __esModule: true, default: () => {} }));

describe("ChangelogPanel", () => {
  it("renders version range and entries in the given order", () => {
    render(
      <ChangelogPanel
        userVersion={1}
        latestVersion={3}
        breaking={false}
        entries={[
          { version: 3, changes: "c3", notes: "n3" },
          { version: 2, changes: "c2", notes: null },
        ]}
      />,
    );
    expect(screen.getByText(/v1 → v3/)).toBeInTheDocument();
    expect(screen.getByText("v3")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getByText("c3")).toBeInTheDocument();
    expect(screen.getByText("n3")).toBeInTheDocument();
    expect(screen.getByText("c2")).toBeInTheDocument();
  });

  it("omits the Notes heading when notes is null", () => {
    const { container } = render(
      <ChangelogPanel
        userVersion={0}
        latestVersion={1}
        breaking={false}
        entries={[{ version: 1, changes: "c1", notes: null }]}
      />,
    );
    expect(container.textContent).not.toMatch(/Notes/);
  });

  it("renders fallback copy when entries is empty but outdated", () => {
    render(
      <ChangelogPanel
        userVersion={1}
        latestVersion={1}
        breaking={true}
        entries={[]}
        showEmptyFallback
      />,
    );
    expect(
      screen.getByText(/No changelog entries available/i),
    ).toBeInTheDocument();
  });

  it("returns null when entries is empty and showEmptyFallback is false", () => {
    const { container } = render(
      <ChangelogPanel
        userVersion={1}
        latestVersion={1}
        breaking={false}
        entries={[]}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
