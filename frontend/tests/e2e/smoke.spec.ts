import { expect, test } from "@playwright/test";

test("home page loads and shows the Provision landing", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Provision" })).toBeVisible();
});

test("home page has a Sign in button that goes to the login", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
});

test("/app redirects to the canonical /dashboard URL", async ({ page }) => {
  await page.goto("/app");
  await expect(page).toHaveURL(/\/dashboard$/);
});
