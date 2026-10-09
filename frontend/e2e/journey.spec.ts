import { expect, test, type Page } from "@playwright/test";

// One investor's complete journey through the product. Screenshots are written to
// docs/screenshots when SCREENSHOTS=1.
const shots = process.env.SCREENSHOTS === "1";
const shot = async (page: Page, name: string) => {
  if (shots) await page.screenshot({ path: `../docs/screenshots/${name}.png`, fullPage: true });
};

test.describe.configure({ mode: "serial" });

const email = `e2e-${Date.now()}@example.com`;
const password = "journey-test-42";

test("landing page calculates a live estimate", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("buy-to-let");
  await page.getByLabel("Purchase price (£)").fill("200000");
  await page.getByLabel("Rent per month (£)").fill("1100");
  await expect(page.getByText("6.60%")).toBeVisible();
  await page.getByRole("button", { name: /Stamp Duty Land Tax/ }).click();
  await expect(page.getByText(/sum over bands/)).toBeVisible();
  await shot(page, "01-landing");
});

test("unauthenticated visitors are sent to sign in", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?next=%2Fdashboard/);
});

test("register, explore the demo portfolio and analyse a property", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("short");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText(/at least 10 characters/i)).toBeVisible();
  await page.getByLabel("Name (optional)").fill("Jordan Investor");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  await page.getByRole("button", { name: "Load the demo portfolio" }).click();
  await expect(page.getByText("Properties tracked")).toBeVisible();
  await expect(page.getByText("7 are demo data")).toBeVisible();

  await page.getByRole("link", { name: "Properties", exact: true }).first().click();
  await expect(page.getByRole("link", { name: "Two-bed terrace, Fallowfield" })).toBeVisible();
  await page.getByPlaceholder("Search by name, town or postcode").fill("Leeds");
  await expect(page.getByRole("link", { name: "Three-bed terrace, Headingley" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Two-bed terrace, Fallowfield" })).toHaveCount(0);
  await page.getByPlaceholder("Search by name, town or postcode").fill("");
  await shot(page, "03-properties");

  await page.getByRole("link", { name: "Two-bed terrace, Fallowfield" }).click();
  await expect(page.getByText("Demonstration property", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Comparable sales" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await shot(page, "04-property-detail");

  await page.getByRole("button", { name: "Run analysis" }).click();
  await page.getByLabel("Offer price (£)").fill("195000");
  await page.getByRole("dialog").getByRole("button", { name: "Run analysis" }).click();
  await expect(page).toHaveURL(/\/analyses\//);
  await expect(page.getByText("Gross yield").first()).toBeVisible();
  await page.getByRole("button", { name: "Explain this deal" }).click();
  await expect(page.getByRole("heading", { name: "Risks" })).toBeVisible();
  await page.getByRole("button", { name: /Monthly cash flow after financing/ }).first().click();
  await expect(page.getByText(/annual mortgage payments\) ÷ 12/)).toBeVisible();
  await shot(page, "05-analysis");

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF report" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.pdf$/);
});

test("simulator, comparison, market and data pages", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await page.waitForLoadState("networkidle");
  await shot(page, "02-dashboard");

  await page.goto("/simulator");
  await expect(page.getByText("Monthly cash flow").first()).toBeVisible();
  await page.getByRole("button", { name: "Edit every assumption" }).click();
  await page.getByLabel("Interest rate").fill("9");
  await expect(page.getByText(/cash-flow negative/)).toBeVisible();
  await page.getByLabel("Interest rate").fill("4.5");
  await page.getByRole("button", { name: "Hide other assumptions" }).click();
  await page.waitForLoadState("networkidle");
  await shot(page, "06-simulator");

  await page.goto("/compare");
  for (const name of ["Two-bed terrace, Fallowfield", "Two-bed terrace, Lenton", "Three-bed terrace, Wavertree"]) {
    await page.getByRole("checkbox", { name: new RegExp(name) }).click();
  }
  await page.getByRole("button", { name: /Compare 3 properties/ }).click();
  await expect(page.getByRole("heading", { name: "Trade-offs" })).toBeVisible();
  await shot(page, "07-compare");

  await page.goto("/market");
  await expect(page.getByText("Median sale price")).toBeVisible();
  await expect(page.getByText("How reliable is the comparable-sales estimate?")).toBeVisible();
  await expect(page.getByText("Comparables method")).toBeVisible();
  await page.waitForLoadState("networkidle");
  await shot(page, "08-market");

  await page.goto("/data");
  await page.getByLabel("CSV file for: import properties").setInputFiles({
    name: "shortlist.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("title,asking_price,estimated_monthly_rent,postcode\nGood row,150000,900,M14 5RG\nBad row,-5,900,M14 5RG\n"),
  });
  await page.getByRole("button", { name: "Import properties", exact: true }).click();
  await expect(page.getByText(/1 of 2 rows imported, 1 rejected/)).toBeVisible();
  await shot(page, "09-data-sources");

  await page.goto("/reports");
  await expect(page.getByRole("cell", { name: "PDF", exact: true })).toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Default assumptions" })).toBeVisible();
  await shot(page, "10-settings");
});

test("mobile layout @mobile", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText("Gross rental yield")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  if (shots) await page.screenshot({ path: "../docs/screenshots/11-mobile-landing.png", fullPage: true });
});
