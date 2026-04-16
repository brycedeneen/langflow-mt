import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";

if (!process.env.CI) {
  dotenv.config({ path: path.resolve(__dirname, "../.env") });
}

test.describe("Flow Assistant E2E Tests", () => {
  test(
    "Panel opens and shows empty state",
    { tag: ["@assistant", "@e2e"] },
    async ({ page }) => {
      // Navigate to home page and wait for bootstrap
      await awaitBootstrapTest(page);

      // Wait for the blank flow button
      await page.waitForSelector('[data-testid="blank-flow"]', {
        timeout: 30000,
      });

      // Create a new blank flow
      await page.getByTestId("blank-flow").click();

      // Wait for the assistant toggle button to be visible
      await page.waitForSelector('[data-testid="assistant-toggle-btn"]', {
        timeout: 30000,
      });

      // Click the assistant toggle button to open the panel
      await page.getByTestId("assistant-toggle-btn").click();

      // Verify the panel header contains "Flow Assistant"
      const panelHeader = page.locator("h3", { hasText: "Flow Assistant" });
      await expect(panelHeader).toBeVisible({ timeout: 5000 });

      // Verify "Assistant Not Configured" message is shown
      const notConfiguredText = page.locator("h3", {
        hasText: "Assistant Not Configured",
      });
      await expect(notConfiguredText).toBeVisible({ timeout: 5000 });

      // Verify the configure button is visible
      const configureButton = page.locator("button", {
        hasText: "Configure Assistant",
      });
      await expect(configureButton).toBeVisible({ timeout: 5000 });
    }
  );

  test(
    "Settings page allows configuration",
    { tag: ["@assistant", "@e2e"] },
    async ({ page }) => {
      // Navigate directly to the settings page
      await page.goto("/settings/assistant");

      // Wait for the page to load
      await page.waitForSelector('[id="provider"]', {
        timeout: 30000,
      });

      // Verify the settings page is loaded with the title
      const pageTitle = page.locator("h2", { hasText: "Flow Assistant" });
      await expect(pageTitle).toBeVisible();

      // Get the provider dropdown and verify it has OpenAI selected
      const providerSelect = page.locator('[id="provider"]');
      await expect(providerSelect).toBeVisible();

      // Verify current value is openai
      await expect(providerSelect).toHaveValue("openai");

      // Get the model dropdown
      const modelSelect = page.locator('[id="model"]');
      await expect(modelSelect).toBeVisible();

      // Verify gpt-4o is an available option and select it if not already selected
      const modelOptions = page.locator('[id="model"] option');
      const modelCount = await modelOptions.count();
      expect(modelCount).toBeGreaterThan(0);

      // Select gpt-4o from the model dropdown
      await modelSelect.selectOption("gpt-4o");
      await expect(modelSelect).toHaveValue("gpt-4o");

      // Get the API key input field
      const apiKeyInput = page.locator('[id="api-key"]');
      await expect(apiKeyInput).toBeVisible();

      // Enter a test API key (this is a fake key for testing purposes)
      const testApiKey = "sk-test-1234567890abcdef";
      await apiKeyInput.fill(testApiKey);
      await expect(apiKeyInput).toHaveValue(testApiKey);

      // Click the Save button
      const saveButton = page.locator("button", { hasText: "Save Settings" });
      await expect(saveButton).toBeVisible();
      await saveButton.click();

      // Verify the success message appears
      // Look for success alert/notification
      const successMessage = page.getByText("Assistant settings saved");
      await expect(successMessage).toBeVisible({ timeout: 10000 });

      // Verify the API key input is cleared after successful save
      await expect(apiKeyInput).toHaveValue("");
    }
  );
});
