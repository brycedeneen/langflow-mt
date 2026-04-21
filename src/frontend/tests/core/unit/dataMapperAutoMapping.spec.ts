import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// Helpers copied from dataMapperModal.spec.ts (lines 12-66). Extract to a
// shared util file if both specs share too much duplication later.
async function addDataMapperToCanvas(page: import("@playwright/test").Page) {
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("Data Mapper");
  await page.waitForSelector('[data-testid="processingData Mapper"]', {
    timeout: 10000,
  });
  await page
    .getByTestId("processingData Mapper")
    .hover()
    .then(async () => {
      await page.getByTestId("add-component-button-data-mapper").click();
    });
  await adjustScreenView(page);
}

async function openMappingModal(page: import("@playwright/test").Page) {
  const btn = page.getByRole("button", {
    name: /configure mapping|edit mapping/i,
  });
  await btn.waitFor({ state: "visible", timeout: 10000 });
  await btn.click();
  await page.waitForSelector("text=Data Mapper", { timeout: 5000 });
}

async function addDestinationField(
  page: import("@playwright/test").Page,
  opts: { name: string; required?: boolean },
) {
  await page.getByTestId("data-mapper-add-field-btn").click();
  await page.getByTestId("data-mapper-field-name-input").fill(opts.name);
  if (opts.required) {
    const cb = page.getByTestId("data-mapper-field-required-checkbox");
    if (!(await cb.isChecked())) await cb.check();
  }
  await page.getByTestId("data-mapper-field-add-submit").click();
}

test.describe("Data Mapper — heavy auto-mapping", () => {
  test.beforeEach(async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.waitForSelector('[data-testid="blank-flow"]', { timeout: 30000 });
    await page.getByTestId("blank-flow").click();

    await addDataMapperToCanvas(page);
    await page.getByTestId("title-Data Mapper").click();
    await openMappingModal(page);

    await addDestinationField(page, { name: "full_name", required: true });
    await addDestinationField(page, { name: "email", required: false });
  });

  test("happy path: Suggest → Apply all → verifies blue rows applied", async ({
    page,
  }) => {
    await page.route("**/api/v1/session/DataMapperAutoMap/run", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          outputs: [
            {
              outputs: [
                {
                  outputs: {
                    message: {
                      message: JSON.stringify([
                        {
                          destination: "full_name",
                          transform: "template",
                          sources: [
                            { input: "users", field: "first_name" },
                            { input: "users", field: "last_name" },
                          ],
                          config: { template: "{first_name} {last_name}" },
                        },
                        {
                          destination: "email",
                          transform: "direct",
                          sources: [{ input: "users", field: "email" }],
                          config: {},
                        },
                      ]),
                    },
                  },
                },
              ],
            },
          ],
        }),
      }),
    );

    await page.getByRole("button", { name: /suggest mappings/i }).click();
    await expect(
      page.getByRole("button", { name: /apply all/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /apply all/i }).click();

    await expect(
      page.getByRole("button", { name: /apply all/i }),
    ).not.toBeVisible();
    await expect(page.getByText(/{first_name} {last_name}/)).toBeVisible();
  });

  test("per-row accept merges one entry and leaves others pending", async ({
    page,
  }) => {
    await page.route("**/api/v1/session/DataMapperAutoMap/run", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          outputs: [
            {
              outputs: [
                {
                  outputs: {
                    message: {
                      message: JSON.stringify([
                        {
                          destination: "full_name",
                          transform: "direct",
                          sources: [{ input: "users", field: "first_name" }],
                          config: {},
                        },
                        {
                          destination: "email",
                          transform: "direct",
                          sources: [{ input: "users", field: "email" }],
                          config: {},
                        },
                      ]),
                    },
                  },
                },
              ],
            },
          ],
        }),
      }),
    );

    await page.getByRole("button", { name: /suggest mappings/i }).click();
    await expect(
      page.getByRole("button", { name: /suggested \(2\)/i }),
    ).toBeVisible();

    await page
      .getByRole("button", { name: /accept suggestion for full_name/i })
      .click();
    await expect(
      page.getByRole("button", { name: /suggested \(1\)/i }),
    ).toBeVisible();
  });

  test("error state: retry after 404", async ({ page }) => {
    let callCount = 0;
    await page.route("**/api/v1/session/DataMapperAutoMap/run", (route) => {
      callCount += 1;
      if (callCount === 1) return route.fulfill({ status: 404, body: "Not Found" });
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          outputs: [
            {
              outputs: [
                { outputs: { message: { message: JSON.stringify([]) } } },
              ],
            },
          ],
        }),
      });
    });

    await page.getByRole("button", { name: /suggest mappings/i }).click();
    await expect(page.getByRole("alert")).toContainText(
      /not available|update Langflow/i,
    );
    await page.getByRole("button", { name: /retry/i }).click();
    await expect(page.getByRole("alert")).not.toBeVisible();
  });

  test("empty result shows the 'no new suggestions' chip", async ({ page }) => {
    await page.route("**/api/v1/session/DataMapperAutoMap/run", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          outputs: [
            {
              outputs: [{ outputs: { message: { message: "[]" } } }],
            },
          ],
        }),
      }),
    );

    await page.getByRole("button", { name: /suggest mappings/i }).click();
    await expect(page.getByText(/no new suggestions/i)).toBeVisible();
  });

  test("button is disabled when every destination is customized", async ({
    page,
  }) => {
    for (const field of ["full_name", "email"]) {
      await page
        .getByTestId(`data-mapper-transform-select-${field}`)
        .selectOption("static");
      await page.locator("textarea").last().fill('"x"');
    }
    await expect(
      page.getByRole("button", { name: /suggest mappings/i }),
    ).toBeDisabled();
  });
});
