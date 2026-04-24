import { expect, test } from "../../fixtures";

test(
  "user must not be able to login after logout and refresh the page",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await page.goto("/");

    await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

    await page.getByPlaceholder("Username").fill("langflow");
    await page.getByPlaceholder("Password").fill("langflow");

    await page.getByRole("button", { name: "Sign In" }).click();

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.getByTestId("user-profile-settings").click();

    await page.getByText("Logout", { exact: true }).click();

    await page.waitForTimeout(1000);

    await page.reload();

    await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

    const isLoggedIn = await page
      .getByTestId("mainpage_title")
      .isVisible()
      .catch(() => false);

    expect(isLoggedIn).toBeFalsy();
  },
);
