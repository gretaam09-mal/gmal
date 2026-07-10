import { expect, test } from "@playwright/test";

test("home page loads and shows the Provision landing", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Provision" })).toBeVisible();
});
