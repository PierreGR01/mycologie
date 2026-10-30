import { existsSync, readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

const MANIFESTE = new URL("../data/latest.json", import.meta.url);
test.skip(!existsSync(MANIFESTE), "web/data/latest.json absent : lancer `make pipeline`");
const manifeste = existsSync(MANIFESTE) ? JSON.parse(readFileSync(MANIFESTE, "utf-8")) : null;

async function accepterAvertissement(page: Page) {
  await page.goto("./");
  const dialogue = page.locator("#avertissement");
  await expect(dialogue).toBeVisible();
  await expect(page.locator("#avertissement-ok")).toBeDisabled();
  await page.locator("#avertissement-lu").check();
  await page.locator("#avertissement-ok").click();
  await expect(dialogue).toBeHidden();
}

async function carteChargee(page: Page) {
  await page.waitForFunction(() => {
    const c = (window as any).__carte;
    return c && c.getSource("score") && c.isSourceLoaded("score") && c.loaded();
  }, undefined, { timeout: 60_000 });
}

test("avertissement au premier lancement, puis plus ensuite", async ({ page }) => {
  await accepterAvertissement(page);
  await page.reload();
  await expect(page.locator(".puce").first()).toBeVisible();
  await expect(page.locator("#avertissement")).toBeHidden();
});

test("sélecteur d'espèce, curseur de date, légende et sources", async ({ page }) => {
  await accepterAvertissement(page);
  await expect(page.locator(".puce")).toHaveCount(manifeste.especes.length);
  await expect(page.locator("#legende li")).toHaveCount(manifeste.legende.length);
  const jRun = manifeste.dates.findIndex((d: { date: string }) => d.date === manifeste.run);
  await expect(page.locator("#graduations span").first()).toHaveText(`J-${jRun}`);
  await expect(page.locator("#graduations span").last()).toHaveText(
    `J+${manifeste.dates.length - 1 - jRun}`,
  );

  await page.getByRole("radio", { name: "Girolle" }).click();
  await expect(page.getByRole("radio", { name: "Girolle" })).toHaveAttribute("aria-checked", "true");
  await page.locator("#curseur-date").fill("0");
  await expect(page.locator("#date-type")).toHaveText("analyse");
  await page.locator("#curseur-date").fill(String(manifeste.dates.length - 1));
  await expect(page.locator("#date-type")).toHaveText("prévision");
  await carteChargee(page);
  const url = await page.evaluate(() => (window as any).__carte.getSource("score").url);
  expect(url).toContain(`/girolle/${manifeste.dates.at(-1).date}.pmtiles`);

  await page.getByRole("radio", { name: "Morille" }).click();
  await expect(page.locator("#avertissement-espece")).toContainText("toxiques crues");

  await page.locator("#bouton-apropos").click();
  await expect(page.locator("#sources li")).toHaveCount(manifeste.sources.length);
  await expect(page.locator("#apropos")).toContainText("Aucune fonction d'identification");
});

test("installable : manifeste et service worker", async ({ page }) => {
  await page.goto("./");
  const webmanifest = await (await page.request.get("manifest.webmanifest")).json();
  expect(webmanifest.display).toBe("standalone");
  expect(webmanifest.icons.map((i: { sizes: string }) => i.sizes)).toEqual(
    expect.arrayContaining(["192x192", "512x512"]),
  );
  const actif = await page.evaluate(async () => !!(await navigator.serviceWorker.ready).active);
  expect(actif).toBe(true);
});

test("hors ligne : la dernière carte consultée reste affichée", async ({ page, context }) => {
  await accepterAvertissement(page);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.getByRole("radio", { name: "Trompette de la mort" }).click();
  await carteChargee(page);
  // La page met en cache le fichier PMTiles complet de la carte affichée.
  await expect
    .poll(
      () =>
        page.evaluate(async () => {
          const cache = await caches.open("derniere-carte");
          const memorise = (await cache.keys()).some((r) => r.url.includes("/trompette/"));
          return memorise && !!localStorage.getItem("derniere-carte-v1")?.includes("/trompette/");
        }),
      { timeout: 30_000 },
    )
    .toBe(true);

  await context.setOffline(true);
  const servies: number[] = [];
  page.on("response", (r) => {
    if (r.url().includes("/trompette/") && r.fromServiceWorker()) servies.push(r.status());
  });
  await page.reload();
  await expect(page.locator("#bandeau")).toContainText("Hors ligne");
  await expect(page.getByRole("radio", { name: "Trompette de la mort" })).toHaveAttribute(
    "aria-checked", "true",
  );
  await carteChargee(page);
  expect(servies.filter((s) => s === 206).length).toBeGreaterThan(0);

  // Une autre carte n'est pas disponible hors ligne.
  await page.getByRole("radio", { name: "Cèpe" }).click();
  await expect(page.locator("#bandeau")).toContainText("seule la dernière carte");
  await context.setOffline(false);
});

test.describe("écran large", () => {
  test.use({ viewport: { width: 1280, height: 900 }, isMobile: false, hasTouch: false });

  // Les tuiles sans pixel favorable sont absentes des cartes : la source doit tout de même
  // terminer son chargement, sinon la dernière carte n'est jamais mémorisée pour le hors-ligne.
  test("la carte termine son chargement malgré les tuiles absentes", async ({ page }) => {
    await accepterAvertissement(page);
    await carteChargee(page);
  });
});
